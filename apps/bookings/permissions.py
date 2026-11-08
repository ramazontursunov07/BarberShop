from rest_framework.permissions import BasePermission


class IsOwnerOrMaster(BasePermission):
    """Sartaroshxona egasi yoki usta (mijoz emas)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('owner', 'master')
