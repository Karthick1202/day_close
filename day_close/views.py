from decimal import Decimal
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import DayCloseSerializer
from .services import close_day, DayCloseError


class DayCloseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = DayCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = close_day(
                store_code=serializer.validated_data["store_code"],
                business_date=serializer.validated_data["business_date"],
                machine_card_total=serializer.validated_data["machine_card_total"],
                user=request.user.get_username(),
            )
        except DayCloseError as exc:
            print('==',exc)
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        close = result["day_close"]
        decimal_string = lambda value: format(value, ".2f")
        return Response({
            "message": "Day closed successfully",
            "store_code": close.store.store_code,
            "business_date": close.business_date.isoformat(),
            "tender_totals": {k: decimal_string(v) for k, v in result["tender_totals"].items()},
            "sales_inclusive_gst": decimal_string(result["sales_inclusive_gst"]),
            "sales_excluding_gst": decimal_string(result["sales_excluding_gst"]),
            "gst": decimal_string(result["gst"]),
            "variance": decimal_string(result["variance"]),
            "loyalty_points_awarded": result["loyalty_points_awarded"],
            "finance_rows": {k: decimal_string(v) for k, v in result["finance_rows"].items()},
        }, status=status.HTTP_201_CREATED)

