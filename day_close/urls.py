from django.urls import path
from .views import DayCloseAPIView
urlpatterns = [path("day-close/", DayCloseAPIView.as_view(), name="day-close")]
