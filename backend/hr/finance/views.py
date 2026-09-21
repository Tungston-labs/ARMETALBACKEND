from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import FinanceRecord,FinanceCategory
from .serializers import FinanceRecordSerializer
from shared.pagination import CustomPagination
from rest_framework.permissions import IsAuthenticated
from user.permissions import IsHRAdmin
from django.db.models import Sum
from rest_framework.response import Response



from rest_framework import generics, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import FinanceRecord
from .serializers import FinanceRecordSerializer,FinanceCategorySerializer
from shared.pagination import CustomPagination

class FinanceCategoryListCreateView(generics.ListCreateAPIView):
    serializer_class = FinanceCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        payment_type = self.request.query_params.get("payment_type")

        queryset = FinanceCategory.objects.filter(company=user.company)

        if payment_type:
            queryset = queryset.filter(payment_type=payment_type)

        return queryset

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)


class FinanceRecordListCreateView(generics.ListCreateAPIView):
    serializer_class = FinanceRecordSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["category", "payment_type"]
    search_fields = ["note", "category__name"]

    # ---------------------------------------------------
    # QUERYSET (Company Based)
    # ---------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        if getattr(user, "is_superadmin", False):
            queryset = FinanceRecord.objects.filter(
                company__isnull=True
            )
        elif user.company:
            queryset = FinanceRecord.objects.filter(
                company=user.company
            )
        else:
            return FinanceRecord.objects.none()

        # Filter by selected month
        month = self.request.query_params.get("month")

        if month:
            try:
                year, month_number = month.split("-")

                queryset = queryset.filter(
                    date__year=int(year),
                    date__month=int(month_number)
                )

            except (ValueError, TypeError):
                pass

        # Sort by finance transaction date
        return queryset.order_by("-date", "-created_at")    
    # ---------------------------------------------------
    # CREATE (Auto assign company)
    # ---------------------------------------------------
    def perform_create(self, serializer):
        user = self.request.user

        if getattr(user, "is_superadmin", False):
            serializer.save(company=None)
        else:
            serializer.save(company=user.company)

    # ---------------------------------------------------
    # LIST WITH FINANCIAL SUMMARY
    # ---------------------------------------------------
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        user = request.user

        # ---------- Summary Query ----------
        if getattr(user, "is_superadmin", False):
            summary_qs = FinanceRecord.objects.filter(company__isnull=True)
        else:
            summary_qs = FinanceRecord.objects.filter(company=user.company)

        # ---------- Calculations ----------
        total_income = summary_qs.filter(payment_type="IN").aggregate(
            total=Sum("amount")
        )["total"] or 0

        total_expense = summary_qs.filter(payment_type="OUT").aggregate(
            total=Sum("amount")
        )["total"] or 0

        cash_balance = total_income - total_expense

        # ---------- Pagination ----------
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            # Inject summary fields (no structure change)
            response.data["total_income"] = total_income
            response.data["total_expense"] = total_expense
            response.data["cash_balance"] = cash_balance

            return response

        serializer = self.get_serializer(queryset, many=True)

        return Response({
            "results": serializer.data,
            "total_income": total_income,
            "total_expense": total_expense,
            "cash_balance": cash_balance,
        })

class FinanceRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = FinanceRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        if getattr(user, "is_superadmin", False):
            return FinanceRecord.objects.all()

        return FinanceRecord.objects.filter(company=user.company)

