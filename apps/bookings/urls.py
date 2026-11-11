from django.urls import path

from .views import (
    BookingCancelView,
    BookingRescheduleView,
    BookingListCreateView,
    BookingStatusView,
    ShopBookingListView,
    SlotListView,
    WaitlistDetailView,
    WaitlistListCreateView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("slots/", SlotListView.as_view(), name="booking-slots"),
    path("shop/", ShopBookingListView.as_view(), name="shop-booking-list"),
    path("waitlist/", WaitlistListCreateView.as_view(), name="waitlist"),
    path("waitlist/<int:pk>/", WaitlistDetailView.as_view(), name="waitlist-detail"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:pk>/reschedule/", BookingRescheduleView.as_view(), name="booking-reschedule"),
    path("<int:pk>/status/", BookingStatusView.as_view(), name="booking-status"),
]
