from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import CustomUser, Customer, Driver, VehicleType, Load, Vehicle
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from django.db import transaction



def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            return render(request, 'admin_login.html', {'error': 'Email and password are required.'})

        # Use Django's authenticate function
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            if user.is_staff or user.role == 'admin':
                login(request, user)
                return redirect('admin_dashboard')
            else:
                return render(request, 'admin_login.html', {'error': 'Access denied. Not an admin user.'})
        else:
            return render(request, 'admin_login.html', {'error': 'Invalid email or password.'})

    return render(request, 'admin_login.html')


@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.role == 'admin'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')

    context = {
        'user': request.user,
        'total_users': CustomUser.objects.count(),
        'staff_count': CustomUser.objects.filter(is_staff=True).count(),
    }
    return render(request, 'admin_dashboard.html', context)


@login_required
def admin_logout(request):
    logout(request)
    return redirect('admin_login')

@login_required
def employee_list(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    employees = CustomUser.objects.filter(
        created_by=request.user,
        role='traffic_person'  # Only Traffic Persons
    ).order_by('-date_joined')

    return render(request, 'employee_list.html', {'employees': employees})

@login_required
@require_http_methods(["POST"])
def add_employee(request):
    """API endpoint to add new employee"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        # Get form data
        full_name = request.POST.get('fullName')
        email = request.POST.get('email')
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        role = request.POST.get('role')
        profile_photo = request.FILES.get('profilePhoto')
        
        # Validation
        if not all([full_name, email, mobile, password, role]):
            return JsonResponse({'success': False, 'error': 'All fields are required'}, status=400)
        
        # Check if email already exists
        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({'success': False, 'error': 'Email already exists'}, status=400)
        
        # Check if phone already exists
        if CustomUser.objects.filter(phone_number=mobile).exists():
            return JsonResponse({'success': False, 'error': 'Phone number already exists'}, status=400)
        
        # Determine role value
        role_value = 'admin' if role == 'Admin' else 'traffic_person'
        
        # Create user - set created_by to current admin
        user = CustomUser.objects.create_user(
            email=email,
            password=password,
            full_name=full_name,
            phone_number=mobile,
            role=role_value,
            is_staff=True if role == 'Admin' else False,
            is_active=True,
            username=None,
            created_by=request.user  # Set the creator
        )
        
        # Handle profile photo
        if profile_photo:
            user.profile_image = profile_photo
            user.save()
        
        return JsonResponse({
            'success': True,
            'message': f'{full_name} has been added successfully!',
            'employee': {
                'id': user.id,
                'name': user.full_name,
                'email': user.email,
                'contact': user.phone_number,
                'role': 'Admin' if user.is_staff else 'Traffic Person',
                'status': 'Active' if user.is_active else 'Inactive',
                'img': user.profile_image.url if user.profile_image else '/static/images/default_avatar.png',
                'joinDate': user.date_joined.strftime('%b %d, %Y'),
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_employee(request, employee_id):
    """API endpoint to update employee"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        employee = CustomUser.objects.get(id=employee_id)
        
        # Update fields
        if request.POST.get('fullName'):
            full_name = request.POST.get('fullName')
            employee.first_name = full_name.split()[0] if full_name else ''
            employee.last_name = ' '.join(full_name.split()[1:]) if len(full_name.split()) > 1 else ''
        
        if request.POST.get('email'):
            employee.email = request.POST.get('email')
            
        if request.POST.get('mobile'):
            employee.phone_number = request.POST.get('mobile')
            
        if request.POST.get('password'):
            employee.set_password(request.POST.get('password'))
            
        if request.POST.get('role'):
            employee.is_staff = (request.POST.get('role') == 'Admin')
            
        if request.FILES.get('profilePhoto'):
            employee.profile_image = request.FILES.get('profilePhoto')
        
        employee.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Employee updated successfully!'
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)




@login_required
@require_http_methods(["POST"])
def delete_employee(request, employee_id):
    """API endpoint to delete employee"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        employee = CustomUser.objects.get(id=employee_id)
        employee_name = employee.get_full_name() or employee.email
        employee.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{employee_name} has been deleted successfully!'
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employee not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def customer_list(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    customers = Customer.objects.all().order_by('-created_at')
    return render(request, 'customer_list.html', {'customers': customers})


@login_required
@require_http_methods(["POST"])
def add_customer(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        # Form fields
        customer_name = request.POST.get('customerName')
        phone_number = request.POST.get('phoneNumber')
        contact_person_name = request.POST.get('contactPersonName')
        contact_person_phone = request.POST.get('contactPersonPhone')
        location = request.POST.get('location')
        profile_photo = request.FILES.get('profilePhoto')

        # Validation
        if not all([customer_name, phone_number]):
            return JsonResponse({'success': False, 'error': 'Customer name & phone are required'}, status=400)

        if Customer.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({'success': False, 'error': 'Phone number already exists'}, status=400)

        # Create
        customer = Customer.objects.create(
            customer_name=customer_name,
            phone_number=phone_number,
            contact_person_name=contact_person_name,
            contact_person_phone=contact_person_phone,
            location=location,
            is_active=True,
        )

        if profile_photo:
            customer.profile_image = profile_photo
            customer.save()

        # JSON payload for JS
        payload = {
            'id': customer.id,
            'name': customer.customer_name,
            'phone': customer.phone_number,
            'contactPerson': customer.contact_person_name or '-',
            'contactPhone': customer.contact_person_phone or '-',
            'location': customer.location or '-',
            'img': customer.profile_image.url if customer.profile_image else '/static/images/default_avatar.png',
            'joinDate': customer.created_at.strftime('%b %d, %Y'),
            'status': 'Active' if customer.is_active else 'Inactive',
        }

        return JsonResponse({
            'success': True,
            'message': f'{customer_name} added successfully!',
            'customer': payload
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_customer(request, pk):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        customer = Customer.objects.get(pk=pk)
        customer.delete()
        return JsonResponse({'success': True, 'message': 'Customer deleted'})
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)
    

@login_required
def driver_list(request):
    """Display all drivers created by current admin"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    # Fetch all drivers created by this admin
    drivers = Driver.objects.filter(created_by=request.user).select_related('owner').order_by('-created_at')
    
    # Get all vendors for the owner dropdown
    vendors = CustomUser.objects.filter(role='vendor', is_active=True)
    
    context = {
        'drivers': drivers,
        'vendors': vendors,
    }
    return render(request, 'driver_list.html', context)


@login_required
@require_http_methods(["POST"])
def add_driver(request):
    """API endpoint to add new driver"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        # Get form data
        full_name = request.POST.get('fullName')
        phone_number = request.POST.get('phoneNo')
        owner_id = request.POST.get('owner')
        
        # Get file uploads
        profile_photo = request.FILES.get('profilePhoto')
        pan_document = request.FILES.get('panDocument')
        aadhar_document = request.FILES.get('aadharDocument')
        rc_document = request.FILES.get('rcDocument')
        
        # Validation
        if not all([full_name, phone_number, owner_id]):
            return JsonResponse({
                'success': False, 
                'error': 'Full Name, Phone Number, and Owner are required'
            }, status=400)
        
        # Check if phone already exists
        if Driver.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Phone number already exists'
            }, status=400)
        
        # Verify owner exists and is a vendor
        try:
            owner = CustomUser.objects.get(id=owner_id, role='vendor')
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid owner selected'
            }, status=400)
        
        # Create driver
        driver = Driver.objects.create(
            full_name=full_name,
            phone_number=phone_number,
            owner=owner,
            profile_photo=profile_photo,
            pan_document=pan_document,
            aadhar_document=aadhar_document,
            rc_document=rc_document,
            created_by=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'{full_name} has been added successfully!',
            'driver': {
                'id': driver.id,
                'name': driver.full_name,
                'phone': driver.phone_number,
                'owner': driver.owner.full_name,
                'owner_id': driver.owner.id,
                'status': driver.get_status_display(),
                'img': driver.profile_photo.url if driver.profile_photo else '/static/images/default_driver.png',
                'joinDate': driver.created_at.strftime('%b %d, %Y'),
                'totalTrips': driver.total_trips,
                'completedTrips': driver.completed_trips,
                'pendingTrips': driver.pending_trips,
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_driver(request, driver_id):
    """API endpoint to update driver"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        driver = Driver.objects.get(id=driver_id, created_by=request.user)
        
        # Update fields
        if request.POST.get('fullName'):
            driver.full_name = request.POST.get('fullName')
        
        if request.POST.get('phoneNo'):
            driver.phone_number = request.POST.get('phoneNo')
        
        if request.POST.get('owner'):
            owner = CustomUser.objects.get(id=request.POST.get('owner'), role='vendor')
            driver.owner = owner
        
        # Update documents if provided
        if request.FILES.get('profilePhoto'):
            driver.profile_photo = request.FILES.get('profilePhoto')
        
        if request.FILES.get('panDocument'):
            driver.pan_document = request.FILES.get('panDocument')
        
        if request.FILES.get('aadharDocument'):
            driver.aadhar_document = request.FILES.get('aadharDocument')
        
        if request.FILES.get('rcDocument'):
            driver.rc_document = request.FILES.get('rcDocument')
        
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Driver updated successfully!'
        })
        
    except Driver.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Driver not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_driver(request, driver_id):
    """API endpoint to delete driver"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        driver = Driver.objects.get(id=driver_id, created_by=request.user)
        driver_name = driver.full_name
        driver.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'{driver_name} has been deleted successfully!'
        })
        
    except Driver.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Driver not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def toggle_driver_status(request, driver_id):
    """API endpoint to toggle driver active status"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        driver = Driver.objects.get(id=driver_id, created_by=request.user)
        driver.is_active = not driver.is_active
        driver.status = 'active' if driver.is_active else 'inactive'
        driver.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Driver status updated to {driver.get_status_display()}'
        })
        
    except Driver.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Driver not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
def vehicle_type_list(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    vehicle_types = VehicleType.objects.all().order_by('-created_at')
    return render(request, 'vehicle_type_list.html', {'vehicle_types': vehicle_types})


@login_required
@require_http_methods(["POST"])
def add_vehicle_type(request):
    """API endpoint to add new vehicle type"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        name = request.POST.get('name')

        # Validation
        if not name:
            return JsonResponse({'success': False, 'error': 'Name is required'}, status=400)

        if VehicleType.objects.filter(name__iexact=name).exists():
            return JsonResponse({'success': False, 'error': 'Vehicle type already exists'}, status=400)

        vehicle_type = VehicleType.objects.create(name=name)

        return JsonResponse({
            'success': True,
            'message': f'"{name}" added successfully!',
            'vehicle_type': {
                'id': vehicle_type.id,
                'name': vehicle_type.name,
                'created_at': vehicle_type.created_at.strftime('%b %d, %Y')
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_vehicle_type(request, pk):
    """API endpoint to delete a vehicle type"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        vt = VehicleType.objects.get(pk=pk)
        vt.delete()
        return JsonResponse({'success': True, 'message': 'Vehicle type deleted successfully!'})
    except VehicleType.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Not found'}, status=404)
    
@login_required
def vehicle_type_list_view(request):
    """API endpoint to get all vehicle types"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        vehicle_types = VehicleType.objects.all().order_by('-created_at')
        data = [{
            'id': vt.id,
            'name': vt.name,
            'created_at': vt.created_at.strftime('%b %d, %Y')
        } for vt in vehicle_types]

        return JsonResponse({
            'success': True,
            'vehicle_types': data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required
def load_list(request):
    """Display list of all loads"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    # Fetch loads created by the current admin
    loads = Load.objects.filter(created_by=request.user).select_related(
        'customer', 'vehicle_type'
    ).order_by('-created_at')
    
    # Fetch all customers and vehicle types for the dropdown
    customers = Customer.objects.filter(is_active=True).order_by('customer_name')
    vehicle_types = VehicleType.objects.all().order_by('name')
    
    context = {
        'loads': loads,
        'customers': customers,
        'vehicle_types': vehicle_types,
    }
    return render(request, 'load_list.html', context)


@login_required
@require_http_methods(["POST"])
def add_load(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid method'}, status=400)

    try:
        with transaction.atomic():
            from .models import Load, Customer, VehicleType

            # Get objects
            customer = Customer.objects.get(id=request.POST['customer'])
            vehicle_type = VehicleType.objects.get(id=request.POST['vehicleType'])

            # Basic fields
            pickup_location = request.POST['pickupLocation'].strip()
            drop_location = request.POST['dropLocation'].strip()
            pickup_date = datetime.strptime(request.POST['pickupDate'], '%Y-%m-%d').date()
            drop_date_str = request.POST.get('dropDate', '').strip()
            drop_date = datetime.strptime(drop_date_str, '%Y-%m-%d').date() if drop_date_str else pickup_date

            # Time from hidden field
            time_str = request.POST['time']  # "02:30 PM"
            time_obj = datetime.strptime(time_str, '%I:%M %p').time()

            # Weight — save exactly as typed
            weight_text = request.POST['weight'].strip()
            if not weight_text:
                return JsonResponse({'success': False, 'error': 'Weight required'}, status=400)

            # Price per unit — convert safely
            price_str = request.POST['pricePerUnit'].replace(',', '').strip()
            try:
                price_per_unit = Decimal(price_str)
                if price_per_unit <= 0:
                    raise ValueError
            except:
                return JsonResponse({'success': False, 'error': 'Invalid price'}, status=400)

            # Create load
            load = Load.objects.create(
                customer=customer,
                contact_person_name=request.POST.get('contactPersonName', '') or None,
                contact_person_phone=request.POST.get('contactPersonPhone', '') or None,
                vehicle_type=vehicle_type,
                weight=weight_text,  # ← Saved exactly
                price_per_unit=price_per_unit,
                pickup_location=pickup_location,
                drop_location=drop_location,
                pickup_date=pickup_date,
                drop_date=drop_date,
                time=time_obj,
                material=request.POST.get('material', '') or None,
                notes=request.POST.get('notes', '') or None,
                created_by=request.user,
                status='pending'
            )

            total_price = load.total_price

            return JsonResponse({
                'success': True,
                'message': f'Load {load.load_id} created!',
                'load': {
                    'id': load.id,
                    'load_id': load.load_id,
                    'customer_name': customer.customer_name,
                    'customer_phone': customer.phone_number,
                    'contact_person': load.contact_person_name or '',
                    'contact_phone': load.contact_person_phone or '',
                    'pickup_location': pickup_location,
                    'drop_location': drop_location,
                    'pickup_date': pickup_date.strftime('%b %d, %Y'),
                    'drop_date': drop_date.strftime('%b %d, %Y'),
                    'time': time_obj.strftime('%I:%M %p'),
                    'vehicle_type': vehicle_type.name,
                    'weight': load.weight,  # ← Shows exactly as typed
                    'price_per_unit': str(price_per_unit),
                    'total_price': str(total_price),
                    'material': load.material or '',
                    'notes': load.notes or '',
                    'status': 'pending',
                    'status_display': 'Pending',
                }
            })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Please check all fields and try again.'
        }, status=400)


@login_required
@require_http_methods(["GET"])
def get_customer_details(request, customer_id):
    """API endpoint to get customer contact details"""
    try:
        customer = Customer.objects.get(id=customer_id)
        return JsonResponse({
            'success': True,
            'contact_person_name': customer.contact_person_name or '',
            'contact_person_phone': customer.contact_person_phone or '',
        })
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def delete_load(request, load_id):
    """API endpoint to delete load"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        load = Load.objects.get(id=load_id, created_by=request.user)
        load_number = load.load_id
        load.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Load {load_number} has been deleted successfully!'
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Load not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def update_load_status(request, load_id):
    """API endpoint to update load status"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        load = Load.objects.get(id=load_id)
        new_status = request.POST.get('status')
        
        if new_status not in dict(Load.STATUS_CHOICES):
            return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)
        
        load.status = new_status
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Load status updated to {load.get_status_display()}',
            'status': load.get_status_display()
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Load not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

@login_required
def vendor_list(request):
    """Display list of vendors created by current admin"""
    if not request.user.is_staff:
        return redirect('admin_login')

    vendors = CustomUser.objects.filter(
        role='vendor',
        created_by=request.user
    ).order_by('-date_joined')

    return render(request, 'vendor_list.html', {'vendors': vendors})


@login_required
@require_http_methods(["POST"])
def add_vendor(request):
    """Add new vendor - handles both AJAX and regular POST"""
    try:
        # Extract fields
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '').strip()

        # Validation
        if not full_name:
            return JsonResponse({'success': False, 'error': 'Full name is required.'}, status=400)

        if not phone:
            return JsonResponse({'success': False, 'error': 'Phone number is required.'}, status=400)

        if not password:
            return JsonResponse({'success': False, 'error': 'Password is required.'}, status=400)

        # Check duplicate phone
        if CustomUser.objects.filter(phone_number=phone).exists():
            return JsonResponse({
                'success': False,
                'error': f'A vendor with phone number {phone} already exists.'
            }, status=400)

        # Optional fields
        address = request.POST.get('address', '').strip() or None
        pan_number = request.POST.get('pan_number', '').strip() or None
        tds_file = request.FILES.get('tds_declaration')

        # Auto-generate email
        email = f"{phone}@vendor.local"

        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': 'This phone number is already registered.'
            }, status=400)

        # Create vendor
        with transaction.atomic():
            vendor = CustomUser(
                username=None,
                full_name=full_name,
                phone_number=phone,
                email=email,
                address=address,
                pan_number=pan_number,
                role='vendor',
                created_by=request.user,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            vendor.set_password(password)

            if tds_file:
                vendor.tds_declaration = tds_file

            vendor.save()

        return JsonResponse({
            'success': True,
            'message': f'Vendor "{vendor.full_name}" has been created successfully!',
            'vendor': {
                'id': vendor.id,
                'full_name': vendor.full_name,
                'phone_number': vendor.phone_number,
                'address': vendor.address or '-',
                'pan_number': vendor.pan_number or '-',
                'tds_declaration': vendor.tds_declaration.url if vendor.tds_declaration else '',
                'profile_image': vendor.profile_image.url if vendor.profile_image else '',
                'date_joined': vendor.date_joined.strftime('%b %d, %Y'),
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Failed to create vendor: {str(e)}'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def delete_vendor(request, vendor_id):
    """Delete a vendor"""
    try:
        vendor = get_object_or_404(
            CustomUser,
            id=vendor_id,
            role='vendor',
            created_by=request.user
        )

        name = vendor.full_name
        vendor.delete()

        return JsonResponse({
            'success': True,
            'message': f'Vendor "{name}" has been deleted successfully.'
        })
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Failed to delete vendor.'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_vendor(request, vendor_id):
    """Get vendor details"""
    try:
        vendor = get_object_or_404(
            CustomUser,
            id=vendor_id,
            role='vendor',
            created_by=request.user
        )

        return JsonResponse({
            'success': True,
            'vendor': {
                'id': vendor.id,
                'full_name': vendor.full_name,
                'phone_number': vendor.phone_number,
                'address': vendor.address or '-',
                'pan_number': vendor.pan_number or '-',
                'tds_declaration': vendor.tds_declaration.url if vendor.tds_declaration else '',
                'profile_image': vendor.profile_image.url if vendor.profile_image else '',
                'date_joined': vendor.date_joined.strftime('%b %d, %Y'),
                'is_active': vendor.is_active,
            }
        })
    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Vendor not found.'
        }, status=404)


@login_required
@require_http_methods(["POST"])
def toggle_vendor_status(request, vendor_id):
    """Toggle vendor active/inactive status"""
    try:
        vendor = get_object_or_404(
            CustomUser,
            id=vendor_id,
            role='vendor',
            created_by=request.user
        )

        vendor.is_active = not vendor.is_active
        vendor.save()

        return JsonResponse({
            'success': True,
            'message': f'Vendor "{vendor.full_name}" has been {"activated" if vendor.is_active else "deactivated"} successfully.',
            'is_active': vendor.is_active
        })

    except Exception:
        return JsonResponse({
            'success': False,
            'error': 'Failed to update vendor status.'
        }, status=500)


@login_required
def vehicle_list(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    # Vehicles: still only those whose owner was created by this admin
    vehicles = Vehicle.objects.filter(owner__created_by=request.user) \
                    .select_related('owner').order_by('-id')

    # Vendors: ALL active vendors (role='vendor')
    vendors = CustomUser.objects.filter(role='vendor', is_active=True).order_by('full_name')

    return render(request, 'vehicle_list.html', {
        'vehicles': vehicles,
        'vendors': vendors
    })

@login_required
@require_http_methods(["POST"])
def add_vehicle(request):
    try:
        reg_no = request.POST.get('reg_no', '').strip().upper()
        owner_id = request.POST.get('owner')
        insurance_doc = request.FILES.get('insurance_doc')
        rc_doc = request.FILES.get('rc_doc')

        if not reg_no or not owner_id:
            return JsonResponse({'success': False, 'error': 'Reg No and Owner are required.'}, status=400)

        if Vehicle.objects.filter(reg_no=reg_no).exists():
            return JsonResponse({'success': False, 'error': 'Vehicle with this Reg No already exists.'}, status=400)

        # SECURITY: Owner must be a real vendor (any vendor)
        try:
            owner = CustomUser.objects.get(id=owner_id, role='vendor', is_active=True)
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid or inactive owner selected.'}, status=400)

        # OPTIONAL: Still tie vehicle to admin's "scope" via owner__created_by?
        # → Not needed for display, but you can keep if you want strict ownership
        # if owner.created_by != request.user:
        #     return JsonResponse({'success': False, 'error': 'You can only add vehicles for your own vendors.'}, status=403)

        with transaction.atomic():
            vehicle = Vehicle(
                reg_no=reg_no,
                owner=owner,
                status='active'
            )
            if insurance_doc: vehicle.insurance_doc = insurance_doc
            if rc_doc: vehicle.rc_doc = rc_doc
            vehicle.save()

        return JsonResponse({
            'success': True,
            'message': f'Vehicle {reg_no} added successfully!',
            'vehicle': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': owner.full_name,
                'type': vehicle.get_type_display(),
                'fuel_type': vehicle.get_fuel_type_display(),
            },
            'vehicle_data': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': owner.full_name,
                'owner_phone': owner.phone_number,
                'type': vehicle.get_type_display(),
                'fuel_type': vehicle.get_fuel_type_display(),
                'insurance_doc': vehicle.insurance_doc.url if vehicle.insurance_doc else '',
                'rc_doc': vehicle.rc_doc.url if vehicle.rc_doc else '',
                'status': 'active',
                'status_label': 'Active'
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_vehicle(request, vehicle_id):
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, owner__created_by=request.user)
        reg_no = vehicle.reg_no
        vehicle.delete()
        return JsonResponse({'success': True, 'message': f'Vehicle {reg_no} deleted.'})
    except Exception:
        return JsonResponse({'success': False, 'error': 'Failed to delete.'}, status=500)

@login_required
@require_http_methods(["POST"])
def toggle_vehicle_status(request, vehicle_id):
    try:
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, owner__created_by=request.user)
        vehicle.status = 'inactive' if vehicle.status == 'active' else 'active'
        vehicle.save()
        return JsonResponse({
            'success': True,
            'message': f'Vehicle {vehicle.reg_no} is now {vehicle.get_status_display().lower()}.'
        })
    except Exception:
        return JsonResponse({'success': False, 'error': 'Failed to update status.'}, status=500)