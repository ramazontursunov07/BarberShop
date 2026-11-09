from django.urls import path

from .views import MyServiceDetailView, MyServiceListCreateView, ServiceListView

urlpatterns = [
    path("", ServiceListView.as_view(), name="service-list"),
    path("my/", MyServiceListCreateView.as_view(), name="my-service-list"),
    path("my/<int:pk>/", MyServiceDetailView.as_view(), name="my-service-detail"),
]
