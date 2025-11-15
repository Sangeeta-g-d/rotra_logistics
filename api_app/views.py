# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegisterSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from logistics_app.models import CustomUser

# views.py
class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Generate tokens for immediate login after registration
            refresh = RefreshToken.for_user(user)
            
            # Build response data
            response_data = {
                'user_id': user.id,
                'name': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'role': user.role,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
            
            # Add TDS declaration URL if it exists
            if user.tds_declaration:
                response_data['tds_declaration'] = request.build_absolute_uri(user.tds_declaration.url)
            else:
                response_data['tds_declaration'] = None
            
            return Response({
                'status': True,
                'message': 'User registered successfully.',
                'data': response_data
            }, status=status.HTTP_201_CREATED)
        return Response({
            'status': False, 
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    def post(self, request):
        phone_number = request.data.get('phone_number')
        password = request.data.get('password')

        if not phone_number or not password:
            return Response(
                {'status': False, 'message': 'Phone number and password are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            return Response(
                {'status': False, 'message': 'Invalid phone number or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.check_password(password):
            return Response(
                {'status': False, 'message': 'Invalid phone number or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        return Response({
            'status': True,
            'message': 'Login successful.',
            'data': {
                'user_id': user.id,
                'name': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'role': user.role,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }
        }, status=status.HTTP_200_OK)