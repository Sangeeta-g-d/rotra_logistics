# serializers.py
from rest_framework import serializers
from logistics_app.models import CustomUser
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
import uuid
from logistics_app.models import VehicleType, Vehicle, Driver, Load, LoadRequest, TripComment, HoldingCharge
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import password_validation


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'email', 'phone_number', 'password', 'confirm_password',
            'pan_number', 'vehicle_number', 'address', 'tds_declaration', 'role'
        ]
        extra_kwargs = {
            'role': {'required': False, 'default': 'vendor'},
            'email': {'required': False},
            'pan_number': {'required': False},
            'vehicle_number': {'required': False},
            'address': {'required': False},
            'tds_declaration': {'required': False},
            'full_name': {'required': True},
        }

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        phone_number = attrs.get('phone_number')
        full_name = attrs.get('full_name')
        email = attrs.get('email')
        pan_number = attrs.get('pan_number')
        vehicle_number = attrs.get('vehicle_number')

        # Validate password and confirm password
        if confirm_password and password != confirm_password:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        # Validate required fields
        if not phone_number:
            raise serializers.ValidationError({"phone_number": "Phone number is required."})
        
        if not full_name:
            raise serializers.ValidationError({"full_name": "Full name is required."})
        
        # Validate password length
        if not password or len(password) < 6:
            raise serializers.ValidationError({"password": "Password must be at least 6 characters long."})
        
        # Check if phone number already exists
        if CustomUser.objects.filter(phone_number=phone_number).exists():
            raise serializers.ValidationError({"phone_number": "Phone number already exists."})
        
        # Check if email already exists (if provided)
        if email and email.strip():
            if CustomUser.objects.filter(email=email).exists():
                raise serializers.ValidationError({"email": "Email already exists."})
        
        # Check if PAN number already exists (if provided)
        if pan_number and pan_number.strip():
            # Validate PAN number format (10 alphanumeric characters)
            if len(pan_number) != 10:
                raise serializers.ValidationError({"pan_number": "PAN number must be 10 characters long."})
            if CustomUser.objects.filter(pan_number=pan_number).exists():
                raise serializers.ValidationError({"pan_number": "PAN number already exists."})
        
        # Check if vehicle number already exists (if provided)
        if vehicle_number and vehicle_number.strip():
            if CustomUser.objects.filter(vehicle_number=vehicle_number).exists():
                raise serializers.ValidationError({"vehicle_number": "Vehicle number already exists."})
        
        return attrs

    def create(self, validated_data):
        email = validated_data.get('email')
        
        # If email is provided and valid, use it; otherwise generate one
        if email and email.strip():
            validated_data['email'] = email.lower()
        else:
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

class PhoneNumberTokenObtainPairSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        password = attrs.get("password")

        if not phone_number or not password:
            raise serializers.ValidationError("Phone number and password are required.")

        # Check if user exists
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("Invalid phone number or password.")

        # Validate password
        if not user.check_password(password):
            raise serializers.ValidationError("Invalid phone number or password.")

        # Create tokens
        refresh = RefreshToken.for_user(user)

        return {
            "status": True,
            "message": "Login successful.",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone_number": user.phone_number,
                "role": user.role,
            }
        }
    
class VehicleTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleType
        fields = ['id', 'name']



# serializers.py
class DriverSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)

    class Meta:
        model = Driver
        fields = [
            "id",
            "full_name",
            "phone_number",
            "owner",
            "owner_name",
            "pan_document",
            "aadhar_document",
            "rc_document",
            "profile_photo",
            "status",
            "is_active",
            "created_at",

            # stats
            "total_trips",
            "completed_trips",
            "pending_trips",
        ]
        read_only_fields = ["id", "owner", "created_at"]



class LoadDetailsSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    created_by_phone = serializers.CharField(source="created_by.phone_number", read_only=True)
    vehicle_type_name = serializers.CharField(source="vehicle_type.name", read_only=True)

    commission = serializers.DecimalField(max_digits=12, decimal_places=2, source="price_per_unit", read_only=True)

    # 👇 Add this
    request_status = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "id",
            "load_id",
            "created_by_name",
            "created_by_phone",
            "vehicle_type_name",
            "pickup_location",
            "drop_location",
            "pickup_date",
            "drop_date",
            "time",
            "weight",
            "price_per_unit",
            "trip_status",
            "commission",
            "notes",
            "request_status",   # 👈 added here
            "created_at",
        ]

    # 👇 This method fetches vendor's request status
    def get_request_status(self, obj):
        vendor = self.context.get("vendor")  # coming from the view

        if not vendor:
            return None

        req = obj.requests.filter(vendor=vendor).first()
        if req:
            return req.status  # pending / accepted / rejected

        return None


class LoadRequestSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.full_name', read_only=True)
    vendor_phone = serializers.CharField(source='vendor.phone_number', read_only=True)

    class Meta:
        model = LoadRequest
        fields = ['id', 'load', 'vendor', 'vendor_name', 'vendor_phone', 'message', 'status', 'created_at']
        read_only_fields = ['id', 'vendor', 'status', 'created_at']

class VehicleSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    owner_phone = serializers.CharField(source="owner.phone_number", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "reg_no",
            "type",
            "load_capacity",
            "insurance_doc",
            "rc_doc",
            "location",
            "status",
            "created_at",
            "owner_name",
            "owner_phone",
        ]

class TripCommentSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)

    class Meta:
        model = TripComment
        fields = [
            'id', 'load', 'sender', 'sender_name',
            'sender_type', 'comment', 'created_at', 'is_read'
        ]
        read_only_fields = ['sender', 'sender_type', 'created_at', 'is_read']

class HoldingChargeSerializer(serializers.ModelSerializer):
    added_by_name = serializers.CharField(source='added_by.full_name', read_only=True)

    class Meta:
        model = HoldingCharge
        fields = [
            'id', 'amount', 'trip_stage', 'reason', 
            'added_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

class VendorAcceptedLoadDetailsSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    creator_phone = serializers.SerializerMethodField()
    vehicle_number = serializers.SerializerMethodField()
    vehicle_type = serializers.SerializerMethodField()
    request_status = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "id",
            "pickup_location",
            "drop_location",
            "weight",
            "price_per_unit",
            "created_by",
            "creator_phone",
            "vehicle_number",
            "vehicle_type",
            "request_status",
            "created_at",
        ]

    def get_created_by(self, obj):
        return obj.created_by.full_name if obj.created_by else None

    def get_creator_phone(self, obj):
        return obj.created_by.phone_number if obj.created_by else None

    def get_vehicle_number(self, obj):
        return obj.vehicle.reg_no if obj.vehicle else None

    def get_vehicle_type(self, obj):
        return obj.vehicle_type.name if obj.vehicle_type else None

    def get_request_status(self, obj):
        vendor = self.context.get("vendor")
        req = obj.requests.filter(vendor=vendor).first()
        return req.status if req else None
    
class VendorTripDetailsSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    created_by_phone = serializers.CharField(source="created_by.phone_number", read_only=True)

    vehicle_number = serializers.SerializerMethodField()
    vehicle_type = serializers.SerializerMethodField()

    driver_name = serializers.CharField(source="driver.full_name", read_only=True)
    driver_phone = serializers.CharField(source="driver.phone_number", read_only=True)

    documents = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    
    # Add this field to get last 2 comments
    recent_comments = serializers.SerializerMethodField()
    
    # Add holding charges field
    holding_charges = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "id",
            "load_id",

            "pickup_location",
            "drop_location",
            "pickup_date",
            "time",
            "weight",
            "price_per_unit",

            "trip_status",
            "status",

            # creator
            "created_by_name",
            "created_by_phone",

            # vehicle
            "vehicle_number",
            "vehicle_type",

            # driver
            "driver_name",
            "driver_phone",

            # attachments
            "documents",

            # timeline
            "timeline",

            # recent comments (last 2)
            "recent_comments",
            
            # holding charges
            "holding_charges",

            "created_at",
        ]

    def get_vehicle_number(self, obj):
        return obj.vehicle.reg_no if obj.vehicle else None

    def get_vehicle_type(self, obj):
        return obj.vehicle_type.name if obj.vehicle_type else None

    def get_documents(self, obj):
        return {
            "lr_document": obj.lr_document.url if obj.lr_document else None,
            "pod_document": obj.pod_document.url if obj.pod_document else None,
        }

    def get_timeline(self, obj):
        return {
            "trip_requested": obj.created_at,
            "loaded": obj.loaded_at,
            "lr_uploaded": obj.lr_uploaded_at,
            "in_transit": obj.in_transit_at,
            "unloading": obj.unloading_at,
            "pod_uploaded": obj.pod_uploaded_at,
            "payment_completed": obj.payment_completed_at,
        }
    
    # Add this method to get last 2 comments
    def get_recent_comments(self, obj):
        # Get the last 2 comments for this load, ordered by latest first
        recent_comments = TripComment.objects.filter(
            load=obj
        ).order_by('-created_at')[:2]  # Get last 2 comments
        
        # Serialize the comments
        serializer = TripCommentSerializer(recent_comments, many=True)
        return serializer.data
    
    def get_holding_charges(self, obj):
        """Get all holding charges for this load as a list"""
        holding_charges = obj.holding_charge_entries.all().order_by('-created_at')
        serializer = HoldingChargeSerializer(holding_charges, many=True)
        return serializer.data
    

class LRUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Load
        fields = ["lr_document"]


class PODUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Load
        fields = ["pod_document"]


class VendorProfileUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, allow_blank=False)
    profile_image = serializers.ImageField(required=False)

    old_password = serializers.CharField(required=False, write_only=True, allow_blank=False)
    new_password = serializers.CharField(required=False, write_only=True, allow_blank=False)

    def validate(self, data):
        user = self.context["request"].user

        # If password is being changed
        if data.get("new_password"):
            if not data.get("old_password"):
                raise serializers.ValidationError({"old_password": "Old password is required to change password."})
            if not user.check_password(data["old_password"]):
                raise serializers.ValidationError({"old_password": "Incorrect old password."})
            # Validate new password strength
            if len(data.get("new_password", "")) < 6:
                raise serializers.ValidationError({"new_password": "New password must be at least 6 characters long."})

        return data

    def save(self):
        user = self.context["request"].user

        # Update name
        if self.validated_data.get("full_name"):
            user.full_name = self.validated_data["full_name"]

        # Update profile image
        if self.validated_data.get("profile_image"):
            user.profile_image = self.validated_data["profile_image"]

        # Update password
        if self.validated_data.get("new_password"):
            user.set_password(self.validated_data["new_password"])

        user.save()
        return user

class LoadFilterOptionsSerializer(serializers.Serializer):
    locations = serializers.ListField(child=serializers.CharField())
    destinations = serializers.ListField(child=serializers.CharField())
    vehicle_types = serializers.ListField(child=serializers.CharField())
    load_capacities = serializers.ListField(child=serializers.CharField())