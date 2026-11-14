from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from .health import health

urlpatterns = [
    path("health/", health),
    path("admin/", admin.site.urls),
    path("api/users/", include("apps.users.urls")),
    path('api/shops/', include('apps.shops.urls')),
    path('api/bookings/', include('apps.bookings.urls')),
    path('api/services/', include('apps.services.urls')),
    path('api/masters/', include('apps.masters.urls')),
    path('api/reviews/', include('apps.reviews.urls')),
    path('api/ai/', include('apps.ai.urls')),
    path('api/insights/', include('apps.insights.urls')),
    path('api/promotions/', include('apps.promotions.urls')),
    path('api/products/', include('apps.products.urls')),
    path('api/faq/', include('apps.faq.urls')),
    path('api/admin/', include('apps.adminpanel.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
