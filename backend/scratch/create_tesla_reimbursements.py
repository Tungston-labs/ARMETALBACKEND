import os
import django
import sys
from datetime import date

# Setup django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from superadmin.models import Company
from departments.models import Department
from employee.models import Employee_db
from reimbursement.models import Reimbursement

try:
    company = Company.objects.get(company_id="tesla1")
    print(f"Found company: {company.name}")
    
    # 1. Create a default department if not exists
    dept, created = Department.objects.get_or_create(
        company=company,
        name="HR Department"
    )
    print(f"Department: {dept.name} (Created: {created})")

    # 2. Create a mock employee
    emp_email = "jane.doe.tesla1@example.com"
    emp, created = Employee_db.objects.get_or_create(
        email=emp_email,
        defaults={
            "name": "Jane Doe",
            "address": "Dubai, UAE",
            "dob": date(1995, 5, 15),
            "gender": "Female",
            "designation": "Senior HR Executive",
            "department": dept,
            "employment_type": "Full-time",
        }
    )
    print(f"Employee: {emp.name} (Created: {created})")

    # 3. Create mock reimbursements if they don't exist
    r1, c1 = Reimbursement.objects.get_or_create(
        employee=emp,
        expense_category="TRAVEL",
        amount=250.00,
        defaults={
            "date": date.today(),
            "note": "Travel allowance for client meeting",
            "status": "On Hold"
        }
    )
    r2, c2 = Reimbursement.objects.get_or_create(
        employee=emp,
        expense_category="MEALS",
        amount=75.50,
        defaults={
            "date": date.today(),
            "note": "Client dinner meal reimbursement",
            "status": "In Verification"
        }
    )
    r3, c3 = Reimbursement.objects.get_or_create(
        employee=emp,
        expense_category="BILLS",
        amount=120.00,
        defaults={
            "date": date.today(),
            "note": "Office internet connectivity bill",
            "status": "Approve"
        }
    )
    print(f"Reimbursements created: TRAVEL={c1}, MEALS={c2}, BILLS={c3}")
    print("✅ Completed successfully!")
except Exception as e:
    print("❌ Failed:", str(e))
