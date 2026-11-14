from rest_framework.permissions import BasePermission


class IsPlatformAdmin(BasePermission):
    """Platforma administratori: role='admin' yoki superuser."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.role == "admin" or u.is_superuser))
    