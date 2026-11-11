from django.urls import path

from .views import FAQListView, MyFAQDetailView, MyFAQListCreateView

urlpatterns = [
    path("", FAQListView.as_view(), name="faq-list"),
    path("my/", MyFAQListCreateView.as_view(), name="my-faq-list"),
    path("my/<int:pk>/", MyFAQDetailView.as_view(), name="my-faq-detail"),
]
