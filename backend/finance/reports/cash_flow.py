from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.banking.models import BankAccount, BankTransaction
from user.permissions import IsCompanyActive, IsHRAdmin


ZERO = Decimal("0.00")


def _date_range(request):
    today = timezone.localdate()
    raw_from = request.query_params.get("date_from")
    raw_to = request.query_params.get("date_to")
    start = parse_date(raw_from) if raw_from else today.replace(day=1)
    end = parse_date(raw_to) if raw_to else today
    if (raw_from and start is None) or (raw_to and end is None):
        raise ValidationError({"date": "Use valid dates in YYYY-MM-DD format."})
    if start > end:
        raise ValidationError({"date_to": "End date must be on or after date_from."})
    return start, end


def _activity(transaction):
    """Classify a bank transaction for the cash-flow statement."""
    description = transaction.description.lower()
    if transaction.transaction_type in {"bank_transfer"}:
        return None, None  # Internal movements must not change consolidated cash.
    if transaction.transaction_type == "customer_receipt":
        return "operating", "Customer Receipts"
    if transaction.transaction_type == "vendor_payment":
        return "operating", "Vendor Payments"
    if transaction.transaction_type == "loan_disbursement":
        return "financing", "Loan Received"
    if transaction.transaction_type == "loan_repayment":
        return "financing", "Loan Repayment"

    # Other bank entries can be categorized from their memo/description.
    if any(word in description for word in ("equipment sale", "sale of equipment", "asset sale")):
        return "investing", "Sale of Equipment"
    if any(word in description for word in ("equipment purchase", "purchase of equipment", "fixed asset")):
        return "investing", "Purchase of Equipment"
    if "salary" in description or "payroll" in description:
        return "operating", "Salary Payments"
    if "rent" in description or "utilit" in description:
        return "operating", "Rent & Utilities"
    if "tax" in description or "vat" in description:
        return "operating", "Tax Payments"
    if "interest" in description:
        return "operating", "Interest Received" if transaction.money_in else "Interest Paid"
    if transaction.transaction_type == "deposit":
        return "operating", "Other Cash Receipts"
    if transaction.transaction_type == "withdrawal":
        return "operating", "Other Cash Payments"
    return "operating", transaction.description.strip() or "Other Cash Movement"


def _money(amount):
    return str(Decimal(amount or ZERO).quantize(Decimal("0.01")))


class CashFlowReportView(APIView):
    permission_classes = [IsAuthenticated, IsCompanyActive, IsHRAdmin]

    def get(self, request):
        company_id = getattr(request.user, "company_id", None)
        if not company_id:
            raise ValidationError({"company": "Your user account is not linked to a company."})
        start, end = _date_range(request)

        accounts = BankAccount.objects.filter(company_id=company_id, status="active")
        search = request.query_params.get("search", "").strip()
        if search:
            accounts = accounts.filter(
                Q(bank_name__icontains=search)
                | Q(account_holder_name__icontains=search)
                | Q(account_number__icontains=search)
            )
        bank_account_id = request.query_params.get("bank_account_id")
        if bank_account_id:
            if not bank_account_id.isdigit():
                raise ValidationError({"bank_account_id": "Must be a positive integer."})
            accounts = accounts.filter(id=int(bank_account_id))
        account_ids = list(accounts.values_list("id", flat=True))

        # Opening cash is each account's configured opening balance plus all
        # recorded movements before the requested period.
        opening = accounts.aggregate(total=Sum("opening_balance"))["total"] or ZERO
        prior = BankTransaction.objects.filter(
            company_id=company_id,
            bank_account_id__in=account_ids,
            transaction_date__lt=start,
        )
        prior_totals = prior.aggregate(inflow=Sum("money_in"), outflow=Sum("money_out"))
        opening += (prior_totals["inflow"] or ZERO) - (prior_totals["outflow"] or ZERO)

        transactions = BankTransaction.objects.filter(
            company_id=company_id,
            bank_account_id__in=account_ids,
            transaction_date__gte=start,
            transaction_date__lte=end,
        ).select_related("bank_account").order_by("transaction_date", "id")
        grouped = {
            "operating": {},
            "investing": {},
            "financing": {},
        }
        for txn in transactions:
            section, label = _activity(txn)
            if section is None:
                continue
            row = grouped[section].setdefault(label, {"cash_in": ZERO, "cash_out": ZERO})
            row["cash_in"] += txn.money_in
            row["cash_out"] += txn.money_out

        sections = {}
        cash_in = ZERO
        cash_out = ZERO
        for key, label in (("operating", "Operating Activities"), ("investing", "Investing Activities"), ("financing", "Financing Activities")):
            rows = []
            section_in = ZERO
            section_out = ZERO
            for particular, values in sorted(grouped[key].items()):
                net = values["cash_in"] - values["cash_out"]
                section_in += values["cash_in"]
                section_out += values["cash_out"]
                rows.append({"particular": particular, "cash_in": _money(values["cash_in"]), "cash_out": _money(values["cash_out"]), "net_amount": _money(net)})
            cash_in += section_in
            cash_out += section_out
            sections[key] = {
                "label": label,
                "rows": rows,
                "cash_in": _money(section_in),
                "cash_out": _money(section_out),
                "net_amount": _money(section_in - section_out),
            }

        net_flow = cash_in - cash_out
        closing = opening + net_flow
        return Response({
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "currency": "SAR",
            "summary": {
                "opening_balance": _money(opening),
                "cash_inflow": _money(cash_in),
                "cash_outflow": _money(cash_out),
                "net_cash_flow": _money(net_flow),
                "closing_balance": _money(closing),
            },
            "sections": sections,
            "totals": {
                "cash_in": _money(cash_in),
                "cash_out": _money(cash_out),
                "net_cash_flow": _money(net_flow),
                "opening_balance": _money(opening),
                "closing_balance": _money(closing),
            },
        })
