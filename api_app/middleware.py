from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

class DisableCSRFOnAPIMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)


class BlockedUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            user = request.user
            if user.is_authenticated and user.is_blocked:
                return JsonResponse(
                    {"detail": "Your account has been blocked"},
                    status=403
                )
        return self.get_response(request)