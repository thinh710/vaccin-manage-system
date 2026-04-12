from rest_framework.permissions import BasePermission, SAFE_METHODS

from feature.authentication.models import User


class IsAdminOnly(BasePermission):
    """Tat ca thao tac tren resource nay danh cho Admin va Bac si."""

    def has_permission(self, request, view):
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        try:
            user = User.objects.get(id=user_id, status=User.STATUS_ACTIVE)
        except User.DoesNotExist:
            return False

        return user.role in (User.ROLE_ADMIN, User.ROLE_DOCTOR)


class CanReadVaccineStock(BasePermission):
    """Admin va bac si toan quyen; staff chi duoc xem ton kho vaccine."""

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

        return user.role in (User.ROLE_ADMIN, User.ROLE_DOCTOR)


IsAdminOrReadOnly = IsAdminOnly
