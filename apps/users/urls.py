from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView

from .telegram import TelegramAuthView
from .telegram_webapp import TelegramWebAppAuthView, TelegramWebAppLinkView
from .views import MeView,RegisterView


urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    path('login/',TokenObtainPairView.as_view(),name='login'),
    path('token/refresh/',TokenRefreshView.as_view(),name='token-refresh'),
    path('me/',MeView.as_view(),name='me'),
    path('telegram/auth/',TelegramAuthView.as_view(),name='telegram-auth'),
    path('telegram/webapp/',TelegramWebAppAuthView.as_view(),name='telegram-webapp'),
    path('telegram/link/',TelegramWebAppLinkView.as_view(),name='telegram-link'),
]
