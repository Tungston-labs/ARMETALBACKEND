from employee.models import Employee_db
from employee.serializers import EmpBankPaymentSerializer
from rest_framework import serializers
from datetime import date, timedelta,datetime
from .models import EmployeePayrollRecord
from attendance.models import Attendance
from leave.models import LeaveRequest
from holidays.models import PublicHoliday
import calendar

class EmployeeWithBankDetailsSerializer(serializers.ModelSerializer):
    bank_details = EmpBankPaymentSerializer(read_only=True)

    class Meta:
        model = Employee_db
        fields = [
            'id',
            'name',
            'employee_id',
            'email',
            'department',
            'joining_date',
            'designation',
            'bank_details',
        ]

from datetime import date, datetime, timedelta
import calendar
from decimal import Decimal, ROUND_HALF_UP

from rest_framework import serializers

from attendance.models import Attendance
from leave.models import LeaveRequest
from holidays.models import PublicHoliday
from employee.models import SalaryIncrement

from .models import EmployeePayrollRecord

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import calendar

from rest_framework import serializers

from attendance.models import Attendance
from leave.models import LeaveRequest
from holidays.models import PublicHoliday
from employee.models import SalaryIncrement
from .models import EmployeePayrollRecord


class EmployeePayrollRecordSerializer(serializers.ModelSerializer):

    employee_name = serializers.CharField(
        source="employee.name",
        read_only=True
    )

    department = serializers.CharField(
        source="employee.department.name",
        read_only=True
    )

    employee_id = serializers.CharField(
        source="employee.employee_id",
        read_only=True
    )

    designation = serializers.CharField(
        source="employee.designation",
        read_only=True
    )

    email = serializers.EmailField(
        source="employee.email",
        read_only=True
    )

    joining_date = serializers.DateField(
        source="employee.joining_date",
        read_only=True
    )

    class Meta:
        model = EmployeePayrollRecord
        fields = "__all__"

    def to_representation(self, instance):

        data = super().to_representation(instance)

        employee = instance.employee
        department = employee.department
        company = department.company if department else None

        request = self.context.get("request")

        year = instance.year
        month = instance.month

        today = date.today()

        first_day = date(year, month, 1)

        last_day = date(
            year,
            month,
            calendar.monthrange(year, month)[1]
        )

        # ==========================================================
        # EMPLOYEE JOINING DATE
        # ==========================================================

        joining_date = employee.joining_date

        if isinstance(joining_date, datetime):
            joining_date = joining_date.date()

        # ==========================================================
        # EMPLOYEE START DATE
        # ==========================================================

        employee_start_date = max(
            first_day,
            joining_date
        )

        # ==========================================================
        # CALCULATION END DATE
        # ==========================================================
        #
        # CURRENT MONTH:
        #     joining date -> today
        #
        # PAST MONTH:
        #     joining date -> last day of month
        #
        # FUTURE MONTH:
        #     no working days
        #
        # ==========================================================

        if first_day > today:

            calculation_end_date = None

        elif last_day > today:

            # Current month
            calculation_end_date = today

        else:

            # Previous month
            calculation_end_date = last_day

        # ==========================================================
        # COMPANY HOLIDAYS / OFF DAYS
        # ==========================================================

        holidays_qs = PublicHoliday.objects.filter(
            company=company
        )

        holidays = set()
        company_off_days = set()

        for holiday in holidays_qs:

            # ------------------------------------------------------
            # WEEKLY COMPANY OFF DAY
            # ------------------------------------------------------

            if holiday.holiday_type == "company_off_day":

                if holiday.off_day_weekday is not None:

                    company_off_days.add(
                        holiday.off_day_weekday
                    )

            # ------------------------------------------------------
            # PUBLIC / COMPANY HOLIDAY
            # ------------------------------------------------------

            else:

                if (
                    holiday.date
                    and first_day <= holiday.date <= last_day
                ):
                    holidays.add(holiday.date)

        # ==========================================================
        # COMPANY FULL MONTH WORKING DAYS
        # ==========================================================
        #
        # This is always the complete month's working days.
        #
        # Example:
        #
        # August = 25 working days
        #
        # This is used for:
        #
        # daily salary = monthly salary / company working days
        #
        # 20,000 / 25 = 800
        #
        # ==========================================================

        company_working_dates = [
            first_day + timedelta(days=i)
            for i in range(
                (last_day - first_day).days + 1
            )
            if (
                first_day + timedelta(days=i)
            ).weekday() not in company_off_days
            and (
                first_day + timedelta(days=i)
            ) not in holidays
        ]

        company_working_days = Decimal(
            len(company_working_dates)
        )

        # ==========================================================
        # EMPLOYEE WORKING DAYS
        # ==========================================================
        #
        # IMPORTANT:
        #
        # Current month:
        #     joining date -> TODAY
        #
        # Previous month:
        #     joining date -> month end
        #
        # Future month:
        #     0
        #
        # ==========================================================

        if (
            calculation_end_date is not None
            and employee_start_date <= calculation_end_date
        ):

            employee_working_dates = [
                employee_start_date + timedelta(days=i)
                for i in range(
                    (
                        calculation_end_date
                        - employee_start_date
                    ).days + 1
                )
                if (
                    employee_start_date
                    + timedelta(days=i)
                ).weekday() not in company_off_days
                and (
                    employee_start_date
                    + timedelta(days=i)
                ) not in holidays
            ]

        else:

            employee_working_dates = []

        employee_working_days = Decimal(
            len(employee_working_dates)
        )

        # ==========================================================
        # ATTENDANCE
        # ==========================================================

        full_day_hours = Decimal(
            str(company.working_hours_per_day or 8)
        )

        half_day_hours = Decimal(
            str(company.half_day_hours or 4)
        )

        # ----------------------------------------------------------
        # Attendance calculation end date
        # ----------------------------------------------------------

        if (
            calculation_end_date is not None
            and employee_start_date <= calculation_end_date
        ):

            attendances = Attendance.objects.filter(
                employee=employee,
                date__range=(
                    employee_start_date,
                    calculation_end_date
                )
            )

        else:

            attendances = Attendance.objects.none()

        attendance_map = {
            attendance.date: attendance
            for attendance in attendances
        }

        full_days = Decimal("0")
        half_days = Decimal("0")

        # ==========================================================
        # COUNT PRESENT DAYS
        # ==========================================================

        for working_date in employee_working_dates:

            attendance = attendance_map.get(
                working_date
            )

            # ------------------------------------------------------
            # NO ATTENDANCE
            # ------------------------------------------------------

            if not attendance:
                continue

            # ------------------------------------------------------
            # PAID ATTENDANCE
            # ------------------------------------------------------

            if (
                attendance.attendance_type
                and attendance.attendance_type.lower() == "paid"
            ):

                full_days += Decimal("1")
                continue

            # ------------------------------------------------------
            # NORMAL ATTENDANCE
            # ------------------------------------------------------

            hours = Decimal(
                str(attendance.total_hours or 0)
            )

            if hours >= full_day_hours:

                full_days += Decimal("1")

            elif hours >= half_day_hours:

                half_days += Decimal("0.5")

        days_present = (
            full_days +
            half_days
        )

        # ==========================================================
        # APPROVED LEAVES
        # ==========================================================

        if (
            calculation_end_date is not None
            and employee_start_date <= calculation_end_date
        ):

            leave_requests = LeaveRequest.objects.filter(
                employee=employee,
                status="approved",
                from_date__lte=calculation_end_date,
                to_date__gte=employee_start_date
            )

        else:

            leave_requests = LeaveRequest.objects.none()

        approved_leave_dates = set()

        for leave in leave_requests:

            start = max(
                leave.from_date,
                employee_start_date
            )

            end = min(
                leave.to_date,
                calculation_end_date
            )

            if isinstance(start, datetime):
                start = start.date()

            if isinstance(end, datetime):
                end = end.date()

            for i in range(
                (end - start).days + 1
            ):

                leave_day = (
                    start +
                    timedelta(days=i)
                )

                # Only count actual employee working days
                if leave_day in employee_working_dates:

                    approved_leave_dates.add(
                        leave_day
                    )

        approved_leave_days = Decimal(
            len(approved_leave_dates)
        )

        # ==========================================================
        # PAYABLE DAYS
        # ==========================================================

        payable_days = (
            days_present +
            approved_leave_days
        )

        # Never exceed employee's working days
        payable_days = min(
            payable_days,
            employee_working_days
        )

        # ==========================================================
        # LOP DAYS
        # ==========================================================

        lop_days = max(
            employee_working_days -
            payable_days,
            Decimal("0")
        )

        # ==========================================================
        # SALARY INCREMENTS
        # ==========================================================

        increments_qs = SalaryIncrement.objects.filter(
            employee=employee
        ).order_by("date")

        total_increment_amount = Decimal("0")
        increment_history = []

        for increment in increments_qs:

            increment_amount = Decimal(
                str(
                    increment.increment_amount or 0
                )
            )

            total_increment_amount += increment_amount

            increment_history.append({
                "date": str(increment.date),
                "increment_amount": float(
                    increment_amount
                ),
            })

        # ==========================================================
        # TOTAL FULL MONTHLY SALARY
        # ==========================================================
        #
        # IMPORTANT:
        #
        # This is the employee's full company salary.
        #
        # Example:
        #
        # basic_salary = 20,000
        # increment = 0
        #
        # total_salary = 20,000
        #
        # This value is NOT reduced because of attendance.
        #
        # ==========================================================

        total_salary = (
            Decimal(
                str(instance.basic_salary or 0)
            )
            +
            total_increment_amount
        )

        # ==========================================================
        # INCENTIVE
        # ==========================================================

        incentive_amount = Decimal(
            str(instance.incentive_amount or 0)
        )

        # ==========================================================
        # OTHER DEDUCTION
        # ==========================================================

        deduction_amount = Decimal(
            str(instance.deduction_amount or 0)
        )

        # ==========================================================
        # DAILY SALARY
        # ==========================================================
        #
        # IMPORTANT:
        #
        # Daily salary uses FULL COMPANY working days.
        #
        # Example:
        #
        # 20,000 / 25 = 800
        #
        # NOT:
        #
        # 20,000 / employee working days
        #
        # ==========================================================

        daily_salary = (
            total_salary /
            (
                company_working_days
                or Decimal("1")
            )
        )

        daily_salary = daily_salary.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # PAYABLE SALARY
        # ==========================================================
        #
        # Employee gets salary only for:
        #
        # Present days
        # +
        # Approved leave days
        #
        # Example:
        #
        # Daily salary = 800
        # Payable days = 2
        #
        # Payable salary = 1,600
        #
        # ==========================================================

        payable_salary = (
            daily_salary *
            payable_days
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # LOP AMOUNT
        # ==========================================================

        lop_amount = (
            daily_salary *
            lop_days
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # FULL MONTHLY SALARY COMPONENTS
        # ==========================================================
        #
        # VERY IMPORTANT:
        #
        # These are based ONLY on total_salary.
        #
        # They are NOT based on payable_days.
        #
        # Example:
        #
        # Total salary = 20,000
        #
        # Basic       50% = 10,000
        # Housing     30% =  6,000
        # Transport   10% =  2,000
        # Special     10% =  2,000
        #
        # ==========================================================

        basic_percent = Decimal(
            str(
                company.basic_salary_percent or 0
            )
        )

        house_percent = Decimal(
            str(
                company.house_allowance_percent or 0
            )
        )

        transport_percent = Decimal(
            str(
                company.transport_allowance_percent or 0
            )
        )

        special_percent = Decimal(
            str(
                company.special_allowance_percent or 0
            )
        )

        # ==========================================================
        # BASIC SALARY
        # ==========================================================

        earning_basic_salary = (
            total_salary *
            basic_percent /
            Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # HOUSING ALLOWANCE
        # ==========================================================

        earning_housing_allowance = (
            total_salary *
            house_percent /
            Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # TRANSPORTATION
        # ==========================================================

        earning_transportation = (
            total_salary *
            transport_percent /
            Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # SPECIAL ALLOWANCE
        # ==========================================================

        earning_special_allowance = (
            total_salary *
            special_percent /
            Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # DO NOT ADJUST SPECIAL ALLOWANCE
        # ==========================================================
        #
        # DO NOT do this:
        #
        # calculated_total = basic + housing + transport + special
        # difference = total_salary - calculated_total
        # special += difference
        #
        # That logic was causing the negative special allowance.
        #
        # The company percentages directly determine each component.
        #
        # ==========================================================

        # ==========================================================
        # GROSS EARNINGS
        # ==========================================================

        gross_earnings = (
            payable_salary +
            incentive_amount
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        # ==========================================================
        # TDS
        # ==========================================================

        tds = Decimal(
            str(
                instance.tds_deduction_amount or 0
            )
        )

        # ==========================================================
        # FINAL NET PAY
        # ==========================================================

        net_pay = (
            payable_salary
            +
            incentive_amount
            -
            tds
            -
            deduction_amount
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        if net_pay < Decimal("0"):
            net_pay = Decimal("0")

        # ==========================================================
        # RESPONSE
        # ==========================================================

        data.update({

            # ======================================================
            # COMPANY
            # ======================================================

            "company": {

                "name": (
                    company.name
                    if company
                    else None
                ),

                "address": (
                    company.address
                    if company
                    else None
                ),

                "email": (
                    company.email
                    if company
                    else None
                ),

                "contact_number": (
                    company.contact_number
                    if company
                    else None
                ),

                "logo_url": (
                    request.build_absolute_uri(
                        company.logo.url
                    )
                    if (
                        request
                        and company
                        and company.logo
                    )
                    else None
                ),
            },

            # ======================================================
            # WORKING DAYS
            # ======================================================

            # Employee working days from joining date
            # until today for current month.

            "working_days": float(
                employee_working_days
            ),

            # Full company's monthly working days.

            "company_working_days": float(
                company_working_days
            ),

            # ======================================================
            # ATTENDANCE
            # ======================================================

            "days_present": float(
                days_present
            ),

            "approved_leave_days": float(
                approved_leave_days
            ),

            "payable_days": float(
                payable_days
            ),

            # ======================================================
            # LOP
            # ======================================================

            "lop_days": float(
                lop_days
            ),

            "lop_amount": float(
                lop_amount
            ),

            # ======================================================
            # SALARY
            # ======================================================

            "daily_salary": float(
                daily_salary
            ),

            "payable_salary": float(
                payable_salary
            ),

            "total_increment_amount": float(
                total_increment_amount
            ),

            "increment_history": increment_history,

            "gross_earnings": float(
                gross_earnings
            ),

            "total_deductions": float(
                tds + deduction_amount
            ),

            "net_pay": float(
                net_pay
            ),

            # ======================================================
            # INCENTIVE
            # ======================================================

            "incentive_amount": float(
                incentive_amount
            ),

            "incentive_type": (
                instance.incentive_type
            ),

            "incentive_reason": (
                instance.incentive_reason
            ),

            # ======================================================
            # OTHER DEDUCTION
            # ======================================================

            "deduction_amount": float(
                deduction_amount
            ),

            "deduction_type": (
                instance.deduction_type
            ),

            "deduction_reason": (
                instance.deduction_reason
            ),

            # ======================================================
            # EARNINGS
            # ======================================================
            #
            # FULL COMPANY SALARY STRUCTURE
            #
            # NOT prorated by attendance.
            #
            # ======================================================

            "earnings": [

                {
                    "label": "Basic Salary",
                    "amount": float(
                        earning_basic_salary
                    )
                },

                {
                    "label": "Housing Allowance",
                    "amount": float(
                        earning_housing_allowance
                    )
                },

                {
                    "label": "Transportation",
                    "amount": float(
                        earning_transportation
                    )
                },

                {
                    "label": "Special Allowance",
                    "amount": float(
                        earning_special_allowance
                    )
                },

                {
                    "label": "Incentive",
                    "amount": float(
                        incentive_amount
                    )
                },

            ],

            # ======================================================
            # DEDUCTIONS
            # ======================================================

            "deductions": [

                {
                    "label": "TDS Deduction",
                    "value": float(
                        tds
                    )
                },

                {
                    "label": "Loss of Pay",
                    "value": float(
                        lop_amount
                    )
                },

                {
                    "label": (
                        instance.deduction_type
                        or "Other Deduction"
                    ),
                    "value": float(
                        deduction_amount
                    )
                },

            ],

        })

        return data


class EmployeePayrollRecordSerializer2(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = EmployeePayrollRecord
        fields = '__all__'  # or list explicitly
        extra_fields = ['download_url']

    def get_download_url(self, obj):
        request = self.context.get('request')
        if obj.payslip_file:
            return request.build_absolute_uri(obj.payslip_file.url)
        return None


