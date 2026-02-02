from rest_framework.permissions import BasePermission

class IsPolicyAdmin(BasePermission):
    """
    Custom permission to only allow users with 'policy_admin' role to access certain views.
    """
    def has_permission(self, request, view):
        return (request.user and 
                request.user.is_authenticated and 
                hasattr(request.user, 'role') and 
                request.user.role == 'policy_admin' and 
                request.user.is_active and 
                request.method in ['GET']) 