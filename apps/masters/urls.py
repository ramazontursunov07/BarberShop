from django.urls import path

from .views import MasterListView, MasterScheduleView, MyMasterDetailView, MyMasterListView

urlpatterns = [
    path("", MasterListView.as_view(), name="master-list"),
    path("my/", MyMasterListView.as_view(), name="my-master-list"),
    path("my/<int:pk>/", MyMasterDetailView.as_view(), name="my-master-detail"),
    path("my/<int:pk>/schedule/", MasterScheduleView.as_view(), name="my-master-schedule"),
]
