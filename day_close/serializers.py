from rest_framework import serializers


class DayCloseSerializer(serializers.Serializer):
    store_code = serializers.CharField(max_length=10)
    business_date = serializers.DateField(input_formats=["%Y-%m-%d"])
    machine_card_total = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
