from rest_framework.permissions import BasePermission

class IsPolicyAdmin(BasePermission):
    """
    Allow governance admin access for platform admins.
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return getattr(user, "role", None) == "admin"
