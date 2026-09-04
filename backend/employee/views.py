from rest_framework import generics, status, filters,permissions
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from user.permissions import IsHRAdmin,IsEmployee
from .models import Employee_db,TempUpload,EmpDocument,EmpBankPaymentModel,ScheduleReminder
from .serializers import EmployeeSerializer,EmpDocumentSerializer,EmployeeProfileSerializer,EmployeeDocumentSummarySerializer,EmpBankPaymentSerializer,ScheduleReminderSerializer,EmployeeDashboardSerializer,TempUploadSerializer
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from shared.pagination import CustomPagination
from rest_framework import serializers
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.parsers import MultiPartParser,FormParser,JSONParser
from calendar import monthrange
from datetime import timedelta, date, datetime
from attendance.models import Attendance
from holidays.models import PublicHoliday
from rest_framework.exceptions import ValidationError
from .tasks import send_reminder
from django.utils.timezone import now as timezone_now
from employee.utils import send_push_notification
import calendar
from departments.models import Department
from leave.models import LeaveRequest
from rest_framework.pagination import PageNumberPagination
from django.core.files.storage import default_storage
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
from .models import SalaryIncrement
from .serializers import SalaryIncrementSerializer
from django.db import transaction, IntegrityError



# BASIC DETAILS-create ,list


from datetime import date

from django.db import transaction, IntegrityError
from django.db.models import Q

from rest_framework import generics, filters, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import Attendance
from leave.models import LeaveRequest
from employee.models import Employee_db
from .serializers import EmployeeSerializer



class EmployeeListCreateView(generics.ListCreateAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]

    filter_backends = [filters.SearchFilter]

    search_fields = [
        'name_search',
        'employee_id','employee_code'
    ]

    pagination_class = CustomPagination

    def get_queryset(self):
        user = self.request.user
        company = user.company

        if not company:
            return Employee_db.objects.none()

        department_id = self.request.query_params.get(
            'department_id'
        )

        attendance_status = self.request.query_params.get(
            'attendance_status'
        )

        # =====================================================
        # BASE EMPLOYEE QUERYSET
        # =====================================================

        queryset = Employee_db.objects.filter(
            department__company=company,
            is_deleted=False
        )

        # =====================================================
        # DEPARTMENT FILTER
        # =====================================================

        if department_id:
            queryset = queryset.filter(
                department_id=department_id
            )

        # =====================================================
        # TODAY
        # =====================================================

        today = date.today()

        # =====================================================
        # TODAY'S PRESENT EMPLOYEES
        # =====================================================

        present_employee_ids = set(
            Attendance.objects.filter(
                employee__department__company=company,
                date=today
            ).values_list(
                'employee_id',
                flat=True
            )
        )

        # =====================================================
        # TODAY'S ON-LEAVE EMPLOYEES
        # =====================================================

        leave_employee_ids = set(
            LeaveRequest.objects.filter(
                employee__department__company=company,
                employee__is_deleted=False,
                status='approved',
                from_date__lte=today,
                to_date__gte=today
            ).values_list(
                'employee_id',
                flat=True
            )
        )

        # =====================================================
        # ATTENDANCE STATUS FILTER
        # =====================================================

        if attendance_status:

            attendance_status = attendance_status.lower()

            if attendance_status == 'present':

                queryset = queryset.filter(
                    id__in=present_employee_ids
                )

            elif attendance_status == 'on_leave':

                queryset = queryset.filter(
                    id__in=leave_employee_ids
                )

            elif attendance_status == "absent":
                queryset = queryset.exclude(
                    id__in=present_employee_ids
                )

        # =====================================================
        # SORT
        # =====================================================

        queryset = queryset.order_by(
            'department__name',
            'name_search'
        )

        return queryset

    # =========================================================
    # LIST
    # =========================================================

    def list(self, request, *args, **kwargs):

        queryset = self.filter_queryset(
            self.get_queryset()
        )

        today = date.today()

        # =====================================================
        # PRESENT EMPLOYEES
        # =====================================================

        present_employee_ids = set(
            Attendance.objects.filter(
                employee__in=queryset,
                date=today
            ).values_list(
                'employee_id',
                flat=True
            )
        )

        # =====================================================
        # ON LEAVE EMPLOYEES
        # =====================================================

        leave_employee_ids = set(
            LeaveRequest.objects.filter(
                employee__in=queryset,
                status='approved',
                from_date__lte=today,
                to_date__gte=today
            ).values_list(
                'employee_id',
                flat=True
            )
        )

        # =====================================================
        # SERIALIZE
        # =====================================================

        serializer = self.get_serializer(
            queryset,
            many=True,
            context={
                'request': request
            }
        )

        data = serializer.data

        # =====================================================
        # ADD TODAY'S STATUS
        # =====================================================

        for employee_data, employee in zip(
            data,
            queryset
        ):

            if employee.id in leave_employee_ids:

                employee_data[
                    'today_attendance_status'
                ] = 'on_leave'

            elif employee.id in present_employee_ids:

                employee_data[
                    'today_attendance_status'
                ] = 'present'

            else:

                employee_data[
                    'today_attendance_status'
                ] = 'absent'

        # =====================================================
        # PAGINATION
        # =====================================================

        page = self.paginate_queryset(data)

        if page is not None:
            return self.get_paginated_response(page)

        return Response(data)

    # =========================================================
    # CREATE
    # =========================================================

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        try:

            with transaction.atomic():

                employee = serializer.save()

                company = employee.department.company

                company.number_of_employees = (
                    company.number_of_employees or 0
                ) + 1

                company.save(
                    update_fields=[
                        'number_of_employees'
                    ]
                )

        except IntegrityError:

            return Response(
                {
                    'detail': (
                        'Employee could not be created because '
                        'some employee details already exist.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:

            send_mail(
                subject=f'Welcome to {company.name}',

                message=f"""
Hello {employee.name},

You have been successfully registered as an employee at {company.name}.

Your login credentials are:

Username: {employee.employee_id}
Password: {employee.password}

Please log in and change your password as soon as possible.

Regards,
{company.name} HR
""",

                from_email=company.email,

                recipient_list=[
                    employee.email
                ],

                fail_silently=False,
            )

        except Exception as e:

            print(
                f'❌ Failed to send email to '
                f'{employee.email}: {str(e)}'
            )

        return Response(
            {
                'message': 'Employee created successfully.',

                'employee': EmployeeSerializer(
                    employee,
                    context={
                        'request': request
                    }
                ).data,

                'login_credentials': {
                    'username': employee.employee_id,
                    'password': employee.password
                }
            },
            status=status.HTTP_201_CREATED
        )
# list employees without pagination

# ------list employee according to admins company
class EmployeeListView(generics.ListAPIView):
    """
    List all employees of the user's company, optionally filtered by department.
    """
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'employee_id']
    pagination_class = None  # Return full list without pagination

    def get_queryset(self):
        user = self.request.user
        company = getattr(user, 'company', None)

        if not company:
            print(f"❌ No valid company found for user: {user.username}")
            return Employee_db.objects.none()

        department_id = self.request.query_params.get('department_id')
        queryset = Employee_db.objects.filter(department__company=company,is_deleted=False)

        if department_id:
            queryset = queryset.filter(department_id=department_id)

        print(f"✅ Returning employees for company: {company.name}, department_id: {department_id}")
        return queryset.order_by('name')

# ------------------------detail view,update,delete employee by admin
class EmployeeRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Employee_db.objects.all()
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated, IsHRAdmin]
    lookup_field = 'pk'

    def perform_update(self, serializer):
        instance = self.get_object()
        old_department = instance.department
        new_department = serializer.validated_data.get('department', old_department)

        # ✅ If department changed, remove as head from old department
        if old_department and old_department != new_department:
            if old_department.department_head == instance:
                old_department.department_head = None
                old_department.save(update_fields=['department_head'])

        # Save the updated employee
        serializer.save()


    def perform_destroy(self, instance):
        company = instance.department.company if instance.department else None
        department = instance.department

        # Soft delete employee
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["is_deleted", "deleted_at"])

        # Clear department_head if this employee was the head
        if department and department.department_head_id == instance.id:
            department.department_head = None
            department.save(update_fields=["department_head"])

        # NEW: remove from all projects (M2M cleanup)
        for project in instance.projects.all():
            project.employees.remove(instance)

        # Disable login
        if instance.user:
            instance.user.is_active = False
            instance.user.save(update_fields=["is_active"])

        # Update employee count
        if company:
            company.number_of_employees = max((company.number_of_employees or 1) - 1, 0)
            company.save(update_fields=["number_of_employees"])

# ------------------------create,list bank details of employee by admin




class EmpBankPaymentCreateListView(generics.ListCreateAPIView):
    serializer_class = EmpBankPaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        employee_id = self.kwargs.get('employee_id')
        return EmpBankPaymentModel.objects.filter(employee__id=employee_id)

    def perform_create(self, serializer):  # ✅ Move this method **inside** the class
        employee_id = self.kwargs.get('employee_id')
        employee = get_object_or_404(Employee_db, id=employee_id)

        if EmpBankPaymentModel.objects.filter(employee=employee).exists():
            raise serializers.ValidationError("Bank payment record already exists for this employee.")

        serializer.save(employee=employee)

# ------------------------detail view,update,delete employee bank details  by admin

class EmpBankPaymentEmployeeScopedDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = EmpBankPaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]
    parser_classes = [MultiPartParser, FormParser]
    def get_queryset(self):
        employee_id = self.kwargs.get('employee_id')
        return EmpBankPaymentModel.objects.filter(employee_id=employee_id)



class StandardResultsSetPagination(PageNumberPagination):
    page_size = 7
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
        })

# ------------------------list visa/contract expiring employees by admin

class UpcomingExpiryEmployeeListView(generics.ListAPIView):
    serializer_class = EmployeeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination 

    def get_queryset(self):
        user = self.request.user
        company = getattr(user, "company", None)
        if not company:
            return Employee_db.objects.none()  # no company assigned

        expiry_type = self.request.query_params.get("type")  # 'visa' or 'contract'
        today = timezone.now().date()
        one_month_later = today + timedelta(days=30)

        queryset = Employee_db.objects.filter(department__company=company,is_deleted=False)  # filter by company

        if expiry_type == "visa":
            queryset = queryset.filter(
                visa_expiry_date__gte=today,
                visa_expiry_date__lte=one_month_later
            )
        elif expiry_type == "contract":
            queryset = queryset.filter(
                contract_expiry_date__gte=today,
                contract_expiry_date__lte=one_month_later
            )
        else:
            queryset = Employee_db.objects.none()

        return queryset.order_by(
            "visa_expiry_date" if expiry_type == "visa" else "contract_expiry_date"
        )




# ------------------------upload employee document images

class UploadImageView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = TempUploadSerializer(data=request.data)
        if serializer.is_valid():
            instance = serializer.save()
            file_url = request.build_absolute_uri(instance.file.url)
            return Response({'url': file_url}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UploadImageDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsHRAdmin]

    def get_object(self, pk):
        return get_object_or_404(TempUpload, pk=pk)

    def get(self, request, pk):
        instance = self.get_object(pk)
        serializer = TempUploadSerializer(instance)
        return Response(serializer.data)

    def put(self, request, pk):
        instance = self.get_object(pk)
        serializer = TempUploadSerializer(instance, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        instance = self.get_object(pk)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EmployeeDocumentsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser,JSONParser)

    def get(self, request, employee_id):
        employee = get_object_or_404(Employee_db, id=employee_id)
        emp_doc, created = EmpDocument.objects.get_or_create(employee=employee)
        serializer = EmpDocumentSerializer(emp_doc)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, employee_id):
        employee = get_object_or_404(Employee_db, id=employee_id)

        try:
            emp_doc = EmpDocument.objects.get(employee=employee)
            serializer = EmpDocumentSerializer(emp_doc, data=request.data, partial=True)
        except EmpDocument.DoesNotExist:
            serializer = EmpDocumentSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(employee=employee)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, employee_id):  # ✅ Inside class now
        employee = get_object_or_404(Employee_db, id=employee_id)

        try:
            emp_doc = EmpDocument.objects.get(employee=employee)
        except EmpDocument.DoesNotExist:
            return Response({"detail": "Document not found for PATCH."}, status=status.HTTP_404_NOT_FOUND)


        # ✅ DEBUG: Print incoming files and data
        print("FILES:", request.FILES)
        print("DATA:", request.data)
        data = request.data.copy()
        for key in request.FILES:
            data.setlist(key, request.FILES.getlist(key))

        for field in request.FILES:
            old_file = getattr(emp_doc, field, None)
            if old_file and default_storage.exists(str(old_file)):
                default_storage.delete(str(old_file))

        serializer = EmpDocumentSerializer(emp_doc, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




class EmpDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EmpDocument.objects.all()
    serializer_class = EmpDocumentSerializer
    permission_classes = [permissions.IsAuthenticated,IsHRAdmin]
    lookup_field = 'employee_id' 




# employee dashboard in web application


class EmployeeDashboardAPIView(APIView):
    permission_classes = [IsHRAdmin]

    def get(self, request, id):
        try:
            employee = Employee_db.objects.get(id=id)
        except Employee_db.DoesNotExist:
            return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = EmployeeDashboardSerializer(employee, context={"request": request})
        return Response(serializer.data)

class SendEmailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_email = request.data.get("to")
        subject = request.data.get("subject")
        message = request.data.get("body")

        if not to_email or not subject or not message:
            return Response(
                {"detail": "Fields 'to', 'subject', and 'body' are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Include info about sender
        email_body = f"""
        Message from: {request.user.email}

        {message}
        """

        try:
            send_mail(
                subject,
                email_body,
                settings.DEFAULT_FROM_EMAIL,   # ALWAYS USE THIS
                [to_email],
                fail_silently=False,
            )
            return Response({"detail": "Email sent successfully!"})

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------dashboard for web application
class DashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def get(self, request):
        today = date.today()
        upcoming_range = today + timedelta(days=30)
        company = request.user.company  # HR admin's company

        # 1. Total employees list with department name
        employees_qs = Employee_db.objects.filter(
            department__company=company,is_deleted=False
        )

        total_employees_count = employees_qs.count()

        employees = employees_qs.order_by('-id')[:5]

        employee_list = [
            {
                "id": emp.id,
                "name": emp.name,
                "department": emp.department.name if emp.department else None,
                "designation": emp.designation,
                "employee_id": emp.employee_id,
                "profile_pic": request.build_absolute_uri(emp.profile_pic.url) if emp.profile_pic else None,
            }
            for emp in employees
        ]

        total_employees_count = employees.count()

        # 2. Upcoming visa expiries
        upcoming_visa_expiry_qs = employees_qs.filter(
            visa_expiry_date__range=[today, upcoming_range]
        )

        upcoming_visa_count = upcoming_visa_expiry_qs.count()

        upcoming_visa_expiry = [
            {
                "id": emp.id,
                "name": emp.name,
                "department": emp.department.name if emp.department else None,
                "visa_expiry_date": emp.visa_expiry_date,
                "profile_pic": request.build_absolute_uri(emp.profile_pic.url) if emp.profile_pic else None,
            }
            for emp in upcoming_visa_expiry_qs.order_by('visa_expiry_date')[:5]
        ]


        # 3. Pending leave requests
        pending_leaves_qs = LeaveRequest.objects.filter(
            status="pending",
            employee__department__company=company
        )
        pending_leaves = [
            {
                "id": leave.id,
                "employee": leave.employee.name,
                "department": leave.employee.department.name if leave.employee.department else None,
                "profile_pic": request.build_absolute_uri(leave.employee.profile_pic.url) if leave.employee.profile_pic else None,
                "leave_type": leave.leave_type,
                "from_date": leave.from_date,
                "to_date": leave.to_date,
                "reason": leave.reason,
            }
            for leave in pending_leaves_qs.order_by('-id')[:5]
        ]

        # 4. Department list with employee count
        department_list = [
            {
                "id": dept.id,
                "name": dept.name,
                "employee_count": dept.employees.count(),
                "head": {
                    "id": dept.department_head.id,
                    "name": dept.department_head.name
                } if dept.department_head else None
            }
            for dept in Department.objects.filter(company=company)
        ]

        # 5. Upcoming holidays (next 10)
        upcoming_holidays_qs = PublicHoliday.objects.filter(
            company=company,
            date__gte=today
        ).order_by("date")

        # 2. Slice safely when using it
        upcoming_holidays = [
            {
                "date": holiday.date,
                "description": holiday.description,
                "holiday_type": holiday.holiday_type,
            }
            for holiday in upcoming_holidays_qs[:10]  # slicing here is safe
        ]

        # 5a. All company holidays (for calendar)
        all_company_holidays_qs = PublicHoliday.objects.filter(company=company).order_by("date")
        all_company_holidays = [
            {
                "id": holiday.id,
                "date": holiday.date,
                "day": holiday.day,
                "description": holiday.description,
                "holiday_type": holiday.holiday_type,
            }
            for holiday in all_company_holidays_qs
        ]

        # 6. Upcoming contract expiries
        # Use the full queryset for filtering
        upcoming_contract_expiry_qs = employees_qs.filter(
            contract_expiry_date__range=[today, upcoming_range]
        )

        # Slice only when converting to a list
        upcoming_contract_expiry = [
            {
                "id": emp.id,
                "name": emp.name,
                "department": emp.department.name if emp.department else None,
                "contract_expiry_date": emp.contract_expiry_date,
                "employee_id": emp.employee_id,
                "profile_pic": request.build_absolute_uri(emp.profile_pic.url) if emp.profile_pic else None,
            }
            for emp in upcoming_contract_expiry_qs.order_by('contract_expiry_date')[:5]
        ]


        # 7. Active employees today
        active_today_count = Attendance.objects.filter(
            date=today,
            employee__department__company=company
        ).count()

        # 8. On leave today
        on_leave_today_count = LeaveRequest.objects.filter(
            from_date__lte=today,
            to_date__gte=today,
            employee__department__company=company,
            status='approved'
        ).values('employee').distinct().count()

        return Response({
            "total_employees": {
                "count": total_employees_count,
                "list": employee_list
            },
            "upcoming_visa_expiry": {
                "count": upcoming_visa_expiry_qs.count(),
                "list": upcoming_visa_expiry
            },
            "pending_leaves": {
                "count": pending_leaves_qs.count(),
                "list": pending_leaves
            },
            "departments": department_list,
            "upcoming_holidays": upcoming_holidays,
            "all_company_holidays": {
                "count": all_company_holidays_qs.count(),
                "list": all_company_holidays
            },
            "upcoming_contract_expiry": {
                "count": upcoming_contract_expiry_qs.count(),
                "list": upcoming_contract_expiry
            },
            "active_today_count": active_today_count,
            "on_leave_today_count": on_leave_today_count
        })





#--------------------------------- VIEW FOR EMPLOYEE--------------------------------



# list employees of same department



 

class EmployeesInMyDepartmentView(APIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        try:
            employee = Employee_db.objects.get(user=request.user,is_deleted=False)
            department = employee.department
        except Employee_db.DoesNotExist:
            return Response({"detail": "Employee profile not found."}, status=404)
        except AttributeError:
            return Response({"detail": "No department assigned."}, status=400)

        employees = Employee_db.objects.filter(department=department,is_deleted=False)
        count = employees.count()
        serializer = EmployeeSerializer(employees, many=True)

        # Get department head info
        head = department.department_head  # Assuming ForeignKey to Employee_db
        head_info = {
            "name": head.name if head else None,
            "profile_pic": head.profile_pic.url if head and head.profile_pic else None,
        }

        return Response({
            "department": department.name,
            "head": head_info,
            "count":count,
            "members": serializer.data

        })

# ------------------------profile view for employee

class EmployeeSelfView(APIView):
    permission_classes = [IsAuthenticated,IsEmployee]

    def get(self, request):
        if not hasattr(request.user, 'employee_db'):
            return Response({'error': 'Employee profile not found.'}, status=404)
        employee = request.user.employee_db
        return Response(EmployeeSerializer(employee).data)


class EmployeeProfileView(APIView):
    permission_classes = [IsAuthenticated, IsEmployee]

    def get(self, request):
        try:
            employee = Employee_db.objects.get(user=request.user)
            serializer = EmployeeProfileSerializer(employee, context={"request": request})
            return Response(serializer.data)
        except Employee_db.DoesNotExist:
            return Response({"detail": "Employee profile not found."}, status=404)

        



class EmployeeDocumentSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        try:
            employee = Employee_db.objects.get(user=request.user)
            serializer = EmployeeDocumentSummarySerializer(employee, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Employee_db.DoesNotExist:
            return Response({'detail': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)







class AttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            employee = Employee_db.objects.select_related(
                "department__company"
            ).get(user=user)
        except Employee_db.DoesNotExist:
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        company = employee.department.company

        # ✅ Dynamic company hours
        full_day_hours = Decimal(company.working_hours_per_day)
        half_day_hours = Decimal(company.half_day_hours)

        # ---------- Month Handling ----------
        month_param = request.query_params.get("month")

        try:
            if month_param:
                year, month = map(int, month_param.split("-"))
                from_date = date(year, month, 1)
            else:
                today = timezone.now().date()
                from_date = today.replace(day=1)

            last_day = monthrange(from_date.year, from_date.month)[1]
            to_date = from_date.replace(day=last_day)

        except ValueError:
            return Response(
                {"error": "Invalid month format. Use YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST
            )

        today = timezone.now().date()

        # ---------- All dates in month ----------
        total_dates = [
            from_date + timedelta(days=i)
            for i in range((to_date - from_date).days + 1)
        ]

        # ---------- Weekly Off (Company Configured) ----------
        company_off_day = PublicHoliday.objects.filter(
            company=company,
            holiday_type="company_off_day"
        ).first()

        off_day_name = company_off_day.day if company_off_day else None

        # ---------- Holidays ----------
        holidays = PublicHoliday.objects.filter(
            company=company,
            date__range=(from_date, to_date)
        ).exclude(holiday_type="company_off_day")

        holiday_dates = list(holidays.values_list("date", flat=True))

        # ---------- Actual Working Days ----------
        actual_working_days = [
            d for d in total_dates
            if (off_day_name is None or d.strftime("%A") != off_day_name)
            and d not in holiday_dates
        ]

        # ---------- Attendance ----------
        attendances = Attendance.objects.filter(
            employee=employee,
            date__range=(from_date, to_date)
        )

        present_days = 0
        half_days = 0
        total_hours = Decimal(0)
        attended_dates = set()

        for att in attendances:
            if not att.date:
                continue

            attended_dates.add(att.date)

            hours = Decimal(att.total_hours or 0)
            total_hours += hours

            if hours >= full_day_hours:
                present_days += 1

            elif hours >= half_day_hours:
                half_days += 1

        # ---------- Absent Days (Only Until Today) ----------
        absent_days = [
            d for d in actual_working_days
            if d <= today and d not in attended_dates
        ]

        # ---------- Remaining Working Days ----------
        remaining_days = [
            d for d in actual_working_days
            if d > today
        ]

        return Response({
            "month": from_date.strftime("%B %Y"),

            "working_days": len(actual_working_days),
            "present_days": present_days,
            "half_days": half_days,
            "absent_days": len(absent_days),

            "holiday_days": len(holiday_dates),
            "remaining_working_days": len(remaining_days),

            "total_hours": float(round(total_hours, 2)),

            # Optional (useful for mobile UI)
            "full_day_hours_required": float(full_day_hours),
            "half_day_hours_required": float(half_day_hours),
        })
# --------------------schedule remainder create list
class ReminderListCreateView(generics.ListCreateAPIView):
    serializer_class = ScheduleReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        employee = user.employee_db
        date_str = self.request.query_params.get("date")
        qs = ScheduleReminder.objects.filter(employee=employee, is_expired=False)
        if date_str:
            qs = qs.filter(scheduled_datetime__date=date_str)
        return qs

    
    def perform_create(self, serializer):
        employee = self.request.user.employee_db
        # Just save reminder with employee automatically
        reminder = serializer.save(employee=employee)
        return reminder




# --------------------schedule remainder create list


class ReminderRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ScheduleReminder.objects.all()
    serializer_class = ScheduleReminderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # restrict to logged-in user's reminders
        user = self.request.user
        employee = user.employee_db
        return ScheduleReminder.objects.filter(employee=employee)



# -------------------employee summary for mobile app




from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Sum
from datetime import date, timedelta, datetime
import calendar

from employee.models import Employee_db
from attendance.models import Attendance
from holidays.models import PublicHoliday

# Attendance model
from decimal import Decimal
import calendar
from datetime import date, timedelta




class EmployeeMonthlySummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            employee = request.user.employee_db
            department = employee.department
            company = department.company if department else None
        except Employee_db.DoesNotExist:
            return Response(
                {"error": "Employee not found"},
                status=404
            )

        if not department or not company:
            return Response(
                {
                    "error": "Employee not assigned to a department or company"
                },
                status=400,
            )

        full_day_hours = Decimal(company.working_hours_per_day or 8)
        half_day_hours = Decimal(company.half_day_hours or 4)

        today = timezone.now().date()

        year = today.year
        month = today.month

        first_day = date(year, month, 1)
        last_day = date(
            year,
            month,
            calendar.monthrange(year, month)[1]
        )

        all_days = [
            first_day + timedelta(days=i)
            for i in range((last_day - first_day).days + 1)
        ]

        # ---------------------------------------------------
        # Company Weekly Off
        # ---------------------------------------------------

        company_off = PublicHoliday.objects.filter(
            company=company,
            holiday_type="company_off_day"
        ).first()

        off_day_weekday = (
            company_off.off_day_weekday
            if company_off else None
        )

        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        off_day_name = (
            weekday_names[off_day_weekday]
            if off_day_weekday is not None
            else None
        )

        # ---------------------------------------------------
        # Public / Company Holidays
        # ---------------------------------------------------

        holidays = list(
            PublicHoliday.objects.filter(
                company=company,
                date__range=(first_day, last_day)
            )
            .exclude(holiday_type="company_off_day")
            .values_list("date", flat=True)
        )

        # ---------------------------------------------------
        # Working Days
        # ---------------------------------------------------

        working_days = [
            d
            for d in all_days
            if (
                off_day_weekday is None
                or d.weekday() != off_day_weekday
            )
            and d not in holidays
        ]

        # ---------------------------------------------------
        # Attendance
        # ---------------------------------------------------

        attendances = Attendance.objects.filter(
            employee=employee,
            date__range=(first_day, last_day),
        )

        total_hours = (
            attendances.aggregate(
                total=Sum("total_hours")
            )["total"]
            or Decimal(0)
        )

        present_days = []
        half_days = []

        for att in attendances:

            hours = Decimal(att.total_hours or 0)

            if hours >= full_day_hours:
                present_days.append(att.date)

            elif hours >= half_day_hours:
                half_days.append(att.date)

        # ---------------------------------------------------
        # Absent Days
        # ---------------------------------------------------

        absent_days = [
            d
            for d in working_days
            if d <= today
            and d not in present_days
            and d not in half_days
        ]

        # ---------------------------------------------------
        # Remaining Working Days
        # ---------------------------------------------------

        remaining_working_days = [
            d
            for d in working_days
            if d > today
        ]

        # ---------------------------------------------------
        # Weekly Off Dates
        # ---------------------------------------------------

        company_off_day_dates = [
            d
            for d in all_days
            if off_day_weekday is not None
            and d.weekday() == off_day_weekday
        ]

        # ---------------------------------------------------
        # Response
        # ---------------------------------------------------

        return Response({
            "month": today.strftime("%B"),

            "total_working_days": len(working_days),
            "total_working_days_dates": working_days,

            "total_working_hours": float(total_hours),

            "present_days_count": len(present_days),
            "present_days_dates": present_days,

            "half_days_count": len(half_days),
            "half_days_dates": half_days,

            "absent_days_count": len(absent_days),
            "absent_days_dates": absent_days,

            "remaining_working_days_count": len(remaining_working_days),
            "remaining_working_days_dates": remaining_working_days,

            "holidays_count": len(holidays),
            "holidays_dates": holidays,

            "company_off_day_name": off_day_name,
            "company_off_day_dates": company_off_day_dates,
            "company_off_day_count": len(company_off_day_dates),
        })



# salary increment create list view for employee

class SalaryIncrementListCreateView(generics.ListCreateAPIView):
    serializer_class = SalaryIncrementSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        employee_id = self.kwargs["employee_id"]
        return SalaryIncrement.objects.filter(employee_id=employee_id)

    def perform_create(self, serializer):
        serializer.save()



# archieved employee list

from rest_framework import generics, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from .models import Employee_db
from .serializers import DeletedEmployeeSerializer


class DeletedEmployeeListView(generics.ListAPIView):
    serializer_class = DeletedEmployeeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [
        filters.SearchFilter,
    ]

    # Search by name, employee code, or email
    search_fields = [
        "name",
        "employee_code",
        "email",
    ]

    def get_queryset(self):
        queryset = Employee_db.objects.filter(
            is_deleted=True
        ).select_related("department")

        # Department filter
        department = self.request.query_params.get("department")

        if department:
            queryset = queryset.filter(
                department__name=department
            )

        # Exit month filter
        # Example: 2026-08
        deleted_date = self.request.query_params.get("deleted_date")

        if deleted_date:
            try:
                year, month = deleted_date.split("-")

                year = int(year)
                month = int(month)

                if month < 1 or month > 12:
                    raise ValueError

                queryset = queryset.filter(
                    deleted_at__year=year,
                    deleted_at__month=month,
                )

            except (ValueError, TypeError):
                raise ValidationError({
                    "deleted_date": [
                        "Use YYYY-MM format, for example 2026-08."
                    ]
                })

        return queryset.order_by("-deleted_at")
    


class EmployeeRehireView(APIView):
    permission_classes = [IsAuthenticated, IsHRAdmin]

    def post(self, request, id):
        try:
            employee = Employee_db.objects.select_related("user").get(
                id=id
            )

            if not employee.is_deleted:
                return Response(
                    {"error": "Employee is already active."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            with transaction.atomic():

                employee.is_deleted = False
                employee.deleted_at = None
                employee.save(
                    update_fields=["is_deleted", "deleted_at"]
                )

                if employee.user:
                    employee.user.is_active = True
                    employee.user.save(
                        update_fields=["is_active"]
                    )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Employee_db.DoesNotExist:
            return Response(
                {"error": "Employee not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception:
            return Response(
                {"error": "Unable to rehire employee."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        



class CompanyDesignationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, "company", None)

        if not company:
            return Response(
                {"detail": "User has no company assigned."},
                status=status.HTTP_400_BAD_REQUEST
            )

        designations = (
            Employee_db.objects
            .filter(
                department__company=company,
                is_deleted=False
            )
            .exclude(
                designation__isnull=True
            )
            .exclude(
                designation=""
            )
            .values_list(
                "designation",
                flat=True
            )
            .distinct()
            .order_by("designation")
        )

        return Response(
            {
                "designations": list(designations)
            },
            status=status.HTTP_200_OK
        )