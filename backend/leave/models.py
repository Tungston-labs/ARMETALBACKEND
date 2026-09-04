from django.db import models
from shared.models import TimeStampedModel
from employee.models import Employee_db
from rest_framework.exceptions import ValidationError
from decimal import Decimal
from django.db.models import Sum

class EmployeeLeaveBalance(TimeStampedModel):

    LEAVE_TYPES = [
        ('casual', 'Casual'),
        ('sick', 'Sick'),
        ('earned', 'Earned'),
        ('maternity', 'Maternity'),
        ('others', 'Others'),
    ]

    employee = models.ForeignKey(
        Employee_db,
        on_delete=models.CASCADE,
        related_name='leave_balances'
    )

    leave_type = models.CharField(
        max_length=20,
        choices=LEAVE_TYPES
    )

    total_leave = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    used_leave = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    remaining_leave = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )

    class Meta:
        unique_together = ('employee', 'leave_type')

    def save(self, *args, **kwargs):
        self.remaining_leave = (
            self.total_leave - self.used_leave
        )
        super().save(*args, **kwargs)

class LeaveRequest(TimeStampedModel):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    LEAVE_TYPES = [
        ('casual', 'Casual'),
        ('sick', 'Sick'),
        ('earned', 'Earned'),
        ('maternity', 'Maternity'),
        ('others', 'Others'),
    ]

    HALF_DAY_CHOICES = [
        ('forenoon', 'Forenoon'),
        ('afternoon', 'Afternoon'),
        ('full', 'Full Day'),
    ]

    employee = models.ForeignKey(Employee_db, on_delete=models.CASCADE, related_name='leave_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)
    reason = models.TextField()
    from_date = models.DateField()
    from_date_type = models.CharField(max_length=10, choices=HALF_DAY_CHOICES, default='full')
    to_date = models.DateField()
    to_date_type = models.CharField(max_length=10, choices=HALF_DAY_CHOICES, default='full')
    to_email = models.EmailField(help_text="Department lead email")
    cc_email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.employee.name} - {self.leave_type} ({self.status})"

    def calculate_leave_days(self):
        """Calculate total leave days considering half days"""
        total_days = (self.to_date - self.from_date).days + 1

        # Single day leave
        if self.from_date == self.to_date:
            if self.from_date_type == 'full':
                return 1
            else:
                return 0.5

        # Multi-day leave
        if self.from_date_type != 'full':
            total_days -= 0.5
        if self.to_date_type != 'full':
            total_days -= 0.5

        return total_days


    def save(self, *args, **kwargs):

        is_new = self._state.adding
        old_status = None

        if not is_new:
            old_status = LeaveRequest.objects.filter(
                pk=self.pk
            ).values_list(
                "status",
                flat=True
            ).first()

        leave_days = Decimal(
            str(self.calculate_leave_days())
        )

        balance = EmployeeLeaveBalance.objects.filter(
            employee=self.employee,
            leave_type=self.leave_type
        ).first()

        # ==========================================
        # PENDING -> APPROVED
        # ==========================================
        if (
            self.status == "approved"
            and old_status != "approved"
        ):

            if balance:

                balance.used_leave += leave_days

                # Never allow used_leave to exceed total_leave
                if balance.used_leave > balance.total_leave:
                    balance.used_leave = balance.total_leave

                balance.save()

        # ==========================================
        # APPROVED -> REJECTED/PENDING
        # ==========================================
        elif (
            old_status == "approved"
            and self.status != "approved"
        ):

            if balance:
                balance.used_leave -= leave_days

                if balance.used_leave < 0:
                    balance.used_leave = 0

                balance.save()

        super().save(*args, **kwargs)

        # ==========================================
        # RECALCULATE EMPLOYEE TOTAL LEAVE
        # ==========================================
        total_remaining = EmployeeLeaveBalance.objects.filter(
            employee=self.employee
        ).aggregate(
            total=Sum("remaining_leave")
        )["total"] or 0

        Employee_db.objects.filter(
            pk=self.employee.pk
        ).update(
            total_leave=total_remaining
        )
