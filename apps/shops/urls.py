from django.urls import path

from .views import ShopListView, ShopDetailView

urlpatterns = [
    path('shop-list/', ShopListView.as_view(), name='shop_list'),
    path('shop-detail/', ShopDetailView.as_view(), name='shop_detail')
]
