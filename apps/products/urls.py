from django.urls import path

from . import views

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product-list"),
    path("my/", views.MyProductListCreateView.as_view(), name="my-product-list"),
    path("my/<int:pk>/", views.MyProductDetailView.as_view(), name="my-product-detail"),
    path("reservations/", views.ReservationListCreateView.as_view(), name="reservation-list"),
    path("reservations/<int:pk>/cancel/", views.ReservationCancelView.as_view(), name="reservation-cancel"),
    path("reservations/shop/", views.ShopReservationListView.as_view(), name="shop-reservation-list"),
    path("reservations/<int:pk>/status/", views.ReservationStatusView.as_view(), name="reservation-status"),
]
