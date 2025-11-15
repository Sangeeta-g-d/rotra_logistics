# logistics_app/backends.py
from django.contrib.auth.backends import ModelBackend
from .models import CustomUser

class EmailOrPhoneBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            # Try to find user by email
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return None
        
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None