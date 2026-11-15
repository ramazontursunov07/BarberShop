from django.urls import path

from .views import NearbyShopsView, ShopListView, ShopDetailView, MyShopListCreateView, MyShopDetailView, ShopPhotoCreateView, ShopPhotoDeleteView

urlpatterns = [
    path("", ShopListView.as_view(), name="shop-list"),
    path("nearby/", NearbyShopsView.as_view(), name="shop-nearby"),
    path("my/", MyShopListCreateView.as_view(), name="my-shop-list"),
    path("my/<int:pk>/", MyShopDetailView.as_view(), name="my-shop-detail"),
    path("photos/", ShopPhotoCreateView.as_view(), name="shop-photo-create"),
    path("photos/<int:pk>/", ShopPhotoDeleteView.as_view(), name="shop-photo-delete"),
    path("<int:pk>/", ShopDetailView.as_view(), name="shop-detail"),
]
