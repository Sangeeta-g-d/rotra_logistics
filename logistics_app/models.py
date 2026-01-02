# models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import re
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.conf import settings
from datetime import timedelta


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        Create and return a regular user with an email and password.
        """
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        
        # Set username to None if not provided
        if 'username' not in extra_fields:
            extra_fields['username'] = None
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and return a superuser with an email and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    # Role choices
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('traffic_person', 'Traffic Person'),
        ('vendor', 'Vendor'),
        ('user', 'User'),
    ]
    
    # First, let's keep username but make it non-unique and nullable
    username = models.CharField(
        max_length=150,
        unique=False,
        blank=True,
        null=True,
        help_text='Optional. Will be removed in future.'
    )
    
    # Full name field to store the actual name
    full_name = models.CharField(
        max_length=255,
        help_text='Full name of the user'
    )
    
    # Make email required and unique
    email = models.EmailField(unique=True)
    
    # Role field
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='traffic_person',
        help_text='User role in the system'
    )
    
    address = models.TextField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=15, unique=True)
    pan_number = models.CharField(max_length=10, unique=True, blank=True, null=True)
    fcm_token = models.TextField(blank=True, null=True, verbose_name='FCM Token')
    
    # TDS Declaration
    tds_declaration = models.FileField(
        upload_to='tds_documents/',
        blank=True,
        null=True
    )
    
    # Profile Image
    profile_image = models.ImageField(
        upload_to='profile_images/',
        blank=True,
        null=True,
        default='profile_images/default_avatar.png'
    )
    
    # ADD THIS FIELD: Track who created this user
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_employees',
        verbose_name='Created By',
        help_text='Admin who created this user account'
    )
    
    # Use custom manager
    objects = CustomUserManager()
    
    # Use email as the username field for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone_number']  # Remove username from required fields

    def __str__(self):
        return f"{self.full_name} - {self.email} - {self.get_role_display()}"
    
    def is_admin(self):
        return self.role == 'admin' or self.is_staff
    
    def get_full_name(self):
        return self.full_name.strip() or self.email.split('@')[0]
    
    def is_traffic_person(self):
        return self.role == 'traffic_person'
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username', '-date_joined']


class PhoneOTP(models.Model):
    phone_number = models.CharField(max_length=15)
    otp = models.CharField(max_length=6)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return f"{self.phone_number} - {self.otp}"


class Customer(models.Model):
    """Customer table – exactly the fields you requested"""
    customer_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    contact_person_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person_phone = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)          # for deactivate/activate
    profile_image = models.ImageField(upload_to='customers/', blank=True, null=True)

    def __str__(self):
        return self.customer_name
    

class Driver(models.Model):
    """Driver Management Model"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
    ]
    
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, unique=True)
    
    # Owner relationship - only vendors can be owners
    owner = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'vendor'},
        related_name='drivers',
        help_text='Vendor who owns this driver'
    )
    
    # Document uploads
    pan_document = models.FileField(
        upload_to='driver_documents/pan/',
        blank=True,
        null=True,
        verbose_name='PAN Card Document'
    )
    
    aadhar_document = models.FileField(
        upload_to='driver_documents/aadhar/',
        blank=True,
        null=True,
        verbose_name='Aadhar Card Document'
    )
    
    rc_document = models.FileField(
        upload_to='driver_documents/rc/',
        blank=True,
        null=True,
        verbose_name='RC Document'
    )
    
    # Profile photo
    profile_photo = models.ImageField(
        upload_to='driver_photos/',
        blank=True,
        null=True,
        default='driver_photos/default_driver.png'
    )
    
    # Status and metadata
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    is_active = models.BooleanField(default=True)
    
    # Tracking fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_drivers',
        verbose_name='Created By'
    )
    
    # Trip statistics (can be updated via signals or computed)
    total_trips = models.IntegerField(default=0)
    completed_trips = models.IntegerField(default=0)
    pending_trips = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.full_name} - {self.owner.full_name}"
    
    class Meta:
        verbose_name = 'Driver'
        verbose_name_plural = 'Drivers'
        ordering = ['-created_at']

class VehicleType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    

class Vehicle(models.Model):

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    reg_no = models.CharField(max_length=20, unique=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vehicles')

    # Accept ANY text (no fixed choices)
    type = models.CharField(max_length=50)  

    # Load capacity (optional)
    load_capacity = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Optional uploads
    insurance_doc = models.FileField(upload_to='vehicles/insurance/', null=True, blank=True)
    rc_doc = models.FileField(upload_to='vehicles/rc/', null=True, blank=True)

    location = models.CharField(max_length=255, null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reg_no
    
    

class Load(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('assigned', 'Assigned'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    TRIP_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('loaded', 'Reach Loading Point'),
        ('lr_uploaded', 'LR Uploaded'),
        ('in_transit', 'In Transit'),
        ('unloading', 'Reach Unloading Point'),
        ('pod_uploaded', 'POD Uploaded'),
        ('payment_completed', 'Payment Completed'),
        ('hold', 'Hold'),
    ]

    # Basic Info
    load_id = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loads')
    contact_person_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person_phone = models.CharField(max_length=15, blank=True, null=True)
    vehicle_type = models.ForeignKey(VehicleType, on_delete=models.PROTECT, related_name='loads')

    # PRICE/FREIGHT
    price_per_unit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Price Per Unit (Full Freight Amount)"
    )

    # Driver + Vehicle
    driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_loads')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_loads')
    assigned_at = models.DateTimeField(null=True, blank=True)

    # Route & Schedule
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
    pickup_date = models.DateField()
    drop_date = models.DateField(null=True, blank=True)
    time = models.TimeField(null=True, blank=True)

    # Load Details
    weight = models.CharField(max_length=50, blank=True, null=True)
    material = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # PAYMENTS
    final_payment = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    
    # Payment split (90% and 10%)
    first_half_payment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="First Half Payment (90%)",
        help_text="First payment installment - 90% of total freight"
    )
    
    second_half_payment = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Second Half Payment (10%)",
        help_text="Second payment installment - 10% of total freight"
    )

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    trip_status = models.CharField(max_length=20, choices=TRIP_STATUS_CHOICES, default='pending')

    # TRACKING DETAILS (NEW FIELD)
    tracking_details = models.TextField(
        blank=True, 
        null=True,
        help_text="Tracking details added by vendor during POD upload or later"
    )

    # LR DOCUMENTS
    lr_document = models.FileField(upload_to='lr_documents/', null=True, blank=True)
    lr_number = models.CharField(max_length=100, blank=True, null=True)
    lr_uploaded_at = models.DateTimeField(null=True, blank=True)
    lr_uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_lrs'
    )

    # POD DOCUMENTS (NO POD NUMBER)
    pod_document = models.FileField(upload_to='pod_documents/', null=True, blank=True)
    pod_uploaded_at = models.DateTimeField(null=True, blank=True)
    pod_uploaded_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_pods'
    )

    # Timeline
    pending_at = models.DateTimeField(null=True, blank=True)
    loaded_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    unloading_at = models.DateTimeField(null=True, blank=True)
    pod_uploaded_at = models.DateTimeField(null=True, blank=True)
    payment_completed_at = models.DateTimeField(null=True, blank=True)
    hold_at = models.DateTimeField(null=True, blank=True)

    # Hold reason
    hold_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for putting the trip on hold"
    )

    # Holding charges (kept for backward compatibility - now calculated from HoldingCharge model)
    holding_charges = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Total Holding Charges",
        help_text="Total additional charges for holding the shipment (auto-calculated)"
    )
    
    holding_charges_added_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Holding Charges Added At",
        help_text="When the first holding charge was added"
    )
    
    holding_charges_added_at_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Trip Status When Charges Added",
        help_text="The trip status at which first holding charge was added"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_loads'
    )

    def save(self, *args, **kwargs):
        # Generate Load ID
        if not self.load_id:
            last = Load.objects.order_by('-id').first()
            if last and last.load_id and '-' in last.load_id:
                try:
                    num = int(last.load_id.split('-')[1]) + 1
                except (ValueError, IndexError):
                    num = 1001
            else:
                num = 1001
            self.load_id = f"L-{num}"

        # Initial timestamp
        if not self.pk and not self.pending_at:
            self.pending_at = timezone.now()

        # Auto Sync Price = Final Payment
        if self.final_payment and self.final_payment > 0:
            self.price_per_unit = self.final_payment.quantize(Decimal('0.01'))

        # Rounding
        if self.final_payment is not None:
            self.final_payment = self.final_payment.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        super().save(*args, **kwargs)

    def update_trip_status(self, new_status, user=None, lr_number=None, tracking_details=None, send_notification=True):
        """Update trip status and send notifications"""
        previous_status = self.trip_status
        self.trip_status = new_status

        timestamp_fields = {
            'pending': 'pending_at',
            'loaded': 'loaded_at',
            'lr_uploaded': 'lr_uploaded_at',
            'in_transit': 'in_transit_at',
            'unloading': 'unloading_at',
            'pod_uploaded': 'pod_uploaded_at',
            'payment_completed': 'payment_completed_at',
            'hold': 'hold_at',
        }

        field_name = timestamp_fields.get(new_status)
        if field_name and not getattr(self, field_name):
            setattr(self, field_name, timezone.now())

        # LR Logic
        if new_status == 'lr_uploaded' and lr_number:
            self.lr_number = lr_number
            if user:
                self.lr_uploaded_by = user
                self.lr_uploaded_at = timezone.now()

        # POD Logic - Store tracking details
        if new_status == 'pod_uploaded' and user:
            self.pod_uploaded_by = user
            self.pod_uploaded_at = timezone.now()
            # Save tracking details if provided
            if tracking_details:
                self.tracking_details = tracking_details

        # Sync main status
        if new_status == 'in_transit':
            self.status = 'in_transit'
        elif new_status == 'payment_completed':
            self.status = 'delivered'

        # Save the model
        self.save()

        # Send notification to vendor if requested and vendor exists
        if send_notification and self.driver and hasattr(self.driver, 'owner') and self.driver.owner:
            try:
                # Import here to avoid circular imports
                from .notifications import send_trip_status_update_notification
                
                # Determine if triggered by admin
                triggered_by_admin = bool(user and (user.is_staff or user.role in ['admin', 'traffic_person']))
                
                # Send notification
                notification, success = send_trip_status_update_notification(
                    vendor=self.driver.owner,
                    load=self,
                    previous_status=previous_status,
                    new_status=new_status,
                    triggered_by_admin=triggered_by_admin
                )
                
                # Log the result
                import logging
                logger = logging.getLogger(__name__)
                if success:
                    logger.info(f"✅ Notification sent for load {self.load_id}: {previous_status} -> {new_status}")
                else:
                    logger.warning(f"⚠️ Notification failed for load {self.load_id}: {previous_status} -> {new_status}")
                    
            except ImportError as e:
                print(f"❌ Cannot import notifications module: {e}")
            except Exception as e:
                print(f"❌ Error sending status update notification for load {self.load_id}: {e}")

        return True

    def assign_to_vendor(self, vendor, vehicle, driver, user=None):
        """Assign load to vendor and update initial status"""
        self.driver = driver
        self.vehicle = vehicle
        self.assigned_at = timezone.now()
        self.status = 'assigned'
        
        # Save the model first
        self.save()
        
        # Update trip status to 'pending' (first status after assignment) WITHOUT notification
        # Send assignment notification separately
        try:
            from .notifications import send_trip_assigned_notification
            notification, success = send_trip_assigned_notification(
                vendor=vendor,
                load=self,
                vehicle=vehicle,
                driver=driver
            )
            
            import logging
            logger = logging.getLogger(__name__)
            if success:
                logger.info(f"✅ Assignment notification sent for load {self.load_id}")
            else:
                logger.warning(f"⚠️ Assignment notification failed for load {self.load_id}")
                
        except ImportError as e:
            print(f"❌ Cannot import notifications module: {e}")
        except Exception as e:
            print(f"❌ Error sending assignment notification: {e}")
            
        return self

    @property
    def total_trip_amount(self):
        base_amount = (self.final_payment or Decimal('0')).quantize(Decimal('0.01'))
        holding_charges = self.get_total_holding_charges()
        return (base_amount + holding_charges).quantize(Decimal('0.01'))

    @property
    def total_trip_amount_formatted(self):
        return f"₹{self.total_trip_amount:,.2f}"
    
    def get_total_holding_charges(self):
        """Calculate total holding charges from all HoldingCharge entries"""
        total = self.holding_charge_entries.aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        return Decimal(str(total)).quantize(Decimal('0.01'))
    
    def update_holding_charges_total(self):
        """Update the holding_charges field based on HoldingCharge entries"""
        self.holding_charges = self.get_total_holding_charges()
        self.save(update_fields=['holding_charges'])

    def get_vendor(self):
        """Get the vendor assigned to this load"""
        if self.driver and hasattr(self.driver, 'owner'):
            return self.driver.owner
        return None

    def get_status_progress(self):
        """Get progress percentage based on trip status"""
        progress_map = {
            'pending': 0,
            'loaded': 12.5,
            'lr_uploaded': 25,
            'in_transit': 50,
            'unloading': 62.5,
            'pod_uploaded': 75,
            'payment_completed': 100,
            'hold': 75,  # Hold is at same progress as pod_uploaded
        }
        return progress_map.get(self.trip_status, 0)

    def __str__(self):
        return f"{self.load_id} | {self.customer} | ₹{self.total_trip_amount:,.0f}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Load"
        verbose_name_plural = "Loads"


class HoldingCharge(models.Model):
    """
    Model to track individual holding charges applied to a load/trip.
    Each charge includes the amount, stage it was applied, and the reason.
    """
    load = models.ForeignKey(
        Load,
        on_delete=models.CASCADE,
        related_name='holding_charge_entries',
        help_text='The load/trip this holding charge is applied to'
    )
    
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        help_text='Amount of holding charges'
    )
    
    trip_stage = models.CharField(
        max_length=20,
        choices=Load.TRIP_STATUS_CHOICES,
        help_text='The trip stage/status at which this charge was applied'
    )
    
    reason = models.TextField(
        help_text='Reason for applying this holding charge'
    )
    
    added_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='added_holding_charges',
        help_text='Admin/user who added this charge'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When this charge was added'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When this charge was last updated'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Holding Charge'
        verbose_name_plural = 'Holding Charges'
        indexes = [
            models.Index(fields=['load', 'created_at']),
            models.Index(fields=['trip_stage']),
        ]
    
    def __str__(self):
        return f"₹{self.amount} - {self.load.load_id} - {self.trip_stage} - {self.created_at.strftime('%Y-%m-%d')}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update the load's total holding charges whenever a charge is added/updated
        if self.load:
            self.load.update_holding_charges_total()



class LoadRequest(models.Model):
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='requests')
    vendor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='load_requests')
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status_choices = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected')
    ]
    status = models.CharField(max_length=10, choices=status_choices, default='pending')

    def __str__(self):
        return f"{self.vendor.full_name} -> {self.load.load_id} ({self.status})"
    

class TripComment(models.Model):
    """Model to store chat messages for a trip between admin and vendor"""
    
    SENDER_TYPE_CHOICES = [
        ('admin', 'Admin'),
        ('vendor', 'Vendor/Owner'),
    ]
    
    load = models.ForeignKey(
        'Load', 
        on_delete=models.CASCADE, 
        related_name='comments',
        help_text='The load/trip this comment belongs to'
    )
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trip_comments',
        help_text='The user who sent this message'
    )
    
    sender_type = models.CharField(
        max_length=10,
        choices=SENDER_TYPE_CHOICES,
        help_text='Type of sender (admin or vendor)'
    )
    
    comment = models.TextField(
        help_text='The message content'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the comment was created'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='When the comment was last updated'
    )
    
    is_read = models.BooleanField(
        default=False,
        help_text='Whether the comment has been read by the recipient'
    )
    
    class Meta:
        ordering = ['created_at']
        verbose_name = 'Trip Comment'
        verbose_name_plural = 'Trip Comments'
        indexes = [
            models.Index(fields=['load', 'created_at']),
            models.Index(fields=['sender', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.sender.full_name} - {self.load.load_id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    def save(self, *args, **kwargs):
        # Automatically set sender_type based on sender's role
        if not self.sender_type:
            if self.sender.is_staff or self.sender.role == 'admin':
                self.sender_type = 'admin'
            elif self.sender.role == 'vendor':
                self.sender_type = 'vendor'
        super().save(*args, **kwargs)


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('trip_reassigned', 'Trip Reassigned'),
        ('trip_assigned', 'Trip Assigned'),
        ('payment_received', 'Payment Received'),
        ('trip_status_updated', 'Trip Status Updated'),
    ]

    recipient = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_trip = models.ForeignKey(
        'Load',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.recipient.full_name}"

    def mark_as_read(self):
        self.is_read = True
        self.save()
