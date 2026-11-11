from django.urls import path

from .views import DemandView, HairstyleView, RiskyBookingsView

urlpatterns = [
    path("demand/", DemandView.as_view(), name="insights-demand"),
    path("hairstyle/", HairstyleView.as_view(), name="insights-hairstyle"),
    path("risky-bookings/", RiskyBookingsView.as_view(), name="insights-risky"),
]
