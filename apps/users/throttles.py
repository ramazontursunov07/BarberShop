from rest_framework.throttling import AnonRateThrottle


class AuthThrottle(AnonRateThrottle):
    """Login va ro'yxatdan o'tish: bitta IP'dan daqiqada cheklangan urinish (parol tanlashdan himoya)."""

    scope = "auth"
