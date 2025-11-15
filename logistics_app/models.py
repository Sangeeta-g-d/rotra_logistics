# models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
import re
from decimal import Decimal, InvalidOperation



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
    

class Load(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]
    
    load_id = models.CharField(max_length=20, unique=True, editable=False)
    
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='loads'
    )
    
    contact_person_name = models.CharField(max_length=255, blank=True, null=True)
    contact_person_phone = models.CharField(max_length=15, blank=True, null=True)
    
    vehicle_type = models.ForeignKey(
        VehicleType,
        on_delete=models.PROTECT,
        related_name='loads'
    )
    
    pickup_location = models.CharField(max_length=255)
    drop_location = models.CharField(max_length=255)
    pickup_date = models.DateField()
    drop_date = models.DateField()
    time = models.TimeField()
    
    # FREE TEXT — Saved exactly as user types
    weight = models.CharField(
        max_length=50,
        help_text='e.g. 10 Ton, 20T, 15.5 Heavy, 8 Ton Urgent'
    )
    
    # Always Decimal — for correct calculation
    price_per_unit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Price per ton (₹)'
    )
    
    material = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_loads'
    )
    
    def save(self, *args, **kwargs):
        if not self.load_id:
            last = Load.objects.order_by('-id').first()
            if last and last.load_id:
                num = int(last.load_id.split('-')[1]) + 1
            else:
                num = 1001
            self.load_id = f'L-{num}'
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.load_id} - {self.customer.customer_name}"
    
    # EXTRACT NUMBER FROM TEXT LIKE "10 Ton" → 10.0
    def get_weight_numeric(self):
        if not self.weight:
            return Decimal('0')
        match = re.search(r'[\d.]+', self.weight)
        if match:
            try:
                return Decimal(match.group())
            except InvalidOperation:
                return Decimal('0')
        return Decimal('0')
    
    # FIXED TOTAL PRICE — THIS WAS THE BUG!
    @property
    def total_price(self):
        return self.get_weight_numeric() * self.price_per_unit
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Load'
        verbose_name_plural = 'Loads'



class Vehicle(models.Model):
    # CORRECT: Each choice is a tuple (value, label)
    TYPE_CHOICES = [
        ('heavy_truck', 'Heavy Truck'),
        ('medium_truck', 'Medium Truck'),
        ('light_truck', 'Light Truck'),
    ]

    FUEL_CHOICES = [
        ('diesel', 'Diesel'),
        ('petrol', 'Petrol'),
        ('cng', 'CNG'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]

    reg_no = models.CharField(max_length=20, unique=True)
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='vehicles')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='heavy_truck')
    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default='diesel')
    insurance_doc = models.FileField(upload_to='vehicles/insurance/', null=True, blank=True)
    rc_doc = models.FileField(upload_to='vehicles/rc/', null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.reg_no