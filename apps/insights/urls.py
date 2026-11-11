from django.urls import path

from .views import DemandView, RiskyBookingsView

urlpatterns = [
    path("demand/", DemandView.as_view(), name="insights-demand"),
    path("risky-bookings/", RiskyBookingsView.as_view(), name="insights-risky"),
]
