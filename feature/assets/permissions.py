from rest_framework.permissions import BasePermission

from feature.authentication.models import User


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        return User.objects.filter(
            id=user_id,
            role__in=[User.ROLE_ADMIN, User.ROLE_STAFF],
            status=User.STATUS_ACTIVE,
        ).exists()
