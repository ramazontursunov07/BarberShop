from django.urls import path

from .views import (AdminMasterDetailView, AdminShopDetailView, AdminShopListCreateView, AdminShopMastersView,
                    AdminStatsView, AdminUserDetailView, AdminUserListView)

urlpatterns = [
    path("stats/", AdminStatsView.as_view(), name="admin-stats"),
    path("shops/", AdminShopListCreateView.as_view(), name="admin-shops"),
    path("shops/<int:pk>/", AdminShopDetailView.as_view(), name="admin-shop-detail"),
    path("shops/<int:pk>/masters/", AdminShopMastersView.as_view(), name="admin-shop-masters"),
    path("masters/<int:pk>/", AdminMasterDetailView.as_view(), name="admin-master-detail"),
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
]
