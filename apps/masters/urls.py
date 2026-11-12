from django.urls import path

from .views import (MasterDayOffDeleteView, MasterDaysOffView, MasterListView, MasterScheduleView,
                    MyMasterDetailView, MyMasterListView)

urlpatterns = [
    path("", MasterListView.as_view(), name="master-list"),
    path("my/", MyMasterListView.as_view(), name="my-master-list"),
    path("my/<int:pk>/", MyMasterDetailView.as_view(), name="my-master-detail"),
    path("<int:pk>/days-off/", MasterDaysOffView.as_view(), name="master-days-off"),
    path("<int:pk>/days-off/<str:day>/", MasterDayOffDeleteView.as_view(), name="master-day-off-delete"),
    path("my/<int:pk>/schedule/", MasterScheduleView.as_view(), name="my-master-schedule"),
]
