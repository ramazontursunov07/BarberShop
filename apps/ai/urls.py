from django.urls import path

from .views import ChatView, ReviewInsightsView, SpeakView, TranscribeView, UsageView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="ai-chat"),
    path("review-insights/", ReviewInsightsView.as_view(), name="ai-review-insights"),
    path("transcribe/", TranscribeView.as_view(), name="ai-transcribe"),
    path("speak/", SpeakView.as_view(), name="ai-speak"),
    path("usage/", UsageView.as_view(), name="ai-usage"),
]
