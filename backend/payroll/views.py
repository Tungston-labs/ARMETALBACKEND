from django.shortcuts import render
from rest_framework import generics, permissions,status,filters
from employee.serializers import EmpBankPaymentSerializer
from user.permissions import IsHRAdmin
from rest_framework.exceptions import NotFound
from .serializers import EmployeeWithBankDetailsSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import EmployeePayrollRecord
from django.db import transaction
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from datetime import date
import calendar
from django.utils import timezone
from finance.models import FinanceRecord
from payroll.serializers import EmployeePayrollRecordSerializer
from finance.models import FinanceCategory
from rest_framework.generics import RetrieveAPIView
from django.http import HttpResponse
from .utils import generate_payslip_pdf
from django.http import HttpResponse, Http404
from payroll.models import EmployeePayrollRecord
from employee.models import Employee_db
from .utils import generate_payslip_pdf 





# Create your views here.
# employee list with bank details
class EmployeeBankDetailListView(generics.ListAPIView):
    serializer_class = EmployeeWithBankDetailsSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get_queryset(self):
        company = self.request.user.company
        if not company:
            return Employee_db.objects.none()
        return Employee_db.objects.filter(department__company=company,is_deleted=False)
    
#for updating status according to month and year(for all employees)



class EmployeePayrollRecordListCreateView(generics.GenericAPIView):
    serializer_class = EmployeePayrollRecordSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['employee__name_search', 'employee__employee_id','employee__employee_code']

    def get_queryset(self):
        company = self.request.user.company
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        department_id = self.request.query_params.get('department')

        employees = Employee_db.objects.filter(department__company=company,is_deleted=False)

        if department_id:
            employees = employees.filter(department__id=department_id)

        #  FILTER BY JOINING DATE
        if year and month:
            year = int(year)
            month = int(month)

            last_day = calendar.monthrange(year, month)[1]
            last_date_of_month = date(year, month, last_day)

            employees = employees.filter(joining_date__lte=last_date_of_month)

            queryset = EmployeePayrollRecord.objects.filter(
                employee__in=employees,
                year=year,
                month=month
            ).select_related(
                'employee',
                'employee__department'
            )
        else:
            queryset = EmployeePayrollRecord.objects.filter(
                employee__in=employees
            ).select_related(
                'employee',
                'employee__department'
            )

        return queryset



    def get(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if not year or not month:
            return Response({"detail": "Year and month are required."}, status=status.HTTP_400_BAD_REQUEST)

        year = int(year)
        month = int(month)

        last_day = calendar.monthrange(year, month)[1]
        last_date_of_month = date(year, month, last_day)

        employees = Employee_db.objects.filter(
            department__company=request.user.company,
            joining_date__lte=last_date_of_month,
            is_deleted=False
        )

        existing_records = self.get_queryset()
        existing_emp_ids = existing_records.values_list('employee_id', flat=True)

        # Create missing payroll records
        missing_emps = employees.exclude(id__in=existing_emp_ids)
        for emp in missing_emps:
            bank = getattr(emp, 'bank_details', None)
            if bank:
                EmployeePayrollRecord.objects.get_or_create(
                    employee=emp,
                    year=year,
                    month=month,
                    defaults={
                        "basic_salary": bank.basic_salary,
                        "salary_increment": bank.salary_increment,
                        "housing_allowance": bank.housing_allowance,
                        "transportation": bank.transportation,
                        "tds_deduction_amount": bank.tds_deduction_amount,
                        "payment_mode": bank.payment_mode,
                        "tax_regime": bank.tax_regime,
                        "pan_number": bank.pan_number,
                        "account_number": bank.account_number,
                        "status": "OnHold"
                    }
                )

        #  AUTO-SYNC SALARY IF EMPLOYEE BANK DETAILS CHANGED
        for record in existing_records:
            # 🔒 Do not touch verified payrolls
            if record.is_fully_verified():
                continue

            bank = getattr(record.employee, 'bank_details', None)
            if not bank:
                continue


            if (
                record.basic_salary != bank.basic_salary or
                record.salary_increment != bank.salary_increment or
                record.housing_allowance != bank.housing_allowance or
                record.transportation != bank.transportation or
                record.tds_deduction_amount != bank.tds_deduction_amount
            ):
                record.basic_salary = bank.basic_salary
                record.salary_increment = bank.salary_increment
                record.housing_allowance = bank.housing_allowance
                record.transportation = bank.transportation
                record.tds_deduction_amount = bank.tds_deduction_amount
                record.save()

        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


    @transaction.atomic
    def post(self, request):
        year = request.data.get('year')
        month = request.data.get('month')
        selected_employee_ids = request.data.get('employee_ids', [])
        new_status = request.data.get('status', 'Pending')

        if not year or not month:
            return Response({'error': 'Year and month are required.'}, status=status.HTTP_400_BAD_REQUEST)

        employees = Employee_db.objects.filter(id__in=selected_employee_ids, department__company=request.user.company,is_deleted=False)
        updated_records = []
        for emp in employees:
            bank = getattr(emp, 'bank_details', None)
            if not bank:
                continue

            record, _ = EmployeePayrollRecord.objects.update_or_create(
                employee=emp,
                year=year,
                month=month,
                defaults={
                    "basic_salary": bank.basic_salary,
                    "salary_increment": bank.salary_increment,
                    "housing_allowance": bank.housing_allowance,
                    "transportation": bank.transportation,
                    "tds_deduction_amount": bank.tds_deduction_amount,
                    "payment_mode": bank.payment_mode,
                    "tax_regime": bank.tax_regime,
                    "pan_number": bank.pan_number,
                    "account_number": bank.account_number,
                    "status": new_status,
                }
            )
            updated_records.append(record)

        serializer = self.get_serializer(updated_records, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class PayrollVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        month = request.data.get("month")
        year = request.data.get("year")

        record = get_object_or_404(
            EmployeePayrollRecord,
            employee__id=employee_id,
            month=month,
            year=year
        )

        user = request.user

        #  Only HR (admin or normal HR) from the same company can verify
        if not (user.is_hr_admin or user.is_hr):
            return Response({"error": "You are not allowed to verify payroll."}, status=403)

        if user.company != record.employee.department.company:
            return Response({"error": "You are not part of this company."}, status=403)

        #  Assign verification slots
        if record.hr1_verified_by is None:
            record.hr1_verified_by = user
            record.hr1_verified_at = now()
        elif record.hr2_verified_by is None and record.hr1_verified_by != user:
            #  Freeze payroll snapshot on final verification
            serializer = EmployeePayrollRecordSerializer(
                record, context={"request": request}
            )
            data = serializer.data

            record.working_days = data.get("working_days")
            record.days_present = data.get("days_present")
            record.lop_days = data.get("lop_days")
            record.lop_amount = data.get("lop_amount")

            record.hr2_verified_by = user
            record.hr2_verified_at = now()

        else:
            return Response({"error": "Already verified or duplicate HR"}, status=400)

        record.save()

        #  FIXED: pass request in serializer context
        serializer = EmployeePayrollRecordSerializer(record, context={"request": request})
        return Response(serializer.data)


from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction

class PayrollStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, employee_id):

        try:
            month = int(request.data.get("month"))
            year = int(request.data.get("year"))
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid month or year"},
                status=400
            )

        new_status = request.data.get("status")

        if not new_status:
            return Response(
                {"error": "Status is required"},
                status=400
            )

        record = get_object_or_404(
            EmployeePayrollRecord,
            employee__id=employee_id,
            month=month,
            year=year
        )

        # Block update unless fully verified
        if not record.is_fully_verified():
            return Response(
                {"error": "Both HRs must verify before updating status."},
                status=400
            )

        valid_statuses = dict(EmployeePayrollRecord.STATUS_CHOICES)

        if new_status not in valid_statuses:
            return Response(
                {"error": "Invalid status"},
                status=400
            )

        previous_status = (record.status or "").strip().lower()

        # Update payroll status
        record.status = new_status
        record.save()

        new_status_lower = (new_status or "").strip().lower()

        print("PREVIOUS STATUS:", previous_status)
        print("NEW STATUS:", new_status_lower)

        # Create finance record only when status changes to PAID
        if previous_status != "paid" and new_status_lower == "paid":

            basic = record.basic_salary or Decimal("0")
            increment = record.salary_increment or Decimal("0")
            housing = record.housing_allowance or Decimal("0")
            transport = record.transportation or Decimal("0")

            lop = record.lop_amount or Decimal("0")
            tds = record.tds_deduction_amount or Decimal("0")

            gross_salary = (
                basic +
                increment +
                housing +
                transport
            )

            net_salary = gross_salary - (lop + tds)

            company = record.employee.department.company

            print("COMPANY:", company)
            print("NET SALARY:", net_salary)

            # Get finance category
            try:
                salary_category = FinanceCategory.objects.get(
                    name__iexact="salary",
                    payment_type="OUT",
                    company=company
                )

                print("SALARY CATEGORY FOUND")

            except FinanceCategory.DoesNotExist:
                return Response(
                    {
                        "error": (
                            "Salary category not configured "
                            "for this company."
                        )
                    },
                    status=400
                )

            # Prevent duplicate finance entries
            already_exists = FinanceRecord.objects.filter(
                company=company,
                category=salary_category,
                note__icontains=str(record.employee.employee_id),
                date__month=month,
                date__year=year,
            ).exists()

            print("ALREADY EXISTS:", already_exists)

            if not already_exists:

                finance_record = FinanceRecord.objects.create(
                    company=company,
                    date=timezone.now().date(),
                    amount=net_salary,
                    payment_type="OUT",
                    category=salary_category,
                    note=(
                        f"Salary paid to "
                        f"{record.employee.name} "
                        f"(Employee ID: "
                        f"{record.employee.employee_id}) "
                        f"for {month}/{year}"
                    )
                )

                print("FINANCE RECORD CREATED:", finance_record.id)

        serializer = EmployeePayrollRecordSerializer(
            record,
            context={"request": request}
        )

        return Response(serializer.data)


    # payroll (payslip) view



class PayrollRecordDetailView(RetrieveAPIView):
    queryset = EmployeePayrollRecord.objects.all()
    serializer_class = EmployeePayrollRecordSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'



class EmployeePayslipView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = Employee_db.objects.get(user=request.user)
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        queryset = EmployeePayrollRecord.objects.filter(employee=employee)
        if year:
            queryset = queryset.filter(year=year)
        if month:
            queryset = queryset.filter(month__iexact=month)

        serializer = EmployeePayrollRecordSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)



from django.http import Http404, FileResponse, HttpResponse
from django.core.files.base import ContentFile
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

class PayslipDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month = request.query_params.get("month")
        year = request.query_params.get("year")

        if not (month and year):
            return HttpResponse("Month and year required", status=400)

        try:
            employee = Employee_db.objects.get(user=request.user)
        except Employee_db.DoesNotExist:
            return HttpResponse("Employee not found", status=404)

        try:
            record = EmployeePayrollRecord.objects.get(
                employee=employee,
                month=int(month),
                year=int(year),
            )
        except EmployeePayrollRecord.DoesNotExist:
            raise Http404("Payroll record not found")

        # If already generated, return the saved file
        if record.payslip_file:
            return FileResponse(
                record.payslip_file.open("rb"),
                as_attachment=True,
                filename=record.payslip_file.name.split("/")[-1],
            )

        # Serialize payroll
        serialized = EmployeePayrollRecordSerializer(
            record,
            context={"request": request},
        ).data

        # Generate PDF
        pdf_bytes = generate_payslip_pdf(serialized)

        # Save PDF into FileField
        filename = f"Payslip_{employee.employee_id}_{month}_{year}.pdf"

        record.payslip_file.save(
            filename,
            ContentFile(pdf_bytes),
            save=True,
        )
        print("Saved file:", record.payslip_file.name)
        print("Saved path:", record.payslip_file.path)

        # Return saved file
        return FileResponse(
            record.payslip_file.open("rb"),
            as_attachment=True,
            filename=filename,
        )

# views.py

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.shortcuts import get_object_or_404

from .models import EmployeePayrollRecord
from .serializers import EmployeePayrollRecordSerializer

class PayrollIncentiveUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, employee_id):

        month = request.data.get("month")
        year = request.data.get("year")

        incentive_amount = request.data.get(
            "incentive_amount",
            0
        )

        incentive_type = request.data.get(
            "incentive_type"
        )

        incentive_reason = request.data.get(
            "incentive_reason"
        )

        if not month or not year:

            return Response(
                {
                    "error": "Month and year are required"
                },
                status=400
            )

        payroll = get_object_or_404(
            EmployeePayrollRecord,
            employee__id=employee_id,
            month=month,
            year=year
        )

        # =====================================================
        # BLOCK VERIFIED PAYROLL UPDATE
        # =====================================================

        if payroll.is_fully_verified():

            return Response(
                {
                    "error": (
                        "Verified payroll cannot be modified"
                    )
                },
                status=400
            )

        # =====================================================
        # ALLOW ONLY ONE INCENTIVE UPDATE
        # =====================================================

        if (
            payroll.incentive_amount
            and payroll.incentive_amount > 0
        ):

            return Response(
                {
                    "error": (
                        "Incentive already added for this employee "
                        "for this month."
                    )
                },
                status=400
            )

        # =====================================================
        # SAVE INCENTIVE
        # =====================================================

        payroll.incentive_amount = incentive_amount
        payroll.incentive_type = incentive_type
        payroll.incentive_reason = incentive_reason

        payroll.save()

        serializer = EmployeePayrollRecordSerializer(
            payroll,
            context={"request": request}
        )

        return Response(serializer.data)
    





class PayrollDeductionUpdateView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, employee_id):

        month = request.data.get("month")
        year = request.data.get("year")

        deduction_amount = request.data.get(
            "deduction_amount",
            0
        )

        deduction_type = request.data.get(
            "deduction_type"
        )

        deduction_reason = request.data.get(
            "deduction_reason"
        )

        if not month or not year:

            return Response(
                {
                    "error": "Month and year are required"
                },
                status=400
            )

        payroll = get_object_or_404(
            EmployeePayrollRecord,
            employee__id=employee_id,
            month=month,
            year=year
        )

        if payroll.is_fully_verified():

            return Response(
                {
                    "error": (
                        "Verified payroll cannot be modified"
                    )
                },
                status=400
            )

        if (
            payroll.deduction_amount
            and payroll.deduction_amount > 0
        ):

            return Response(
                {
                    "error": (
                        "Deduction already added for this employee "
                        "for this month."
                    )
                },
                status=400
            )

        payroll.deduction_amount = deduction_amount
        payroll.deduction_type = deduction_type
        payroll.deduction_reason = deduction_reason

        payroll.save()

        serializer = EmployeePayrollRecordSerializer(
            payroll,
            context={"request": request}
        )

        return Response(serializer.data)
    

from decimal import Decimal

from django.db.models import Sum



class PayrollCountsView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        try:
            company = getattr(request.user, "company", None)

            if not company:
                return Response(
                    {
                        "detail": "Company not assigned to user."
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            # ---------------------------------------------
            # Company payroll records
            # ---------------------------------------------

            payroll_qs = EmployeePayrollRecord.objects.filter(
                employee__department__company=company
            )

            # ---------------------------------------------
            # Total payroll records
            # ---------------------------------------------

            total_payroll = payroll_qs.count()

            # ---------------------------------------------
            # Pending payroll
            # Pending + OnHold
            # ---------------------------------------------

            pending_payroll_count = payroll_qs.filter(
                status__in=["Pending", "OnHold"]
            ).count()

            # ---------------------------------------------
            # Total incentive
            # ---------------------------------------------

            total_incentive_amount = payroll_qs.aggregate(
                total=Sum("incentive_amount")
            )["total"] or Decimal("0.00")

            # ---------------------------------------------
            # Total deduction
            # ---------------------------------------------

            total_deduction_amount = payroll_qs.aggregate(
                total=Sum("deduction_amount")
            )["total"] or Decimal("0.00")

            # ---------------------------------------------
            # Response
            # ---------------------------------------------

            return Response(
                {
                    "total_payroll": total_payroll,
                    "pending_payroll_count": pending_payroll_count,
                    "total_incentive_amount": total_incentive_amount,
                    "total_deduction_amount": total_deduction_amount,
                },
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )