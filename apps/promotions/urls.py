from django.urls import path

from . import views

urlpatterns = [
    path("loyalty/", views.LoyaltyStatusView.as_view(), name="loyalty-status"),
    path("offers/", views.PublicPromoListView.as_view(), name="promo-offers"),
    path("quote/", views.QuoteView.as_view(), name="promo-quote"),
    path("certificates/check/", views.CertificateCheckView.as_view(), name="certificate-check"),
    path("my/promo-codes/", views.MyPromoCodeListCreateView.as_view(), name="my-promo-list"),
    path("my/promo-codes/<int:pk>/", views.MyPromoCodeDetailView.as_view(), name="my-promo-detail"),
    path("my/certificates/", views.MyCertificateListCreateView.as_view(), name="my-certificate-list"),
    path("my/certificates/<int:pk>/", views.MyCertificateDetailView.as_view(), name="my-certificate-detail"),
    path("my/loyalty/", views.MyLoyaltyView.as_view(), name="my-loyalty"),
]
