from rest_framework.permissions import BasePermission

class IsNotBlocked(BasePermission):
    message = "Your account has been blocked. Please contact support."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return True  # Allow unauthenticated APIs like login / OTP

        return not user.is_blocked
