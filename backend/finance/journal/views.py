
# finance/journal_entries/views.py

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone

from rest_framework import status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import JournalEntry
from .serializers import (
    JournalEntrySerializer,
    JournalEntryListSerializer,
)
from shared.pagination import CustomPagination


def get_user_company(user, request):
    if getattr(user, "is_superadmin", False):
        company_id = request.query_params.get("company")

        if not company_id:
            raise ValidationError(
                {"company": "Superadmin must specify a company ID."}
            )

        return company_id

    company = getattr(user, "company", None)

    if not company:
        raise PermissionDenied("Your user is not assigned to a company.")

    return company.pk


class JournalEntryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPagination

    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
    ]

    search_fields = [
        "entry_number",
        "reference_number",
        "description",
    ]

    ordering_fields = [
        "entry_number",
        "entry_date",
        "created_at",
        "status",
    ]

    ordering = ["-entry_date", "-id"]

    def get_queryset(self):
        company_id = get_user_company(
            self.request.user, self.request
        )

        qs = JournalEntry.objects.filter(
            company_id=company_id
        ).select_related(
            "created_by", "posted_by"
        ).prefetch_related("lines")

        # Default date range: current calendar month.
        today = timezone.localdate()
        first_day = today.replace(day=1)

        date_from = self.request.query_params.get(
            "date_from", first_day.isoformat()
        )
        date_to = self.request.query_params.get(
            "date_to", today.isoformat()
        )

        if date_from:
            qs = qs.filter(entry_date__gte=date_from)

        if date_to:
            qs = qs.filter(entry_date__lte=date_to)

        source = self.request.query_params.get("source")
        if source in ("manual", "auto"):
            qs = qs.filter(source=source)

        entry_status = self.request.query_params.get("status")
        if entry_status in ("draft", "posted", "voided"):
            qs = qs.filter(status=entry_status)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return JournalEntryListSerializer
        return JournalEntrySerializer

    def perform_create(self, serializer):
        company_id = get_user_company(
            self.request.user, self.request
        )

        serializer.save(
            company_id=company_id,
            created_by=self.request.user,
            source="manual",
            status="draft",
        )

    def perform_update(self, serializer):
        entry = self.get_object()

        if entry.status != "draft":
            raise ValidationError(
                "Only draft entries can be edited."
            )

        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != "draft":
            raise ValidationError(
                "Only draft entries can be deleted."
            )

        instance.delete()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # KPI aggregates use the selected date range and company.
        totals = queryset.aggregate(
            total_entries=Count("id"),
            total_debit=Sum("lines__debit_amount"),
            total_credit=Sum("lines__credit_amount"),
        )

        # Count entries without multiplying counts by their lines.
        counts = queryset.aggregate(
            manual_entries=Count(
                "id", filter=Q(source="manual"), distinct=True
            ),
            auto_entries=Count(
                "id", filter=Q(source="auto"), distinct=True
            ),
            draft_entries=Count(
                "id", filter=Q(status="draft"), distinct=True
            ),
            posted_entries=Count(
                "id", filter=Q(status="posted"), distinct=True
            ),
            voided_entries=Count(
                "id", filter=Q(status="voided"), distinct=True
            ),
        )

        # Aggregate debit and credit separately to avoid join
        # multiplication from entries having multiple lines.
        from .models import JournalEntryLine

        entry_ids = queryset.values("id")

        line_totals = JournalEntryLine.objects.filter(
            journal_entry_id__in=entry_ids
        ).aggregate(
            debit=Sum("debit_amount"),
            credit=Sum("credit_amount"),
        )

        debit = line_totals["debit"] or Decimal("0.00")
        credit = line_totals["credit"] or Decimal("0.00")

        # Determine entry-level balance counts from the full,
        # date/source/status-filtered set, not the current page.
        balanced_count = 0
        unbalanced_count = 0

        for entry in queryset:
            if entry.is_balanced:
                balanced_count += 1
            else:
                unbalanced_count += 1

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response = self.get_paginated_response(serializer.data)

            response.data["kpis"] = {
                "total_entries": counts["manual_entries"]
                + counts["auto_entries"],
                "auto_posted": queryset.filter(
                    source="auto", status="posted"
                ).count(),
                "manual_entries": counts["manual_entries"],
                "draft_entries": counts["draft_entries"],
                "voided_entries": counts["voided_entries"],
                "posted_entries": counts["posted_entries"],
                "balanced_entries": balanced_count,
                "unbalanced_entries": unbalanced_count,
                "total_debit": debit,
                "total_credit": credit,
            }

            return response

        serializer = self.get_serializer(queryset, many=True)

        return Response({
            "results": serializer.data,
            "kpis": {
                "total_entries": counts["manual_entries"]
                + counts["auto_entries"],
                "auto_posted": queryset.filter(
                    source="auto", status="posted"
                ).count(),
                "manual_entries": counts["manual_entries"],
                "draft_entries": counts["draft_entries"],
                "voided_entries": counts["voided_entries"],
                "posted_entries": counts["posted_entries"],
                "balanced_entries": balanced_count,
                "unbalanced_entries": unbalanced_count,
                "total_debit": debit,
                "total_credit": credit,
            },
        })

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def post(self, request, pk=None):
        entry = self.get_object()

        if entry.status != "draft":
            raise ValidationError(
                "Only draft entries can be posted."
            )

        lines = list(entry.lines.all())

        if len(lines) < 2:
            raise ValidationError(
                "At least two journal lines are required to post."
            )

        for line in lines:
            if (
                line.debit_amount < 0
                or line.credit_amount < 0
                or (
                    line.debit_amount > 0
                    and line.credit_amount > 0
                )
                or (
                    line.debit_amount == 0
                    and line.credit_amount == 0
                )
            ):
                raise ValidationError(
                    "Every line must contain a positive debit "
                    "or credit amount, but not both."
                )

        if entry.total_debit != entry.total_credit:
            raise ValidationError({
                "detail": "Entry is unbalanced.",
                "total_debit": str(entry.total_debit),
                "total_credit": str(entry.total_credit),
            })

        if entry.total_debit <= 0:
            raise ValidationError(
                "A posted journal entry must have a positive total."
            )

        entry.status = "posted"
        entry.posted_by = request.user
        entry.posted_at = timezone.now()
        entry.save(update_fields=[
            "status", "posted_by", "posted_at", "updated_at"
        ])

        return Response(
            JournalEntrySerializer(
                entry, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def void(self, request, pk=None):
        entry = self.get_object()

        if entry.status != "posted":
            raise ValidationError(
                "Only posted entries can be voided."
            )

        # This marks the entry voided; it does not delete it.
        # A reversal entry can be added in a later accounting step.
        entry.status = "voided"
        entry.save(update_fields=["status", "updated_at"])

        return Response(
            JournalEntrySerializer(
                entry, context={"request": request}
            ).data,
            status=status.HTTP_200_OK,
        )