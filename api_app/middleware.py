from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from rest_framework_simplejwt.authentication import JWTAuthentication

class DisableCSRFOnAPIMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)


class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            # First, check Django-authenticated user (session)
            user = getattr(request, 'user', None)
            if user and getattr(user, 'is_authenticated', False) and getattr(user, 'is_blocked', False):
                return JsonResponse({"detail": "Your account has been blocked"}, status=403)

            # Next, if request uses JWT (Authorization: Bearer <token>), attempt to authenticate and check `is_blocked`
            try:
                auth_result = JWTAuthentication().authenticate(request)
                if auth_result:
                    jwt_user, validated_token = auth_result
                    if getattr(jwt_user, 'is_blocked', False):
                        return JsonResponse({"detail": "Your account has been blocked"}, status=403)
            except Exception:
                # If JWT auth fails, let downstream views/permissions handle it
                pass
        return self.get_response(request)