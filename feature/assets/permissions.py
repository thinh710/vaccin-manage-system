from rest_framework.permissions import BasePermission, SAFE_METHODS

from feature.authentication.models import User


class IsAdminOnly(BasePermission):
    """Tat ca thao tac tren resource nay chi danh cho Admin."""

    def has_permission(self, request, view):
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        try:
            user = User.objects.get(id=user_id, status=User.STATUS_ACTIVE)
        except User.DoesNotExist:
            return False

        return user.role == User.ROLE_ADMIN


class CanReadVaccineStock(BasePermission):
    """Admin toan quyen; staff/doctor chi duoc xem ton kho vaccine."""

    def has_permission(self, request, view):
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        try:
            user = User.objects.get(id=user_id, status=User.STATUS_ACTIVE)
        except User.DoesNotExist:
            return False

        if request.method in SAFE_METHODS:
            return user.role in (User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_DOCTOR)

        return user.role == User.ROLE_ADMIN


IsAdminOrReadOnly = IsAdminOnly
