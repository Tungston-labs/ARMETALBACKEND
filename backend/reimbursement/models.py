# reimbursements/models.py
from django.db import models
from django.conf import settings
from employee.models import Employee_db
class Reimbursement(models.Model):
    EXPENSE_CATEGORIES = [
        ("TRAVEL", "Travel Expenses"),
        ("ACCOMMODATION", "Accommodation"),
        ("MEALS", "Meals & Daily Allowance"),
        ("SUPPLIES", "Office Supplies & Equipment"),
        ("TRAINING", "Training & Certifications"),
        ("ENTERTAINMENT", "Client Entertainment"),
        ("BILLS", "Internet & Phone Bills"),
        ("HEALTHCARE", "Healthcare"),
        ("MISC", "General / Miscellaneous"),
        ("OTHERS", "Others"),
    ]
    STATUS_CATEGORIES = [
        ("On Hold", " On Hold"),
        ("In Verification", "In Verification"),
        ("Approve", "Approve"),
        ("Reject", "Reject"),
        
    ]

    employee = models.ForeignKey(Employee_db, on_delete=models.CASCADE, related_name="reimbursements")
    expense_category = models.CharField(max_length=50, choices=EXPENSE_CATEGORIES)
    to_mail = models.EmailField(null=True,blank=True)
    note = models.TextField(blank=True, null=True)
    date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50,choices=STATUS_CATEGORIES,null=True,blank=True,default="On Hold")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee} - {self.expense_category} - {self.amount}"


class ReimbursementImage(models.Model):
    reimbursement = models.ForeignKey(Reimbursement, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="reimbursements/")

    def __str__(self):
        return f"Image for {self.reimbursement.id}"

