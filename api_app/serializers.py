# serializers.py
from rest_framework import serializers
from logistics_app.models import CustomUser, PhoneOTP, TDSRate
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
import uuid
from logistics_app.models import VehicleType, Vehicle, Driver, Load, LoadRequest, TripComment, HoldingCharge
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import password_validation
from decimal import Decimal
import pytz
from django.utils import timezone

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    # Profile image
    profile_image = serializers.ImageField(required=False, allow_null=True)
    # Vehicle fields for optional vehicle creation during registration
    reg_no = serializers.CharField(required=False, allow_blank=True)
    type = serializers.CharField(required=False, allow_blank=True)
    load_capacity = serializers.DecimalField(required=False, max_digits=5, decimal_places=2)
    insurance_doc = serializers.FileField(required=False, allow_null=True)
    rc_doc = serializers.FileField(required=False, allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            'full_name', 'email', 'phone_number', 'password', 'confirm_password',
            'pan_number', 'address', 'tds_declaration', 'profile_image', 'role',
            # vehicle fields
            'reg_no', 'type', 'load_capacity', 'insurance_doc', 'rc_doc','acc_no','ifsc_code'
        ]
        extra_kwargs = {
            'role': {'required': False, 'default': 'vendor'},
            'email': {'required': False},
            'pan_number': {'required': False},
            'address': {'required': False},
            'tds_declaration': {'required': False},
            'profile_image': {'required': False},
            'full_name': {'required': True},
        }

    def validate(self, attrs):
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')
        phone_number = attrs.get('phone_number')
        full_name = attrs.get('full_name')
        email = attrs.get('email')
        pan_number = attrs.get('pan_number')
        reg_no = attrs.get('reg_no')

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
            # PAN number is optional, but if provided, it should be unique
            # No strict length validation - allow any format
            if CustomUser.objects.filter(pan_number=pan_number).exists():
                raise serializers.ValidationError({"pan_number": "PAN number already exists."})

        # Validate vehicle reg_no uniqueness if provided
        if reg_no and reg_no.strip():
            from logistics_app.models import Vehicle
            if Vehicle.objects.filter(reg_no__iexact=reg_no.strip()).exists():
                raise serializers.ValidationError({"reg_no": "Vehicle with this registration number already exists."})
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

        # Extract vehicle fields if present
        reg_no = validated_data.pop('reg_no', None)
        vehicle_type = validated_data.pop('type', None)
        load_capacity = validated_data.pop('load_capacity', None)
        insurance_doc = validated_data.pop('insurance_doc', None)
        rc_doc = validated_data.pop('rc_doc', None)

        user = CustomUser.objects.create(**validated_data)

        # If vehicle registration provided, create Vehicle instance
        if reg_no and reg_no.strip():
            from logistics_app.models import Vehicle
            vehicle = Vehicle.objects.create(
                reg_no=reg_no.strip(),
                owner=user,
                type=(vehicle_type or ''),
                load_capacity=load_capacity or None,
            )
            # Attach files if provided
            if insurance_doc:
                vehicle.insurance_doc = insurance_doc
            if rc_doc:
                vehicle.rc_doc = rc_doc
            vehicle.save()

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
    apply_tds = serializers.BooleanField()
    tds_percentage = serializers.SerializerMethodField()
    tds_amount = serializers.SerializerMethodField()
    net_amount_after_tds = serializers.SerializerMethodField()
    commission = serializers.DecimalField(max_digits=12, decimal_places=2, source="price_per_unit", read_only=True)

    # 👇 Add this
    request_status = serializers.SerializerMethodField()

    class Meta:
        model = Load
        fields = [
            "id",
            "load_id",
            "created_by_name",
            'apply_tds', 'tds_percentage', 'tds_amount', 
            'net_amount_after_tds',
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

    def get_tds_percentage(self, obj):
        """Get TDS percentage for this load"""
        # Get default TDS percentage from context or use 2%
        default_tds_percentage = self.context.get('default_tds_percentage', Decimal('2.00'))
        
        # Return default percentage if apply_tds is True, otherwise 0
        return float(default_tds_percentage) if obj.apply_tds else 0.0
    
    def get_tds_amount(self, obj):
        """Calculate TDS amount for this load"""
        if not obj.apply_tds:
            return 0.00
        
        # Get TDS percentage
        tds_percentage = self.get_tds_percentage(obj)
        
        # Calculate TDS amount from final_payment
        final_payment = obj.final_payment or Decimal('0.00')
        tds_amount = (final_payment * Decimal(tds_percentage) / Decimal('100')).quantize(Decimal('0.01'))
        
        return float(tds_amount)
    
    def get_net_amount_after_tds(self, obj):
        """Calculate net amount after deducting TDS"""
        if not obj.apply_tds:
            return float(obj.final_payment or Decimal('0.00'))
        
        final_payment = obj.final_payment or Decimal('0.00')
        tds_amount = Decimal(str(self.get_tds_amount(obj)))
        net_amount = (final_payment - tds_amount).quantize(Decimal('0.01'))
        
        return float(net_amount)

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

    # ✅ ADD THIS
    to_location = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True
    )

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
            "to_location",   # ✅ include here
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
    recent_comments = serializers.SerializerMethodField()
    holding_charges = serializers.SerializerMethodField()

    first_half_payment = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    second_half_payment = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_holding_charges = serializers.SerializerMethodField()
    total_trip_amount = serializers.SerializerMethodField()

    hold_reason = serializers.SerializerMethodField()
    before_payment_amount = serializers.SerializerMethodField()
    confirmed_paid_amount = serializers.SerializerMethodField()

    # ✅ NEW FIELDS
    apply_tds = serializers.BooleanField(read_only=True)
    tds_percentage = serializers.SerializerMethodField()
    pod_received_at = serializers.SerializerMethodField()

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

            # payments
            "first_half_payment",
            "second_half_payment",
            "total_holding_charges",
            "total_trip_amount",
            'hold_reason',

            # ✅ TDS
            "apply_tds",
            "tds_percentage",

            # tracking
            "current_location",
            "trip_status",
            "status",
            "pod_received_at",

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

            # comments
            "recent_comments",

            # holding charges
            "holding_charges",


            # payment adjustment
            "before_payment_amount",
            "confirmed_paid_amount",

            "created_at",
        ]

    def get_tds_percentage(self, obj):
        """
        If apply_tds is true → fetch value from TDSRate table
        If false → return default 2%
        """
        DEFAULT_TDS = 2.00
    
        if not obj.apply_tds:
            return DEFAULT_TDS
    
        tds = TDSRate.objects.first()
        return float(tds.rate) if tds else DEFAULT_TDS
    
    def get_pod_received_at(self, obj):
        if not obj.pod_received_at:
            return None

        ist = pytz.timezone("Asia/Kolkata")

        # Ensure datetime is timezone-aware
        dt = obj.pod_received_at
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.utc)

        dt_ist = dt.astimezone(ist)

        return dt_ist.strftime("%d %b %Y, %I:%M %p")
    
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
    
    def get_total_holding_charges(self, obj):
        """Calculate and return total holding charges"""
        return obj.get_total_holding_charges()
    
    def get_total_trip_amount(self, obj):
        """Calculate and return total trip amount (freight + holding charges)"""
        return obj.total_trip_amount
    
    def get_hold_reason(self, obj):
        """Return hold reason if trip status is 'hold', otherwise None"""
        if obj.trip_status == 'balance_hold':
            return obj.hold_reason
        return None
    
    def get_before_payment_amount(self, obj):
        """Return the amount that was expected before any manual adjustment."""
        # If explicitly set, use it; otherwise default to second half or final payment
        if getattr(obj, 'before_payment_amount', None) is not None and obj.before_payment_amount != 0:
            return obj.before_payment_amount
        # prefer second half if available
        if getattr(obj, 'second_half_payment', None):
            return obj.second_half_payment
        return obj.final_payment

    def get_confirmed_paid_amount(self, obj):
        """Return the confirmed paid amount if present, otherwise None."""
        return obj.confirmed_paid_amount if getattr(obj, 'confirmed_paid_amount', None) is not None else None
    

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
    tds_declaration = serializers.FileField(required=False)
    bank_cheque = serializers.FileField(required=False)
    aadhaar_card = serializers.FileField(required=False)
    pan_card = serializers.FileField(required=False)

    # 🔹 New fields
    pan_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    acc_no = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    ifsc_code = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    old_password = serializers.CharField(required=False, write_only=True, allow_blank=False)
    new_password = serializers.CharField(required=False, write_only=True, allow_blank=False)

    alternate_no = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True
    )

    def validate(self, data):
        user = self.context["request"].user

        # ✅ alternate_no uniqueness check
        alternate_no = data.get("alternate_no")
        if alternate_no:
            if CustomUser.objects.filter(alternate_no=alternate_no).exclude(id=user.id).exists():
                raise serializers.ValidationError({
                    "alternate_no": "This alternate number is already in use."
                })

        # ✅ PAN uniqueness check
        pan_number = data.get("pan_number")
        if pan_number:
            if CustomUser.objects.filter(pan_number=pan_number).exclude(id=user.id).exists():
                raise serializers.ValidationError({
                    "pan_number": "This PAN number is already in use."
                })

        # ✅ Password validation
        if data.get("new_password"):
            if not data.get("old_password"):
                raise serializers.ValidationError({
                    "old_password": "Old password is required to change password."
                })
            if not user.check_password(data["old_password"]):
                raise serializers.ValidationError({
                    "old_password": "Incorrect old password."
                })
            if len(data["new_password"]) < 6:
                raise serializers.ValidationError({
                    "new_password": "New password must be at least 6 characters long."
                })

        return data

    def save(self):
        user = self.context["request"].user
        data = self.validated_data

        # 🔹 Basic fields
        if data.get("full_name"):
            user.full_name = data["full_name"]

        if "alternate_no" in data:
            user.alternate_no = data.get("alternate_no")

            # 🔹 New docs
        if data.get("bank_cheque"):
            user.bank_cheque = data["bank_cheque"]

        if data.get("pan_card"):
            user.pan_card = data["pan_card"]
    
        if data.get("aadhaar_card"):
            user.aadhaar_card = data["aadhaar_card"]

        if data.get("profile_image"):
            user.profile_image = data["profile_image"]

        if data.get("tds_declaration"):
            user.tds_declaration = data["tds_declaration"]

        # 🔹 Banking & PAN
        if "pan_number" in data:
            user.pan_number = data.get("pan_number")

        if "acc_no" in data:
            user.acc_no = data.get("acc_no")

        if "ifsc_code" in data:
            user.ifsc_code = data.get("ifsc_code")

        # 🔹 Password
        if data.get("new_password"):
            user.set_password(data["new_password"])

        user.save()
        return user



class LoadFilterOptionsSerializer(serializers.Serializer):
    locations = serializers.ListField(child=serializers.CharField())
    destinations = serializers.ListField(child=serializers.CharField())
    vehicle_types = serializers.ListField(child=serializers.CharField())
    load_capacities = serializers.ListField(child=serializers.CharField())


# forgot password serializer
class ForgotPasswordRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

    def validate_phone_number(self, value):
        # Check if user exists with this phone number
        if not CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No account found with this phone number.")
        return value


class VerifyOTPForgotPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        phone_number = data.get('phone_number')
        otp = data.get('otp')

        # Check if OTP exists and is valid
        try:
            otp_record = PhoneOTP.objects.filter(
                phone_number=phone_number,
                otp=otp,
                purpose='forgot_password',
                is_verified=False
            ).latest('created_at')
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        # Check if OTP is expired
        if otp_record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please request a new one.")

        return data


class ResetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        # Check if passwords match
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        
        # Verify OTP
        phone_number = data.get('phone_number')
        otp = data.get('otp')

        try:
            otp_record = PhoneOTP.objects.filter(
                phone_number=phone_number,
                otp=otp,
                purpose='forgot_password',
                is_verified=False
            ).latest('created_at')
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP.")

        if otp_record.is_expired():
            raise serializers.ValidationError("OTP has expired. Please request a new one.")

        # Check if user exists
        try:
            user = CustomUser.objects.get(phone_number=phone_number)
            data['user'] = user
            data['otp_record'] = otp_record
        except CustomUser.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        return data