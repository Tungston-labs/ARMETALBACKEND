from calendar import month_name, monthrange

from django.core.mail import EmailMessage
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils.timezone import now

from rest_framework import filters, generics, permissions, serializers, status
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from employee.models import Employee_db

from user.permissions import IsSuperAdmin

from superadmin.models import (
    Company,
    CompanySubscription,
    SubscriptionPlan,SubscriptionFeature
)

from superadmin.serializers import (
    CompanyCreateSerializer,
    CompanyListSerializer,
    CompanySelfUpdateSerializer,
    CompanySubscriptionSerializer,
    CompanySubscriptionActionSerializer,
    SubscriptionPlanSerializer,
    SubscriptionReminderSerializer,
    SubscriptionReminderSimpleSerializer,SubscriptionFeatureSerializer
)

from superadmin.management.commands.subscriptions import (
    get_billable_employee_count,calculate_subscription_amount
)

from superadmin.management.commands.subscription_service import (
    SubscriptionService,
)

from superadmin.management.commands.subscription_email_service import (
    SubscriptionEmailService,
)


# permission class

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_superadmin
    

#  create companies 

class CompanyCreateView(generics.CreateAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyCreateSerializer
    permission_classes = [IsSuperAdmin]



#  List all companies
class CompanyListView(generics.ListAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyCreateSerializer
    permission_classes = [IsSuperAdmin]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'company_id', 'contact_number', 'address']  # Customize as needed


#  Retrieve, Update, Delete a company
class CompanyDetailUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanyCreateSerializer
    permission_classes = [IsSuperAdmin]


    
# create and list subscriptions for a company
class CompanySubscriptionListCreateView(APIView):

    def get(self, request, company_id, year=None):
        year = year or now().year

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response(
                {"error": "Company not found"},
                status=404
            )

        subs = []

        # -----------------------------------------
        # Start from company creation month
        # -----------------------------------------
        if year == company.created_at.year:
            start_month = company.created_at.month
        else:
            start_month = 1

        for m in range(start_month, 13):

            obj, created = CompanySubscription.objects.get_or_create(
                company=company,
                month=m,
                year=year,
                defaults={
                    "amount": 0,
                    "employee_count": 0,
                    "amount_per_employee": company.amount_per_employee,
                }
            )

            # -----------------------------------------
            # Update only unpaid subscriptions
            # -----------------------------------------
            if obj.status == "unpaid":

                employee_count = get_billable_employee_count(
                    company,
                    m,
                    year
                )

                amount = calculate_subscription_amount(
                    company,
                    employee_count
                )

                obj.employee_count = employee_count

                # -----------------------------------------
                # Plan pricing
                # -----------------------------------------
                if company.plan:
                    obj.amount_per_employee = (
                        company.plan.extra_employee_price or 0
                    )
                else:
                    obj.amount_per_employee = (
                        company.amount_per_employee or 0
                    )

                obj.amount = amount

                obj.save()

            subs.append(obj)

        current_year = now().date().year
        current_month = now().date().month
        if int(year) == current_year:
            subs = [s for s in subs if s.month <= current_month]

        serializer = CompanySubscriptionSerializer(
            subs,
            many=True
        )

        return Response({
            "company": {
                "id": company.id,
                "company_id": company.company_id,
                "name": company.name,
                "address": company.address,
                "location": company.location,
                "country": company.country,
                "contact_number": company.contact_number,
                "email": company.email,

                "employee_count": Employee_db.objects.filter(
                    department__company=company,
                    is_deleted=False
                ).count(),

                "amount_per_employee": company.amount_per_employee,

                "currency": subs[0].currency if subs else "AED",

                "today": now().date(),
            },

            "subscriptions": serializer.data
        })

from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated

class MarkSubscriptionPaidView(UpdateAPIView):
    queryset = CompanySubscription.objects.all()
    serializer_class = CompanySubscriptionSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()

        new_status = request.data.get("status")

        if new_status not in ["paid", "unpaid"]:
            return Response(
                {
                    "detail": "Status must be either 'paid' or 'unpaid'."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        instance.status = new_status

        if new_status == "paid":
            instance.paid_date = now().date()
        else:
            instance.paid_date = None

        instance.save()

        serializer = self.get_serializer(instance)

        return Response(serializer.data)
    



class SendInvoiceEmailView(APIView):
    def post(self, request):
        entry = request.data.get("entry")
        company_id = request.data.get("company_id")  # <-- change here

        if not entry or not company_id:
            return Response({"error": "Missing required fields"}, status=400)

        try:
            company = Company.objects.get(id=company_id)
        except Company.DoesNotExist:
            return Response({"error": "Company not found"}, status=404)

        html_content = render_to_string("invoice_template.html", {
            "entry": entry,
            "company": company.name
        })

        email = EmailMessage(
            subject=f"Invoice for {entry['month_display']} {entry['year']}",
            body=html_content,
            from_email=None,
            to=[company.email]
        )
        email.content_subtype = "html"

        try:
            email.send()
            return Response({"message": "Email sent successfully"}, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)




class CompanyOverviewView(APIView):
    def get(self, request):
        from django.db.models import Q, Count
        from django.contrib.auth import get_user_model
        
        companies = Company.objects.order_by('-created_at')
        serializer = CompanyListSerializer(companies, many=True, context={'request': request})

        current_date = now().date()
        current_year = current_date.year
        current_month = current_date.month
        current_day = current_date.day

        # Find unpaid companies based on active, overdue subscriptions
        unpaid_companies = []
        for company in companies:
            billing_day = company.created_at.day
            start_year = company.created_at.year
            start_month = company.created_at.month
            
            # Fetch all unpaid subscriptions
            unpaid_subs = company.subscriptions.filter(status="unpaid")
            
            is_overdue = False
            for sub in unpaid_subs:
                # Ignore subscriptions before company creation month
                if sub.year < start_year or (sub.year == start_year and sub.month < start_month):
                    continue
                
                # Overdue check:
                # 1. Year is in the past
                # 2. Year is current, but month is in the past
                # 3. Year is current, month is current, and billing day <= current day
                if sub.year < current_year:
                    is_overdue = True
                    break
                elif sub.year == current_year:
                    if sub.month < current_month:
                        is_overdue = True
                        break
                    elif sub.month == current_month and billing_day <= current_day:
                        is_overdue = True
                        break
            
            if is_overdue:
                unpaid_companies.append(company)

        unpaid_serializer = CompanyListSerializer(unpaid_companies, many=True, context={'request': request})

        # Calculate Total Revenue in Indian Rupees (INR)
        paid_subs = CompanySubscription.objects.filter(status="paid")
        total_revenue_inr = 0.0
        for sub in paid_subs:
            amt = float(sub.amount or 0)
            curr = (sub.currency or "AED").upper()
            if curr == "INR":
                total_revenue_inr += amt
            elif curr == "SAR":
                total_revenue_inr += amt * 22.5
            elif curr == "USD":
                total_revenue_inr += amt * 83.5
            else:  # AED or others
                total_revenue_inr += amt * 22.8

        # Calculate Most Ordered Plan
        plan_counts = Company.objects.exclude(plan=None).values('plan__name').annotate(c=Count('id')).order_by('-c')
        most_ordered_plan = "No Plan"
        if plan_counts.exists():
            most_ordered_plan = plan_counts.first()['plan__name']

        # Calculate Active Subscriptions (Active Companies)
        active_subscriptions = Company.objects.filter(is_active=True).count()

        # Calculate Total Users
        User = get_user_model()
        total_users = User.objects.filter(is_active=True).count()

        # Calculate Revenue Overview (12 months of the current year in INR)
        months_short = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        revenue_overview = []
        for i in range(1, 13):
            subs_for_month = CompanySubscription.objects.filter(
                status="paid",
                year=current_year,
                month=i
            )
            monthly_revenue_inr = 0.0
            for sub in subs_for_month:
                amt = float(sub.amount or 0)
                curr = (sub.currency or "AED").upper()
                if curr == "INR":
                    monthly_revenue_inr += amt
                elif curr == "SAR":
                    monthly_revenue_inr += amt * 22.5
                elif curr == "USD":
                    monthly_revenue_inr += amt * 83.5
                else:  # AED or others
                    monthly_revenue_inr += amt * 22.8
            revenue_overview.append({
                "month": months_short[i-1],
                "revenue": monthly_revenue_inr
            })

        # Calculate Top Plans chart data in INR
        plan_revenue = {
            "Enterprise": 0.0,
            "PRO": 0.0,
            "Custom": 0.0,
            "Basic": 0.0
        }
        current_year_paid_subs = CompanySubscription.objects.filter(
            status="paid",
            year=current_year
        )
        for sub in current_year_paid_subs:
            amt = float(sub.amount or 0)
            curr = (sub.currency or "AED").upper()
            
            # Convert to INR
            amt_inr = amt
            if curr == "SAR":
                amt_inr = amt * 22.5
            elif curr == "USD":
                amt_inr = amt * 83.5
            elif curr != "INR":  # AED or default
                amt_inr = amt * 22.8
                
            plan_name = "Custom"
            if sub.company.plan:
                p_name_lower = sub.company.plan.name.lower()
                if "enterprise" in p_name_lower:
                    plan_name = "Enterprise"
                elif "pro" in p_name_lower:
                    plan_name = "PRO"
                elif "basic" in p_name_lower:
                    plan_name = "Basic"
            
            plan_revenue[plan_name] += amt_inr
            
        top_plans = [
            {"name": k, "value": v} for k, v in plan_revenue.items()
        ]

        data = {
            "total_companies": companies.count(),
            "unpaid_companies_count": len(unpaid_companies),
            "companies": serializer.data,
            "unpaid_companies": unpaid_serializer.data,
            "total_revenue": total_revenue_inr,
            "most_ordered_plan": most_ordered_plan,
            "active_subscriptions": active_subscriptions,
            "total_users": total_users,
            "revenue_overview": revenue_overview,
            "top_plans": top_plans
        }
        return Response(data)



class CompanySelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = request.user.company
        serializer = CompanySelfUpdateSerializer(company)
        return Response(serializer.data)

    def put(self, request):
        company = request.user.company
        serializer = CompanySelfUpdateSerializer(
            company,
            data=request.data,
            partial=False
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        company = request.user.company
        serializer = CompanySelfUpdateSerializer(
            company,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)






class CompanySubscriptionStatusAPIView(APIView):

    permission_classes = [
        IsSuperAdmin
    ]


    def post(self, request):


        serializer = (
            CompanySubscriptionActionSerializer(
                data=request.data
            )
        )


        serializer.is_valid(
            raise_exception=True
        )


        company_id = (
            serializer.validated_data[
                "company_id"
            ]
        )


        action = (
            serializer.validated_data[
                "action"
            ]
        )


        company = Company.objects.get(
            id=company_id
        )


        if action == "freeze":


            users = (
                SubscriptionService
                .freeze_company(company)
            )


            return Response(
                {
                    "message":
                    "Company frozen successfully",

                    "users_frozen":
                    users
                }
            )



        if action == "unfreeze":


            users = (
                SubscriptionService
                .unfreeze_company(company)
            )


            return Response(
                {
                    "message":
                    "Company unfreezed successfully",

                    "users_activated":
                    users
                }
            )
        



class SendSubscriptionReminderAPIView(APIView):

    permission_classes = [IsSuperAdmin]

    def post(self, request):

        serializer = SubscriptionReminderSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        company = get_object_or_404(
            Company,
            id=serializer.validated_data["company_id"]
        )

        SubscriptionEmailService.send_subscription_email(company)

        return Response(
            {
                "message": "Subscription reminder email sent successfully."
            },
            status=status.HTTP_200_OK
        )
    




class SendSubscriptionReminderMailAPIView(APIView):

    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = SubscriptionReminderSimpleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = get_object_or_404(
            Company,
            id=serializer.validated_data["company_id"]
        )

        SubscriptionEmailService.send_reminder_email(
            company=company,
            extra_email=serializer.validated_data.get("email")
        )

        return Response(
            {
                "message": "Reminder email sent successfully."
            },
            status=status.HTTP_200_OK
        )
    


#  plan module




class SubscriptionFeatureCreateListAPIView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        queryset = SubscriptionFeature.objects.all()

        serializer = SubscriptionFeatureSerializer(
            queryset,
            many=True
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = SubscriptionFeatureSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Feature created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class SubscriptionFeatureRetrieveUpdateDeleteAPIView(APIView):
    permission_classes = [IsSuperAdmin]

    def get_object(self, pk):
        return get_object_or_404(
            SubscriptionFeature,
            pk=pk
        )

    def get(self, request, pk):
        serializer = SubscriptionFeatureSerializer(
            self.get_object(pk)
        )

        return Response(serializer.data)

    def put(self, request, pk):
        feature = self.get_object(pk)

        serializer = SubscriptionFeatureSerializer(
            feature,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Feature updated successfully.",
                "data": serializer.data
            }
        )

    def delete(self, request, pk):
        self.get_object(pk).delete()

        return Response(
            {
                "message": "Feature deleted successfully."
            }
        )


from .models import SubscriptionPlan
from .serializers import SubscriptionPlanSerializer


class SubscriptionPlanCreateListAPIView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        queryset = SubscriptionPlan.objects.prefetch_related(
            "features"
        )

        serializer = SubscriptionPlanSerializer(
            queryset,
            many=True
        )

        return Response(serializer.data)

    def post(self, request):
        serializer = SubscriptionPlanSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Subscription plan created successfully.",
                "data": serializer.data
            },
            status=status.HTTP_201_CREATED
        )


class SubscriptionPlanRetrieveUpdateDeleteAPIView(APIView):
    permission_classes = [IsSuperAdmin]

    def get_object(self, pk):
        return get_object_or_404(
            SubscriptionPlan,
            pk=pk
        )

    def get(self, request, pk):
        serializer = SubscriptionPlanSerializer(
            self.get_object(pk)
        )

        return Response(serializer.data)

    def put(self, request, pk):
        plan = self.get_object(pk)

        serializer = SubscriptionPlanSerializer(
            plan,
            data=request.data
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Subscription plan updated successfully.",
                "data": serializer.data
            }
        )

    def delete(self, request, pk):
        self.get_object(pk).delete()

        return Response(
            {
                "message": "Subscription plan deleted successfully."
            }
        )
    

from django.db.models import Min, Max



class SubscriptionPlanSummaryAPIView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        summary = SubscriptionPlan.objects.aggregate(
            lowest_plan_amount=Min("base_price"),
            highest_plan_amount=Max("base_price"),
        )

        data = {
            "total_plans": SubscriptionPlan.objects.count(),
            "lowest_plan_amount": summary["lowest_plan_amount"] or 0,
            "highest_plan_amount": summary["highest_plan_amount"] or 0,
        }

        return Response(data, status=status.HTTP_200_OK)