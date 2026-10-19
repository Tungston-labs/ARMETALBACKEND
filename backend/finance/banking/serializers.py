
from rest_framework import serializers

from .models import BankAccount, BankTransaction, LoanAccount


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        exclude = ["company"]

    def validate_account_number(self, value):
        request = self.context.get("request")
        company_id = getattr(
            getattr(request, "user", None), "company_id", None
        )

        queryset = BankAccount.objects.filter(
            company_id=company_id,
            account_number=value,
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A bank account with this account number already exists."
            )

        return value


class BankTransactionSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(
        source="bank_account.bank_name",
        read_only=True,
    )

    bank_account_id = serializers.PrimaryKeyRelatedField(
        source="bank_account",
        queryset=BankAccount.objects.none(),
        error_messages={
            "required": "Please select a bank account.",
            "does_not_exist": "The selected bank account does not exist.",
            "incorrect_type": "Invalid bank account ID.",
        },
    )

    class Meta:
        model = BankTransaction
        fields = [
            "id",
            "bank_account_id",
            "bank_name",
            "transaction_date",
            "reference_number",
            "transaction_type",
            "money_in",
            "money_out",
            "balance_after",
            "status",
            "description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

        extra_kwargs = {
            "transaction_date": {
                "error_messages": {
                    "required": "Transaction date is required.",
                    "invalid": "Enter a valid transaction date (YYYY-MM-DD).",
                }
            },
            "reference_number": {
                "error_messages": {
                    "required": "Reference number is required.",
                    "blank": "Reference number cannot be empty.",
                }
            },
            "transaction_type": {
                "error_messages": {
                    "required": "Please select a transaction type.",
                    "invalid_choice": "Please select a valid transaction type.",
                }
            },
            "money_in": {
                "error_messages": {
                    "invalid": "Money in must be a valid amount.",
                    "min_value": "Money in cannot be negative.",
                }
            },
            "money_out": {
                "error_messages": {
                    "invalid": "Money out must be a valid amount.",
                    "min_value": "Money out cannot be negative.",
                }
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            company_id = getattr(request.user, "company_id", None)

            self.fields["bank_account_id"].queryset = (
                BankAccount.objects.filter(company_id=company_id)
            )

    def validate(self, attrs):
        money_in = attrs.get(
            "money_in",
            getattr(self.instance, "money_in", 0),
        )
        money_out = attrs.get(
            "money_out",
            getattr(self.instance, "money_out", 0),
        )

        if money_in > 0 and money_out > 0:
            raise serializers.ValidationError({
                "money_in": (
                    "Enter either Money In or Money Out, not both."
                ),
                "money_out": (
                    "Enter either Money In or Money Out, not both."
                ),
            })

        if money_in == 0 and money_out == 0:
            raise serializers.ValidationError({
                "money_in": (
                    "Enter an amount in either Money In or Money Out."
                ),
                "money_out": (
                    "Enter an amount in either Money In or Money Out."
                ),
            })

        return attrs


class LoanAccountSerializer(serializers.ModelSerializer):
    bank_name = serializers.CharField(
        source="bank_account.bank_name",
        read_only=True,
    )

    bank_account_id = serializers.PrimaryKeyRelatedField(
        source="bank_account",
        queryset=BankAccount.objects.none(),
        error_messages={
            "required": "Please select a bank account.",
            "does_not_exist": "The selected bank account does not exist or is inactive.",
            "incorrect_type": "Invalid bank account ID.",
        },
    )

    bank_account_number = serializers.CharField(
        source="bank_account.account_number",
        read_only=True,
    )

    bank_status = serializers.CharField(
        source="bank_account.status",
        read_only=True,
    )

    class Meta:
        model = LoanAccount
        fields = [
            "id",
            "bank_account_id",
            "bank_name",
            "bank_account_number",
            "bank_status",
            "loan_account_number",
            "loan_type",
            "loan_amount",
            "interest_rate",
            "tenure_months",
            "start_date",
            "next_due_date",
            "monthly_installment",
            "outstanding_balance",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

        extra_kwargs = {
            "loan_account_number": {
                "error_messages": {
                    "required": "Loan account number is required.",
                    "blank": "Loan account number cannot be empty.",
                }
            },
            "loan_type": {
                "error_messages": {
                    "required": "Please select a loan type.",
                    "invalid_choice": "Please select a valid loan type.",
                }
            },
            "loan_amount": {
                "error_messages": {
                    "required": "Loan amount is required.",
                    "invalid": "Enter a valid loan amount.",
                    "min_value": "Loan amount cannot be negative.",
                }
            },
            "interest_rate": {
                "error_messages": {
                    "required": "Interest rate is required.",
                    "invalid": "Enter a valid interest rate.",
                    "min_value": "Interest rate cannot be negative.",
                }
            },
            "tenure_months": {
                "error_messages": {
                    "required": "Loan tenure is required.",
                    "invalid": "Enter a valid tenure in months.",
                    "min_value": "Loan tenure must be greater than zero.",
                }
            },
            "start_date": {
                "error_messages": {
                    "required": "Loan start date is required.",
                    "invalid": "Enter a valid start date (YYYY-MM-DD).",
                }
            },
            "monthly_installment": {
                "error_messages": {
                    "required": "Monthly installment is required.",
                    "invalid": "Enter a valid monthly installment.",
                    "min_value": "Monthly installment cannot be negative.",
                }
            },
            "outstanding_balance": {
                "error_messages": {
                    "required": "Outstanding balance is required.",
                    "invalid": "Enter a valid outstanding balance.",
                    "min_value": "Outstanding balance cannot be negative.",
                }
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request and request.user.is_authenticated:
            company_id = getattr(request.user, "company_id", None)

            self.fields["bank_account_id"].queryset = (
                BankAccount.objects.filter(
                    company_id=company_id,
                    status="active",
                )
            )

    def validate_loan_account_number(self, value):
        bank_account = self.initial_data.get("bank_account_id")

        if bank_account is None:
            return value

        queryset = LoanAccount.objects.filter(
            bank_account_id=bank_account,
            loan_account_number=value,
        )

        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "A loan with this account number already exists for the selected bank account."
            )

        return value

    def validate(self, attrs):
        bank_account = attrs.get(
            "bank_account",
            getattr(self.instance, "bank_account", None),
        )

        if bank_account and bank_account.status != "active":
            raise serializers.ValidationError({
                "bank_account_id": "Please select an active bank account."
            })

        return attrs
