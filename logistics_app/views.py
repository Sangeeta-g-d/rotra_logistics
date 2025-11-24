from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import CustomUser, Customer, Driver, VehicleType, Load, Vehicle, LoadRequest, TripComment
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
import re
from django.db import transaction
from django.core.files.storage import default_storage
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils import timezone
import traceback





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
    """API endpoint to add new driver (without profile photo)"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        full_name = request.POST.get('fullName')
        phone_number = request.POST.get('phoneNo')
        owner_id = request.POST.get('owner')
        
        # File uploads (no profile photo)
        pan_document = request.FILES.get('panDocument')
        aadhar_document = request.FILES.get('aadharDocument')
        rc_document = request.FILES.get('rcDocument')
        
        # Validation
        if not all([full_name, phone_number, owner_id]):
            return JsonResponse({
                'success': False, 
                'error': 'Full Name, Phone Number, and Owner are required'
            }, status=400)
        
        if Driver.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({
                'success': False, 
                'error': 'A driver with this phone number already exists'
            }, status=400)
        
        try:
            owner = CustomUser.objects.get(id=owner_id, role='vendor')
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Selected owner is invalid or not a vendor'
            }, status=400)
        
        # Create driver (no profile_photo field)
        driver = Driver.objects.create(
            full_name=full_name.strip(),
            phone_number=phone_number,
            owner=owner,
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
                'status': driver.get_status_display(),
                'joinDate': driver.created_at.strftime('%b %d, %Y'),
                'hasPan': bool(driver.pan_document),
                'hasAadhar': bool(driver.aadhar_document),
                'hasRC': bool(driver.rc_document),
            }
        }, status=201)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': 'Something went wrong. Please try again.'}, status=500)


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
    """Display only PENDING loads created by the admin"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    # Show ONLY pending loads created by this admin
    loads = Load.objects.filter(
        created_by=request.user,
        status='pending'  # Changed from 'request_status' to 'status'
    ).select_related(
        'customer', 'vehicle_type', 'driver', 'vehicle'
    ).order_by('-created_at')

    customers = Customer.objects.filter(is_active=True).order_by('customer_name')
    vehicle_types = VehicleType.objects.all().order_by('name')

    context = {
        'loads': loads,
        'customers': customers,
        'vehicle_types': vehicle_types,
    }
    return render(request, 'load_list.html', context)


@login_required
@require_http_methods(["GET"])
def load_requests_api(request, load_id):
    """API endpoint to get LoadRequest data for a specific load - only for load creator"""
    try:
        # First, verify that the current user created this load
        load = Load.objects.get(id=load_id)
        
        # Check if the current user is the creator of this load
        if load.created_by != request.user:
            return JsonResponse({
                'error': 'Access denied. You can only view requests for loads you created.'
            }, status=403)
        
        # Get only pending LoadRequest objects for this load
        load_requests = LoadRequest.objects.filter(
            load_id=load_id,
            status='pending'  # Only return pending requests
        ).select_related('vendor').order_by('-created_at')
        
        requests_data = []
        for req in load_requests:
            requests_data.append({
                'id': req.id,
                'vendor_id': req.vendor.id,  # Include vendor_id
                'vendor_name': req.vendor.full_name,
                'vendor_phone': req.vendor.phone_number,
                'vendor_email': req.vendor.email,
                'message': req.message,
                'status': req.status,
                'status_display': req.get_status_display(),
                'created_at': req.created_at.strftime('%b %d, %Y %I:%M %p'),
            })
        
        return JsonResponse(requests_data, safe=False)
        
    except Load.DoesNotExist:
        return JsonResponse({
            'error': 'Load not found'
        }, status=404)
    except Exception as e:
        print(f"Error loading requests for load {load_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def accept_load_request(request, load_id, request_id):
    """API endpoint to accept a load request and assign driver/vehicle"""
    try:
        # Get the load and verify ownership
        load = Load.objects.get(id=load_id)
        if load.created_by != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        # Get the load request
        load_request = LoadRequest.objects.get(id=request_id, load=load)
        
        # Verify request is still pending
        if load_request.status != 'pending':
            return JsonResponse({'success': False, 'error': 'Request already processed'}, status=400)

        # Parse JSON data from request body
        try:
            data = json.loads(request.body)
            vehicle_id = data.get('vehicle_id')
            driver_id = data.get('driver_id')
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)

        # Validate required fields
        if not vehicle_id or not driver_id:
            return JsonResponse({'success': False, 'error': 'Vehicle and Driver are required'}, status=400)

        # Get the vehicle and driver objects
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id, owner=load_request.vendor)
            driver = Driver.objects.get(id=driver_id, owner=load_request.vendor)
        except Vehicle.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Vehicle not found or does not belong to this vendor'}, status=404)
        except Driver.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Driver not found or does not belong to this vendor'}, status=404)

        # Update the load request status
        load_request.status = 'accepted'
        load_request.save()

        # Update the load with assigned driver and vehicle
        load.driver = driver
        load.vehicle = vehicle
        load.status = 'assigned'
        load.save()

        # Reject all other pending requests for this load
        LoadRequest.objects.filter(
            load=load, 
            status='pending'
        ).exclude(id=request_id).update(status='rejected')

        return JsonResponse({
            'success': True,
            'message': 'Load assigned successfully!',
            'load': {
                'id': load.id,
                'load_id': load.load_id,
                'driver_name': driver.full_name,
                'driver_phone': driver.phone_number,
                'vehicle_reg_no': vehicle.reg_no,
                'vehicle_type': vehicle.get_type_display(),
                'status': load.get_status_display()
            }
        })

    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Load not found'}, status=404)
    except LoadRequest.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)
    except Exception as e:
        print(f"Error accepting load request: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@login_required
@require_http_methods(["POST"])
def accept_load_request_with_assignment(request, load_id, request_id):
    try:
        load = get_object_or_404(Load, id=load_id, created_by=request.user)
        load_request = get_object_or_404(LoadRequest, id=request_id, load=load, status='pending')

        data = json.loads(request.body)
        vehicle_id = data.get('vehicle_id')
        driver_id = data.get('driver_id')

        if not vehicle_id or not driver_id:
            return JsonResponse({'success': False, 'error': 'Please select vehicle and driver'}, status=400)

        vehicle = get_object_or_404(Vehicle, id=vehicle_id, owner=load_request.vendor)
        driver = get_object_or_404(Driver, id=driver_id, owner=load_request.vendor)

        with transaction.atomic():
            load.driver = driver
            load.vehicle = vehicle
            load.status = 'assigned'
            load.assigned_at = timezone.now()
            load.save()

            load_request.status = 'accepted'
            load_request.save()

            LoadRequest.objects.filter(load=load, status='pending').exclude(id=request_id).update(status='rejected')

        return JsonResponse({
            'success': True,
            'message': 'Load assigned successfully!',
            'driver_name': driver.full_name,
            'vehicle_reg': vehicle.reg_no
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def reject_load_request(request, load_id, request_id):
    return _handle_load_request_action(request, load_id, request_id, 'rejected')

def _handle_load_request_action(request, load_id, request_id, new_status):
    try:
        load = Load.objects.get(id=load_id)
        if load.created_by != request.user:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        load_request = LoadRequest.objects.get(id=request_id, load=load)
        
        if load_request.status != 'pending':
            return JsonResponse({'error': 'Request already processed'}, status=400)

        load_request.status = new_status
        load_request.save()

        # Optional: if accepted → assign driver automatically, etc.
        if new_status == 'accepted':
            load.driver = load_request.vendor   # assuming vendor is the driver
            load.status = 'assigned'            # or whatever your flow is
            load.save()

        return JsonResponse({
            'success': True,
            'message': f'Request {new_status.capitalize()} successfully'
        })
    except Load.DoesNotExist:
        return JsonResponse({'error': 'Load not found'}, status=404)
    except LoadRequest.DoesNotExist:
        return JsonResponse({'error': 'Request not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def vendor_vehicles_api(request, vendor_id):
    """API endpoint to get vehicles for a specific vendor"""
    try:
        # Verify vendor exists and user has permission
        vendor = CustomUser.objects.get(id=vendor_id, role='vendor')
        
        # Get vehicles owned by this vendor
        vehicles = Vehicle.objects.filter(owner=vendor, status='active')
        
        vehicles_data = []
        for vehicle in vehicles:
            vehicles_data.append({
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'type': vehicle.type,
                'load_capacity': str(vehicle.load_capacity) if vehicle.load_capacity else None,
            })
        
        return JsonResponse(vehicles_data, safe=False)
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Vendor not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["GET"])
def vendor_drivers_api(request, vendor_id):
    """API endpoint to get drivers for a specific vendor"""
    try:
        # Verify vendor exists and user has permission
        vendor = CustomUser.objects.get(id=vendor_id, role='vendor')
        
        # Get drivers owned by this vendor
        drivers = Driver.objects.filter(owner=vendor, is_active=True)
        
        drivers_data = []
        for driver in drivers:
            drivers_data.append({
                'id': driver.id,
                'full_name': driver.full_name,
                'phone_number': driver.phone_number,
                'status': driver.status,
            })
        
        return JsonResponse(drivers_data, safe=False)
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'error': 'Vendor not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# AJAX view to update request status
@login_required
@csrf_exempt
def update_request_status(request, request_id):
    if request.method == "POST":
        status = request.POST.get('status')
        load_request = get_object_or_404(LoadRequest, id=request_id)
        load_request.status = status
        load_request.save()
        return JsonResponse({'success': True, 'status': status})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})


@login_required
@require_http_methods(["POST"])
def add_load(request):
    try:
        with transaction.atomic():
            # 1. Customer
            customer_id = request.POST.get('customer')
            if not customer_id:
                return JsonResponse({'success': False, 'error': 'Customer is required'}, status=400)
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid customer'}, status=400)

            # 2. Vehicle Type
            vehicle_type_id = request.POST.get('vehicleType')
            if not vehicle_type_id:
                return JsonResponse({'success': False, 'error': 'Vehicle type is required'}, status=400)
            try:
                vehicle_type = VehicleType.objects.get(id=vehicle_type_id)
            except VehicleType.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid vehicle type'}, status=400)

            # 3. Locations
            pickup_location = request.POST.get('pickupLocation', '').strip()
            drop_location = request.POST.get('dropLocation', '').strip()
            if not pickup_location or not drop_location:
                return JsonResponse({'success': False, 'error': 'Both pickup & drop locations are required'}, status=400)

            # 4. Dates
            pickup_date_str = request.POST.get('pickupDate')
            if not pickup_date_str:
                return JsonResponse({'success': False, 'error': 'Pickup date is required'}, status=400)
            try:
                pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid pickup date format'}, status=400)

            drop_date_str = request.POST.get('dropDate', '').strip()
            drop_date = None
            if drop_date_str:
                try:
                    drop_date = datetime.strptime(drop_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid drop date format'}, status=400)

            # 5. Time
            time_str = request.POST.get('time', '').strip()
            if not time_str:
                return JsonResponse({'success': False, 'error': 'Time is required'}, status=400)
            try:
                time_obj = datetime.strptime(time_str, '%I:%M %p').time()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid time format. Use: 02:30 PM'}, status=400)

            # 6. Total Trip Amount (this is what admin enters)
            total_amount_str = request.POST.get('total_amount', '').replace(',', '').strip()
            if not total_amount_str:
                return JsonResponse({'success': False, 'error': 'Total trip amount is required'}, status=400)
            try:
                total_amount = Decimal(total_amount_str)
                if total_amount <= 0:
                    return JsonResponse({'success': False, 'error': 'Amount must be greater than 0'}, status=400)
            except:
                return JsonResponse({'success': False, 'error': 'Invalid amount format'}, status=400)

            # 7. Correct 90-10 Split (with proper 2 decimal rounding)
            first_half_payment = (total_amount * Decimal('0.9')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            final_payment = (total_amount - first_half_payment).quantize(Decimal('0.01'))

            # price_per_unit = full freight amount entered by admin
            price_per_unit = total_amount

            # 8. Optional fields
            contact_person_name = request.POST.get('contactPersonName', '').strip() or None
            contact_person_phone = request.POST.get('contactPersonPhone', '').strip() or None
            weight = request.POST.get('weight', '').strip() or None
            material = request.POST.get('material', '').strip() or None
            notes = request.POST.get('notes', '').strip() or None

            # 9. Create Load Instance
            load = Load(
                customer=customer,
                contact_person_name=contact_person_name,
                contact_person_phone=contact_person_phone,
                vehicle_type=vehicle_type,
                pickup_location=pickup_location,
                drop_location=drop_location,
                pickup_date=pickup_date,
                drop_date=drop_date,
                time=time_obj,
                weight=weight,
                material=material,
                notes=notes,

                # PAYMENTS
                price_per_unit=price_per_unit,                    # Full amount saved here
                first_half_payment=first_half_payment,           # 90%
                final_payment=final_payment,                     # 10%

                created_by=request.user,
                status='pending',
                trip_status='pending'
            )

            load.save()  # This will also auto-generate load_id and sync price_per_unit via save()

            # 10. Success Response
            return JsonResponse({
                'success': True,
                'message': f'Load {load.load_id} created successfully!',
                'load': {
                    'id': load.id,
                    'load_id': load.load_id,
                    'price_per_unit': str(load.price_per_unit),
                    'first_half_payment': str(load.first_half_payment),
                    'final_payment': str(load.final_payment),
                    'total_trip_amount': str(load.total_trip_amount),
                    'total_trip_amount_formatted': load.total_trip_amount_formatted,
                }
            })

    except Exception as e:
        print("=== ADD LOAD ERROR ===")
        traceback.print_exc()
        print("=== END ERROR ===")
        return JsonResponse({
            'success': False,
            'error': 'Failed to create load. Please try again.'
        }, status=500)
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
    vehicles = Vehicle.objects.select_related('owner').order_by('-id')

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
            },
            'vehicle_data': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': owner.full_name,
                'owner_phone': owner.phone_number,
                'insurance_doc': vehicle.insurance_doc.url if vehicle.insurance_doc else '',
                'rc_doc': vehicle.rc_doc.url if vehicle.rc_doc else '',
                'hasInsurance': bool(vehicle.insurance_doc),
                'hasRC': bool(vehicle.rc_doc),
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
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        reg_no = vehicle.reg_no
        vehicle.delete()
        return JsonResponse({'success': True, 'message': f'Vehicle {reg_no} deleted.'})
    except Exception:
        return JsonResponse({'success': False}, status=500)
    
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
    
@login_required
def update_profile(request):
    """
    Handle profile update via AJAX
    """
    if request.method == 'POST':
        try:
            user = request.user
            
            # Update basic fields
            user.full_name = request.POST.get('full_name', user.full_name)
            user.email = request.POST.get('email', user.email)
            user.phone_number = request.POST.get('phone_number', user.phone_number)
            
            # Handle password change
            new_password = request.POST.get('new_password')
            if new_password:
                # Validate password length
                if len(new_password) < 6:
                    return JsonResponse({
                        'success': False,
                        'error': 'Password must be at least 6 characters long'
                    }, status=400)
                
                # Set the new password
                user.set_password(new_password)
            
            # Handle profile image upload
            if 'profile_image' in request.FILES:
                # Delete old profile image if it exists and is not the default
                if user.profile_image and user.profile_image.name != 'profile_images/default_avatar.png':
                    default_storage.delete(user.profile_image.name)
                
                user.profile_image = request.FILES['profile_image']
            
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Profile updated successfully',
                'data': {
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'profile_image_url': user.profile_image.url if user.profile_image else None
                }
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def get_profile_data(request):
    """
    Get current user profile data for modal
    """
    user = request.user
    
    return JsonResponse({
        'full_name': user.full_name,
        'email': user.email,
        'phone_number': user.phone_number,
        'role': user.get_role_display(),
        'role_value': user.role,
        'address': user.address or '',
        'pan_number': user.pan_number or '',
        'profile_image_url': user.profile_image.url if user.profile_image else None,
        'created_by': user.created_by.full_name if user.created_by else 'System'
    })

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db import transaction
import json
from .models import Driver, Vehicle, CustomUser

@login_required
@require_http_methods(["POST"])
def add_load_driver(request):
    """Add a new driver for a vendor"""
    try:
        with transaction.atomic():
            print("=== ADD DRIVER DEBUG ===")
            print("POST data:", dict(request.POST))
            print("FILES:", dict(request.FILES))
            
            # Get vendor_id from form data
            vendor_id = request.POST.get('vendor_id')
            if not vendor_id:
                return JsonResponse({'success': False, 'error': 'Vendor ID is required'}, status=400)
            
            try:
                vendor = CustomUser.objects.get(id=vendor_id, role='vendor')
            except CustomUser.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid vendor selected'}, status=400)
            
            # Validate required fields
            required_fields = ['full_name', 'phone_number']
            for field in required_fields:
                if not request.POST.get(field):
                    return JsonResponse({'success': False, 'error': f'{field.replace("_", " ").title()} is required'}, status=400)
            
            # Check if phone number already exists
            phone_number = request.POST['phone_number'].strip()
            if Driver.objects.filter(phone_number=phone_number).exists():
                return JsonResponse({'success': False, 'error': 'Driver with this phone number already exists'}, status=400)
            
            # Create driver
            driver_data = {
                'full_name': request.POST['full_name'].strip(),
                'phone_number': phone_number,
                'owner': vendor,
               
                'status': 'active',
                'is_active': True,
                'created_by': request.user,
            }
            
            # Handle file uploads
            file_fields = {
                'profile_photo': request.FILES.get('profile_photo'),
                'pan_document': request.FILES.get('pan_document'),
                'aadhar_document': request.FILES.get('aadhar_document'),
                'license_document': request.FILES.get('license_document'),  # Note: your model has rc_document but form sends license_document
            }
            
            # Map license_document to rc_document if your model expects it
            if 'license_document' in file_fields and file_fields['license_document']:
                driver_data['rc_document'] = file_fields['license_document']
            
            # Add other files
            for field, file_obj in file_fields.items():
                if file_obj and field != 'license_document':  # Skip license_document as we handled it above
                    driver_data[field] = file_obj
            
            driver = Driver.objects.create(**driver_data)
            
            print(f"Driver created successfully: {driver.full_name}")
            
            return JsonResponse({
                'success': True,
                'message': f'Driver {driver.full_name} added successfully!',
                'driver': {
                    'id': driver.id,
                    'full_name': driver.full_name,
                    'phone_number': driver.phone_number,
                    'owner_name': vendor.full_name,
                    'status': driver.status,
                }
            })
            
    except Exception as e:
        print(f"Unexpected error in add_load_driver: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)

@login_required
@require_http_methods(["POST"])
def add_load_vehicle(request):
    """Add a new vehicle for a vendor"""
    try:
        with transaction.atomic():
            print("=== ADD VEHICLE DEBUG ===")
            print("POST data:", dict(request.POST))
            print("FILES:", dict(request.FILES))
            
            # Get vendor_id from form data
            vendor_id = request.POST.get('vendor_id')
            if not vendor_id:
                return JsonResponse({'success': False, 'error': 'Vendor ID is required'}, status=400)
            
            try:
                vendor = CustomUser.objects.get(id=vendor_id, role='vendor')
            except CustomUser.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid vendor selected'}, status=400)
            
            # Validate required fields
            required_fields = ['reg_no', 'vehicle_type']
            for field in required_fields:
                if not request.POST.get(field):
                    return JsonResponse({'success': False, 'error': f'{field.replace("_", " ").title()} is required'}, status=400)
            
            # Check if registration number already exists
            reg_no = request.POST['reg_no'].strip().upper()
            if Vehicle.objects.filter(reg_no=reg_no).exists():
                return JsonResponse({'success': False, 'error': 'Vehicle with this registration number already exists'}, status=400)
            
            # Get vehicle type (from your form it's vehicle_type, but model has type)
            vehicle_type = request.POST['vehicle_type'].strip()
            
            # Create vehicle
            vehicle_data = {
                'reg_no': reg_no,
                'owner': vendor,
                'type': vehicle_type,
                'status': 'active',
            }
            
            # Handle optional load capacity
            load_capacity = request.POST.get('load_capacity', '').strip()
            if load_capacity:
                try:
                    vehicle_data['load_capacity'] = float(load_capacity)
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid load capacity format'}, status=400)
            
            # Handle file uploads
            file_fields = {
                'insurance_document': request.FILES.get('insurance_document'),
                'rc_document': request.FILES.get('rc_document'),
            }
            
            # Map file fields to model fields
            if file_fields['insurance_document']:
                vehicle_data['insurance_doc'] = file_fields['insurance_document']
            if file_fields['rc_document']:
                vehicle_data['rc_doc'] = file_fields['rc_document']
            
            vehicle = Vehicle.objects.create(**vehicle_data)
            
            print(f"Vehicle created successfully: {vehicle.reg_no}")
            
            return JsonResponse({
                'success': True,
                'message': f'Vehicle {vehicle.reg_no} added successfully!',
                'vehicle': {
                    'id': vehicle.id,
                    'reg_no': vehicle.reg_no,
                    'type': vehicle.type,
                    'load_capacity': str(vehicle.load_capacity) if vehicle.load_capacity else '',
                    'owner_name': vendor.full_name,
                    'status': vehicle.status,
                }
            })
            
    except Exception as e:
        print(f"Unexpected error in add_load_vehicle: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        return JsonResponse({
            'success': False,
            'error': f'Server error: {str(e)}'
        }, status=500)
    
@login_required
def trip_management(request):
    """Display trip management page with all assigned/ongoing trips"""
    if not request.user.is_staff:
        return redirect('admin_login')

    # Show trips that have been assigned (not pending)
    trips = Load.objects.filter(
        created_by=request.user,
    ).exclude(
        status='pending'
    ).select_related(
        'driver', 'vehicle', 'vehicle_type', 'customer'
    ).order_by('-updated_at')

    return render(request, 'trip_management.html', {'trips': trips})


@login_required
@require_http_methods(["GET"])
def get_trip_details_api(request, trip_id):
    """API endpoint to get detailed trip information"""
    try:
        load = Load.objects.select_related(
            'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 'driver__owner'
        ).get(id=trip_id, created_by=request.user)
        
        # Progress mapping
        status_progress = {
            'pending': 0,
            'loaded': 12.5,
            'lr_uploaded': 25,
            'first_half_payment': 37.5,
            'in_transit': 50,
            'unloading': 62.5,
            'pod_uploaded': 75,
            'payment_completed': 100,
        }
        progress = status_progress.get(load.trip_status, 0)

        # Payment status
        first_half_paid = load.trip_status not in ['pending', 'loaded', 'lr_uploaded']
        final_payment_paid = load.trip_status == 'payment_completed'

        # Get comments for this trip
        comments = []
        trip_comments = TripComment.objects.filter(load=load).select_related('sender').order_by('created_at')
        for comment in trip_comments:
            comments.append({
                'id': comment.id,
                'comment': comment.comment,
                'sender_name': comment.sender.full_name,
                'sender_type': comment.sender_type,
                'created_at': comment.created_at.isoformat(),
                'timestamp': comment.created_at.strftime('%b %d, %I:%M %p'),
                'is_read': comment.is_read
            })

        data = {
            'id': load.id,
            'load_id': load.load_id,
            'trip_status': load.trip_status,
            'trip_status_display': load.get_trip_status_display(),

            'pickup_location': load.pickup_location,
            'drop_location': load.drop_location,
            'pickup_date': load.pickup_date.strftime('%b %d, %Y'),
            'drop_date': load.drop_date.strftime('%b %d, %Y') if load.drop_date else 'TBD',
            'time': load.time.strftime('%I:%M %p'),

            'vehicle_no': load.vehicle.reg_no if load.vehicle else 'Not Assigned',
            'vehicle_type': load.vehicle_type.name,
            'driver_name': load.driver.full_name if load.driver else 'Not Assigned',
            'driver_phone': load.driver.phone_number if load.driver else 'N/A',

            'customer_name': load.customer.customer_name,
            'customer_phone': load.customer.phone_number,
            'customer_location': load.customer.location or 'N/A',
            'contact_person': load.contact_person_name or load.customer.contact_person_name or 'N/A',
            'contact_person_phone': load.contact_person_phone or load.customer.contact_person_phone or 'N/A',

            'vendor_name': load.driver.owner.full_name if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'Not Assigned',
            'vendor_phone': load.driver.owner.phone_number if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'N/A',

            'first_half_payment': float(load.first_half_payment),
            'final_payment': float(load.final_payment),
            'total_amount': float(load.first_half_payment + load.final_payment),
            'first_half_paid': first_half_paid,
            'final_payment_paid': final_payment_paid,

            'weight': load.weight or 'N/A',
            'material': load.material or 'N/A',
            'distance': 'Calculating...',
            'current_location': 'Location tracking not available',
            'notes': load.notes or '',

            'progress': progress,
            'comments': comments,

            'created_at': load.created_at.strftime('%b %d, %Y %I:%M %p'),
            'last_updated': load.updated_at.strftime('%b %d, %Y %I:%M %p'),
            
            # LR Document
            'lr_document': load.lr_document.url if load.lr_document else None,
            'lr_document_name': load.lr_document.name if load.lr_document else None,
            
            # POD Document
            'pod_document': load.pod_document.url if load.pod_document else None,
            'pod_document_name': load.pod_document.name if load.pod_document else None,
            
            # All timestamps in ISO format for JavaScript parsing
            'pending_at': load.created_at.isoformat() if load.created_at else None,
            'loaded_at': load.loaded_at.isoformat() if hasattr(load, 'loaded_at') and load.loaded_at else None,
            'lr_uploaded_at': load.lr_uploaded_at.isoformat() if load.lr_uploaded_at else None,
            'first_half_payment_at': load.first_half_payment_at.isoformat() if hasattr(load, 'first_half_payment_at') and load.first_half_payment_at else None,
            'in_transit_at': load.in_transit_at.isoformat() if hasattr(load, 'in_transit_at') and load.in_transit_at else None,
            'unloading_at': load.unloading_at.isoformat() if hasattr(load, 'unloading_at') and load.unloading_at else None,
            'pod_uploaded_at': load.pod_uploaded_at.isoformat() if load.pod_uploaded_at else None,
            'payment_completed_at': load.payment_completed_at.isoformat() if hasattr(load, 'payment_completed_at') and load.payment_completed_at else None,
        }

        return JsonResponse({'success': True, 'data': data})

    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error fetching trip details: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["POST"])
def upload_lr_document_api(request, trip_id):
    """Upload LR document and update trip status"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Check if LR is already uploaded
        if load.lr_document:
            return JsonResponse({
                'success': False, 
                'error': 'LR document already uploaded'
            }, status=400)
        
        # Only allow upload if status is 'loaded'
        if load.trip_status != 'loaded':
            return JsonResponse({
                'success': False, 
                'error': 'LR can only be uploaded when trip status is "Loaded"'
            }, status=400)
        
        if 'lr_document' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
        
        lr_document = request.FILES['lr_document']
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if lr_document.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'File must be PDF, JPG, or PNG'}, status=400)
        
        # Validate file size (max 10MB)
        if lr_document.size > 10 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File size must be less than 10MB'}, status=400)
        
        # Save the document
        load.lr_document = lr_document
        load.lr_uploaded_at = timezone.now()
        
        # Update trip status to lr_uploaded
        load.update_trip_status('lr_uploaded', user=request.user)
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': 'LR document uploaded successfully',
            'document_url': load.lr_document.url,
            'document_name': load.lr_document.name
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error uploading LR document: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["GET"])
def view_lr_document_api(request, trip_id):
    """View LR document"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        if not load.lr_document:
            return JsonResponse({'success': False, 'error': 'No LR document found'}, status=404)
        
        # Redirect to the document URL
        return redirect(load.lr_document.url)
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error viewing LR document: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["POST"])
def update_trip_status_api(request, trip_id):
    """Update trip status to next stage with automatic completion of related statuses"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Define status flow
        status_flow = [
            'pending', 'loaded', 'lr_uploaded', 'first_half_payment',
            'in_transit', 'unloading', 'pod_uploaded', 'payment_completed'
        ]
        
        try:
            current_index = status_flow.index(load.trip_status)
        except ValueError:
            return JsonResponse({'success': False, 'error': 'Invalid current trip status'}, status=400)
        
        if current_index >= len(status_flow) - 1:
            return JsonResponse({'success': False, 'error': 'Trip is already at final stage'}, status=400)
        
        next_status = status_flow[current_index + 1]
        
        # For LR uploaded status, check if document exists
        if next_status == 'lr_uploaded':
            if not load.lr_document:
                return JsonResponse({
                    'success': False, 
                    'error': 'Please upload LR document first',
                    'requires_lr_upload': True
                }, status=400)
        
        # For POD uploaded status, check if document exists
        if next_status == 'pod_uploaded':
            if not load.pod_document:
                return JsonResponse({
                    'success': False, 
                    'error': 'Please upload POD document first',
                    'requires_pod_upload': True
                }, status=400)
        
        # Special case: When moving to first_half_payment, also complete in_transit
        if next_status == 'first_half_payment':
            # Update to first_half_payment
            load.update_trip_status('first_half_payment', user=request.user)
            
            # Also mark in_transit as completed if not already
            if not load.in_transit_at:
                load.in_transit_at = timezone.now()
            
            # Set trip_status to show both are completed, but we move to unloading as current
            load.trip_status = 'first_half_payment'
        
        # Special case: When moving to in_transit, also complete first_half_payment
        elif next_status == 'in_transit':
            # Update to in_transit
            load.update_trip_status('in_transit', user=request.user)
            
            # Also mark first_half_payment as completed if not already
            if not load.first_half_payment_at:
                load.first_half_payment_at = timezone.now()
            
            load.trip_status = 'in_transit'
        
        # For other status updates
        else:
            load.update_trip_status(next_status, user=request.user)
        
        # Save the model after all updates
        load.save()

        # Get timestamp for the main status update
        timestamp_fields = {
            'pending': 'pending_at',
            'loaded': 'loaded_at',
            'lr_uploaded': 'lr_uploaded_at',
            'first_half_payment': 'first_half_payment_at',
            'in_transit': 'in_transit_at',
            'unloading': 'unloading_at',
            'pod_uploaded': 'pod_uploaded_at',
            'payment_completed': 'payment_completed_at',
        }

        field_name = timestamp_fields.get(load.trip_status)
        timestamp = getattr(load, field_name) if field_name else load.updated_at
        timestamp_str = timestamp.strftime('%b %d, %I:%M %p') if timestamp else 'Just now'

        return JsonResponse({
            'success': True,
            'message': f'Trip status updated to {load.get_trip_status_display()}',
            'new_status': load.trip_status,
            'new_status_display': load.get_trip_status_display(),
            'timestamp': timestamp_str,
            'special_case': next_status in ['first_half_payment', 'in_transit']
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error updating trip status: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)

@login_required
@require_http_methods(["POST"])
def add_trip_comment_api(request, trip_id):
    """Add a comment to the trip chat"""
    try:
        # Get the load
        load = Load.objects.select_related('driver__owner').get(id=trip_id)
        
        # Check permissions: Only load creator (admin) or assigned vendor can comment
        is_admin = load.created_by == request.user
        is_vendor = (load.driver and 
                    hasattr(load.driver, 'owner') and 
                    load.driver.owner == request.user)
        
        if not (is_admin or is_vendor):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to comment on this trip'
            }, status=403)
        
        # Parse comment from request
        data = json.loads(request.body) if request.body else {}
        comment_text = data.get('comment', '').strip()
        
        if not comment_text:
            return JsonResponse({
                'success': False,
                'error': 'Comment cannot be empty'
            }, status=400)
        
        # Determine sender type
        sender_type = 'admin' if is_admin else 'vendor'
        
        # Create comment
        comment = TripComment.objects.create(
            load=load,
            sender=request.user,
            sender_type=sender_type,
            comment=comment_text
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Comment added successfully',
            'comment': {
                'id': comment.id,
                'sender_name': request.user.full_name,
                'sender_type': sender_type,
                'comment': comment.comment,
                'created_at': comment.created_at.isoformat(),
                'timestamp': comment.created_at.strftime('%b %d, %I:%M %p')
            }
        })
    
    except Load.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trip not found'
        }, status=404)
    except Exception as e:
        print(f"Error adding comment: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': 'Server error while adding comment'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_trip_comments_api(request, trip_id):
    """Get all comments for a trip"""
    try:
        # Get the load
        load = Load.objects.select_related('driver__owner').get(id=trip_id)
        
        # Check permissions
        is_admin = load.created_by == request.user
        is_vendor = (load.driver and 
                    hasattr(load.driver, 'owner') and 
                    load.driver.owner == request.user)
        
        if not (is_admin or is_vendor):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to view these comments'
            }, status=403)
        
        # Get all comments for this load
        comments = TripComment.objects.filter(load=load).select_related('sender').order_by('created_at')
        
        # Mark unread comments as read for current user
        TripComment.objects.filter(
            load=load,
            is_read=False
        ).exclude(
            sender=request.user
        ).update(is_read=True)
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'id': comment.id,
                'sender_name': comment.sender.full_name,
                'sender_type': comment.sender_type,
                'comment': comment.comment,
                'created_at': comment.created_at.isoformat(),
                'timestamp': comment.created_at.strftime('%b %d, %I:%M %p'),
                'is_read': comment.is_read
            })
        
        return JsonResponse({
            'success': True,
            'comments': comments_data
        })
    
    except Load.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trip not found'
        }, status=404)
    except Exception as e:
        print(f"Error getting comments: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Server error while fetching comments'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_unread_comments_count_api(request, trip_id):
    """Get count of unread comments for current user"""
    try:
        load = Load.objects.get(id=trip_id)
        
        # Check permissions
        is_admin = load.created_by == request.user
        is_vendor = (load.driver and 
                    hasattr(load.driver, 'owner') and 
                    load.driver.owner == request.user)
        
        if not (is_admin or is_vendor):
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
        
        # Count unread comments not sent by current user
        unread_count = TripComment.objects.filter(
            load=load,
            is_read=False
        ).exclude(
            sender=request.user
        ).count()
        
        return JsonResponse({
            'success': True,
            'unread_count': unread_count
        })
    
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def close_trip_api(request, trip_id):
    """Mark trip as completed and close it"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        if load.trip_status != 'payment_completed':
            return JsonResponse({
                'success': False,
                'error': 'Can only close trips with completed payment'
            }, status=400)
        
        load.status = 'delivered'
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Trip closed successfully'
        })
        
    except Load.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trip not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    
@login_required
@require_http_methods(["POST"])
def upload_pod_document_api(request, trip_id):
    """Upload POD document and update trip status"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Check if POD is already uploaded
        if load.pod_document:
            return JsonResponse({
                'success': False, 
                'error': 'POD document already uploaded'
            }, status=400)
        
        # Only allow upload if status is 'unloading'
        if load.trip_status != 'unloading':
            return JsonResponse({
                'success': False, 
                'error': 'POD can only be uploaded when trip status is "Unloading"'
            }, status=400)
        
        if 'pod_document' not in request.FILES:
            return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)
        
        pod_document = request.FILES['pod_document']
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if pod_document.content_type not in allowed_types:
            return JsonResponse({'success': False, 'error': 'File must be PDF, JPG, or PNG'}, status=400)
        
        # Validate file size (max 10MB)
        if pod_document.size > 10 * 1024 * 1024:
            return JsonResponse({'success': False, 'error': 'File size must be less than 10MB'}, status=400)
        
        # Save the document
        load.pod_document = pod_document
        load.pod_uploaded_at = timezone.now()
        
        # Update trip status to pod_uploaded
        load.update_trip_status('pod_uploaded', user=request.user)
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': 'POD document uploaded successfully',
            'document_url': load.pod_document.url,
            'document_name': load.pod_document.name
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error uploading POD document: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
def payment_management(request):
    """Display payment management page with all trips and their payment status"""
    if not request.user.is_staff:
        return redirect('admin_login')

    # Show all trips that are not pending (assigned onwards)
    trips = Load.objects.filter(
        created_by=request.user,
    ).exclude(
        status='pending'
    ).select_related(
        'driver', 'vehicle', 'vehicle_type', 'customer'
    ).order_by('-updated_at')

    return render(request, 'payment_management.html', {'trips': trips})


@login_required
@require_http_methods(["GET"])
def get_payment_details_api(request, trip_id):
    """API endpoint to get detailed payment information for a trip"""
    try:
        load = Load.objects.select_related(
            'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 'driver__owner'
        ).get(id=trip_id, created_by=request.user)
        
        # Determine payment status
        first_half_paid = load.trip_status not in ['pending', 'loaded', 'lr_uploaded']
        final_payment_paid = load.trip_status == 'payment_completed'

        # Get payment dates
        first_half_date = None
        final_payment_date = None
        
        if hasattr(load, 'first_half_payment_at') and load.first_half_payment_at:
            first_half_date = load.first_half_payment_at.strftime('%b %d, %Y %I:%M %p')
        
        if hasattr(load, 'payment_completed_at') and load.payment_completed_at:
            final_payment_date = load.payment_completed_at.strftime('%b %d, %Y %I:%M %p')

        data = {
            'id': load.id,
            'load_id': load.load_id,
            'trip_status': load.trip_status,
            'trip_status_display': load.get_trip_status_display(),

            'pickup_location': load.pickup_location,
            'drop_location': load.drop_location,
            'pickup_date': load.pickup_date.strftime('%b %d, %Y'),
            'drop_date': load.drop_date.strftime('%b %d, %Y') if load.drop_date else 'TBD',

            'vehicle_no': load.vehicle.reg_no if load.vehicle else 'Not Assigned',
            'vehicle_type': load.vehicle_type.name,
            'driver_name': load.driver.full_name if load.driver else 'Not Assigned',
            'driver_phone': load.driver.phone_number if load.driver else 'N/A',

            'customer_name': load.customer.customer_name,
            'customer_phone': load.customer.phone_number,

            'vendor_name': load.driver.owner.full_name if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'Not Assigned',
            'vendor_phone': load.driver.owner.phone_number if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'N/A',

            # Payment details
            'first_half_payment': float(load.first_half_payment),
            'final_payment': float(load.final_payment),
            'total_amount': float(load.first_half_payment + load.final_payment),
            'first_half_paid': first_half_paid,
            'final_payment_paid': final_payment_paid,
            'first_half_date': first_half_date,
            'final_payment_date': final_payment_date,

            'notes': load.notes or 'No notes available',
            'created_at': load.created_at.strftime('%b %d, %Y %I:%M %p'),
            'last_updated': load.updated_at.strftime('%b %d, %Y %I:%M %p'),
        }

        return JsonResponse({'success': True, 'data': data})

    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Payment record not found'}, status=404)
    except Exception as e:
        print(f"Error fetching payment details: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_first_half_paid_api(request, trip_id):
    """Mark first half payment as paid"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Check if already paid
        if load.trip_status not in ['pending', 'loaded', 'lr_uploaded']:
            return JsonResponse({
                'success': False,
                'error': 'First half payment is already marked as paid'
            }, status=400)
        
        # Update status to first_half_payment
        load.update_trip_status('first_half_payment', user=request.user)
        
        # Also mark in_transit if not already marked
        if not hasattr(load, 'in_transit_at') or not load.in_transit_at:
            load.in_transit_at = timezone.now()
        
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': 'First half payment marked as paid',
            'payment_date': load.first_half_payment_at.strftime('%b %d, %Y %I:%M %p') if hasattr(load, 'first_half_payment_at') and load.first_half_payment_at else None
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error marking first half payment: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_final_payment_paid_api(request, trip_id):
    """Mark final payment as paid"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Check if POD is uploaded
        if load.trip_status != 'pod_uploaded':
            return JsonResponse({
                'success': False,
                'error': 'Final payment can only be marked after POD is uploaded'
            }, status=400)
        
        # Update status to payment_completed
        load.update_trip_status('payment_completed', user=request.user)
        load.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Final payment marked as paid',
            'payment_date': load.payment_completed_at.strftime('%b %d, %Y %I:%M %p') if hasattr(load, 'payment_completed_at') and load.payment_completed_at else None
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error marking final payment: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


