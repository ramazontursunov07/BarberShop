from django.urls import path

from .views import MyReviewListView, ReviewListCreateView

urlpatterns = [
    path("", ReviewListCreateView.as_view(), name="review-list-create"),
    path("my/", MyReviewListView.as_view(), name="my-review-list"),
]
