from django.urls import path

from .views import (ClientDetailView, ClientsView, DemandView, HairstyleView, PayrollView, RiskyBookingsView,
                    StatsView)

urlpatterns = [
    path("demand/", DemandView.as_view(), name="insights-demand"),
    path("hairstyle/", HairstyleView.as_view(), name="insights-hairstyle"),
    path("stats/", StatsView.as_view(), name="insights-stats"),
    path("clients/", ClientsView.as_view(), name="insights-clients"),
    path("clients/<int:client_id>/", ClientDetailView.as_view(), name="insights-client-detail"),
    path("payroll/", PayrollView.as_view(), name="insights-payroll"),
    path("risky-bookings/", RiskyBookingsView.as_view(), name="insights-risky"),
]
