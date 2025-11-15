# serializers.py
from rest_framework import serializers
from logistics_app.models import CustomUser
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
import uuid

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'phone_number', 'password', 'confirm_password',
            'pan_number', 'address', 'tds_declaration', 'role'
        ]
        extra_kwargs = {
            'role': {'required': False, 'default': 'vendor'},
            'pan_number': {'required': False},
            'address': {'required': False},
            'tds_declaration': {'required': False},
            'full_name': {'required': True},  # Make it required in serializer
        }

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        phone_number = attrs.get('phone_number')
        full_name = attrs.get('full_name')

        if confirm_password and password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")
        
        if not phone_number:
            raise serializers.ValidationError("Phone number is required.")
        
        if not full_name:
            raise serializers.ValidationError("Full name is required.")
        
        # Check if phone number already exists
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError({"phone_number": "Phone number already exists."})
        
        # Check if PAN number already exists (if provided)
        pan_number = attrs.get('pan_number')
        if pan_number and CustomUser.objects.filter(pan_number=pan_number).exists():
            raise serializers.ValidationError({"pan_number": "PAN number already exists."})
        
        return attrs

    def create(self, validated_data):
        # Generate unique email using phone number + UUID to ensure uniqueness
        phone_last_6 = validated_data['phone_number'][-6:]
        unique_id = uuid.uuid4().hex[:4]
        validated_data['email'] = f"user_{phone_last_6}_{unique_id}@roadfleet.com"
        
        # Set username to None since we're not using it
        validated_data['username'] = None
        
        # Set default role if not provided
        if not validated_data.get('role'):
            validated_data['role'] = 'vendor'

        # Hash password and remove confirm_password
        validated_data['password'] = make_password(validated_data['password'])
        validated_data.pop('confirm_password', None)

        user = CustomUser.objects.create(**validated_data)
        return user

class PhoneNumberTokenObtainPairSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone_number'] = serializers.CharField()
        self.fields['password'] = serializers.CharField(write_only=True)
        
        # Remove the default username field
        del self.fields['username']

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        password = attrs.get('password')

        if not phone_number or not password:
            raise serializers.ValidationError('Both phone number and password are required.')

        # Find user by phone number
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError('Invalid phone number or password.')

        # Check password
        if not user.check_password(password):
            raise serializers.ValidationError('Invalid phone number or password.')

        # For JWT to work, we need to create credentials with username (email)
        credentials = {
            'username': user.email,  # Since USERNAME_FIELD is email
            'password': password
        }

        # Manually authenticate to get the user
        user = authenticate(request=self.context.get('request'), **credentials)
        
        if user is None:
            raise serializers.ValidationError('Authentication failed.')

        # Get the token
        refresh = self.get_token(user)

        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'status': True,
            'message': 'Login successful.',
            'user': {
                'id': user.id,
                'name': user.username,
                'email': user.email,
                'phone_number': user.phone_number,
                'role': user.role,
            }
        }

        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['phone_number'] = user.phone_number
        token['role'] = user.role
        token['name'] = user.username
        return token