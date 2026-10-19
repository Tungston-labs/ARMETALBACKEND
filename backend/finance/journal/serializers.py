
# finance/journal_entries/serializers.py

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from .models import JournalEntry, JournalEntryLine


class JournalEntryLineSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(
        source="account.account_name",
        read_only=True,
    )

    account_code = serializers.CharField(
        source="account.account_code",
        read_only=True,
    )

    class Meta:
        model = JournalEntryLine
        fields = [
            "id",
            "account",
            "account_name",
            "account_code",
            "description",
            "debit_amount",
            "credit_amount",
        ]
        read_only_fields = [
            "id",
            "account_name",
            "account_code",
        ]

    def validate(self, attrs):
        debit = attrs.get("debit_amount", Decimal("0.00"))
        credit = attrs.get("credit_amount", Decimal("0.00"))

        if debit < 0 or credit < 0:
            raise serializers.ValidationError(
                "Debit and credit amounts cannot be negative."
            )

        if debit > 0 and credit > 0:
            raise serializers.ValidationError(
                "A line cannot have both debit and credit amounts."
            )

        if debit == 0 and credit == 0:
            raise serializers.ValidationError(
                "Enter either a debit or a credit amount."
            )

        # if not attrs.get("account_name"):
        #     raise serializers.ValidationError(
        #         {"account_name": "Account name is required."}
        #     )

        return attrs


class JournalEntrySerializer(serializers.ModelSerializer):

    lines = JournalEntryLineSerializer(many=True)

    total_debit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    total_credit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    is_balanced = serializers.BooleanField(read_only=True)

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entry_number",
            "entry_date",
            "reference_number",
            "description",
            "source",
            "source_module",
            "source_id",
            "status",
            "lines",
            "total_debit",
            "total_credit",
            "is_balanced",
            "created_by",
            "created_by_name",
            "posted_by",
            "posted_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "entry_number",
            "source",
            "source_module",
            "source_id",
            "status",
            "created_by",
            "posted_by",
            "posted_at",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj):
        user = obj.created_by
        if not user:
            return None

        return (
            user.get_full_name()
            or getattr(user, "username", None)
            or str(user.pk)
        )

    def validate_lines(self, lines):
        if not lines:
            raise serializers.ValidationError(
                "Add at least one journal line."
            )
        return lines

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        entry = JournalEntry.objects.create(**validated_data)

        for line_data in lines_data:
            JournalEntryLine.objects.create(
                journal_entry=entry,
                **line_data,
            )

        return entry

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()

            for line_data in lines_data:
                JournalEntryLine.objects.create(
                    journal_entry=instance,
                    **line_data,
                )

        return instance


class JournalEntryListSerializer(serializers.ModelSerializer):

    total_debit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    total_credit = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )

    is_balanced = serializers.BooleanField(read_only=True)

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = JournalEntry
        fields = [
            "id",
            "entry_number",
            "entry_date",
            "reference_number",
            "description",
            "source",
            "status",
            "total_debit",
            "total_credit",
            "is_balanced",
            "created_by",
            "created_by_name",
            "created_at",
        ]

    def get_created_by_name(self, obj):
        user = obj.created_by
        if not user:
            return None

        return (
            user.get_full_name()
            or getattr(user, "username", None)
            or str(user.pk)
        )