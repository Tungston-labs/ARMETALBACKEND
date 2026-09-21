from rest_framework import serializers
from .models import PublicHoliday

class PublicHolidaySerializer(serializers.ModelSerializer):
    holiday_type_display = serializers.SerializerMethodField()

    class Meta:
        model = PublicHoliday
        fields = [
            "id",
            "description",
            "holiday_type",
            "holiday_type_display",
            "date",
            "day",
            "off_day_weekday",
        ]

    def get_holiday_type_display(self, obj):

        if isinstance(obj, dict):
            holiday_type = obj.get("holiday_type")

            return dict(
                PublicHoliday.HOLIDAY_TYPES
            ).get(holiday_type, holiday_type)

        return obj.get_holiday_type_display()