try:  # Celery faqat production'da (worker/beat) kerak; o'rnatilmagan bo'lsa ham loyiha ishlayveradi
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:  # pragma: no cover
    pass
