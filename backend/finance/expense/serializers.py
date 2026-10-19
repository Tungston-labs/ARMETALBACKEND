
from rest_framework import serializers

from .models import Expense
from finance.banking.models import BankAccount


class ExpenseSerializer(serializers.ModelSerializer):

    paid_from_account_id = serializers.PrimaryKeyRelatedField(
        source="paid_from_account",
        queryset=BankAccount.objects.none(),
        required=True,
        error_messages={
            "required": (
                "Please select a bank account in the Paid From Account field."
            ),
            "does_not_exist": (
                "The selected bank account does not exist, is inactive, "
                "or does not belong to your company."
            ),
            "incorrect_type": "Invalid bank account ID.",
            "null": "Please select a valid bank account.",
        },
    )

    paid_from_account_name = serializers.CharField(
        source="paid_from_account.bank_name",
        read_only=True,
    )

    class Meta:
        model = Expense

        fields = [
            "id",
            "expense_id",
            "expense_date",
            "category",
            "paid_to",
            "paid_method",
            "paid_from_account_id",
            "paid_from_account_name",
            "amount",
            "document",
            "status",
            "description",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "expense_id",
            "paid_from_account_name",
            "created_at",
            "updated_at",
        ]

        extra_kwargs = {
            "expense_date": {
                "error_messages": {
                    "required": "Expense date is required.",
                    "invalid": (
                        "Enter a valid expense date in YYYY-MM-DD format."
                    ),
                    "null": "Expense date cannot be empty.",
                }
            },
            "category": {
                "error_messages": {
                    "required": "Please select an expense category.",
                    "invalid_choice": "Please select a valid expense category.",
                    "blank": "Expense category cannot be empty.",
                }
            },
            "paid_to": {
                "error_messages": {
                    "required": "Paid to is required.",
                    "blank": "Paid to cannot be empty.",
                    "null": "Paid to cannot be empty.",
                }
            },
            "paid_method": {
                "error_messages": {
                    "required": "Please select a payment method.",
                    "invalid_choice": "Please select a valid payment method.",
                    "blank": "Payment method cannot be empty.",
                }
            },
            "amount": {
                "error_messages": {
                    "required": "Expense amount is required.",
                    "invalid": "Enter a valid expense amount.",
                    "min_value": "Expense amount must be greater than zero.",
                    "max_digits": "Expense amount has too many digits.",
                    "max_decimal_places": (
                        "Expense amount cannot have more than 2 decimal places."
                    ),
                    "null": "Expense amount is required.",
                }
            },
            "status": {
                "error_messages": {
                    "invalid_choice": (
                        "Please select a valid status: Paid or Unpaid."
                    ),
                    "blank": "Expense status cannot be empty.",
                }
            },
            "document": {
                "error_messages": {
                    "invalid": "Please upload a valid document.",
                }
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")

        if request and request.user.is_authenticated:
            company_id = getattr(request.user, "company_id", None)

            self.fields["paid_from_account_id"].queryset = (
                BankAccount.objects.filter(
                    company_id=company_id,
                    status="active",
                )
            )

    def validate_expense_date(self, value):
        if not value:
            raise serializers.ValidationError(
                "Expense date is required."
            )
        return value

    def validate_category(self, value):
        if not value:
            raise serializers.ValidationError(
                "Please select an expense category."
            )
        return value

    def validate_paid_to(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError(
                "Please enter the person, employee, or vendor paid."
            )
        return value.strip()

    def validate_paid_method(self, value):
        if not value:
            raise serializers.ValidationError(
                "Please select a payment method."
            )
        return value

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Expense amount must be greater than zero."
            )
        return value

    def validate_document(self, value):
        if value:
            max_size = 5 * 1024 * 1024  # 5 MB

            if value.size > max_size:
                raise serializers.ValidationError(
                    "Document size cannot exceed 5 MB."
                )

            allowed_extensions = (
                ".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx"
            )

            filename = value.name.lower()

            if not filename.endswith(allowed_extensions):
                raise serializers.ValidationError(
                    "Unsupported document format. "
                    "Upload PDF, JPG, JPEG, PNG, DOC, or DOCX."
                )

        return value

    def validate(self, attrs):
        bank_account = attrs.get(
            "paid_from_account",
            getattr(self.instance, "paid_from_account", None),
        )

        request = self.context.get("request")

        if bank_account and request and request.user.is_authenticated:
            company_id = getattr(request.user, "company_id", None)

            if bank_account.company_id != company_id:
                raise serializers.ValidationError({
                    "paid_from_account_id": (
                        "The selected bank account does not belong "
                        "to your company."
                    )
                })

            if bank_account.status != "active":
                raise serializers.ValidationError({
                    "paid_from_account_id": (
                        "Please select an active bank account."
                    )
                })

        return attrs
