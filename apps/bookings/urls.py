from django.urls import path

from .views import (
    BookingCancelView,
    BookingListCreateView,
    BookingStatusView,
    ShopBookingListView,
    SlotListView,
)

urlpatterns = [
    path("", BookingListCreateView.as_view(), name="booking-list-create"),
    path("slots/", SlotListView.as_view(), name="booking-slots"),
    path("shop/", ShopBookingListView.as_view(), name="shop-booking-list"),
    path("<int:pk>/cancel/", BookingCancelView.as_view(), name="booking-cancel"),
    path("<int:pk>/status/", BookingStatusView.as_view(), name="booking-status"),
]
