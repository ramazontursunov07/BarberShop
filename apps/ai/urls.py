from django.urls import path

from .views import ChatView, ReviewInsightsView, TranscribeView, UsageView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("review-insights/", ReviewInsightsView.as_view(), name="ai-review-insights"),
    path("transcribe/", TranscribeView.as_view(), name="ai-transcribe"),
    path("usage/", UsageView.as_view(), name="ai-usage"),
]
