from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from .models import CustomUser, Customer, Driver, VehicleType, Load, Vehicle, LoadRequest, TripComment, Notification, HoldingCharge, TDSRate,CustomerContactPerson
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from rest_framework.decorators import api_view
import re
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from django.core.files.storage import default_storage
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils import timezone
import traceback
from django.views.decorators.http import require_GET
from django.http import HttpResponse
import os
from django.conf import settings
import secrets
import string
import hashlib
import hmac
from django.core.mail import send_mail
from datetime import timedelta
from .notifications import send_trip_assigned_notification, send_trip_rejected_notification
from django.views.decorators.http import require_POST 

def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person':
            return redirect('admin_dashboard')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            return render(request, 'admin_login.html', {'error': 'Email and password are required.'})

        # Use Django's authenticate function
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            if user.is_staff or user.role == 'admin' or user.role == 'traffic_person':
                login(request, user)
                return redirect('admin_dashboard')
            else:
                return render(request, 'admin_login.html', {'error': 'Access denied. Not an authorized user.'})
        else:
            return render(request, 'admin_login.html', {'error': 'Invalid email or password.'})

    return render(request, 'admin_login.html')


@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')
    # Get statistics based on user role
    if request.user.role == 'traffic_person':
        # Traffic person only sees their own data
        total_loads = Load.objects.filter(created_by=request.user).count()
        pending_loads = Load.objects.filter(created_by=request.user, status='pending').count()
        assigned_loads = Load.objects.filter(created_by=request.user, status='assigned').count()
        completed_loads = Load.objects.filter(created_by=request.user, status='delivered').count()

        context = {
            'user': request.user,
            'total_loads': total_loads,
            'pending_loads': pending_loads,
            'assigned_loads': assigned_loads,
            'completed_loads': completed_loads,
        }
    else:
        # Admin sees all statistics and KPIs
        now = timezone.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Basic counts
        total_users = CustomUser.objects.count()
        staff_count = CustomUser.objects.filter(is_staff=True).count()
        total_loads = Load.objects.count()
        pending_loads = Load.objects.filter(status='pending').count()
        assigned_loads = Load.objects.filter(status='assigned').count()
        completed_loads = Load.objects.filter(status='delivered').count()

        # Deliveries this month
        total_deliveries = Load.objects.filter(payment_completed_at__gte=start_of_month, payment_completed_at__lte=now).count()

        # Active drivers
        active_drivers = Driver.objects.filter(is_active=True).count()

        # Revenue this month (sum of final payment where payment_completed_at in this month)
        revenue_qs = Load.objects.filter(payment_completed_at__gte=start_of_month, payment_completed_at__lte=now)
        revenue_agg = revenue_qs.aggregate(total=Sum('final_payment'))
        revenue_this_month = revenue_agg.get('total') or Decimal('0.00')

        # Fleet utilization
        total_vehicles = Vehicle.objects.count()
        active_vehicles = Vehicle.objects.filter(status='active').count()
        fleet_utilization = round((active_vehicles / total_vehicles) * 100, 2) if total_vehicles else 0

        # Trip status counts for charting
        status_counts_qs = Load.objects.values('trip_status').annotate(count=Count('id'))
        status_counts_map = {item['trip_status']: item['count'] for item in status_counts_qs}
        trip_status_labels = [label for key, label in Load.TRIP_STATUS_CHOICES]
        trip_status_values = [status_counts_map.get(key, 0) for key, label in Load.TRIP_STATUS_CHOICES]

        context = {
            'user': request.user,
            'total_users': total_users,
            'staff_count': staff_count,
            'total_loads': total_loads,
            'pending_loads': pending_loads,
            'assigned_loads': assigned_loads,
            'completed_loads': completed_loads,

            # KPIs
            'total_deliveries': total_deliveries,
            'active_drivers': active_drivers,
            'revenue_this_month': revenue_this_month,
            'fleet_utilization': fleet_utilization,

            # Chart data
            'trip_status_labels': trip_status_labels,
            'trip_status_values': trip_status_values,
            'trip_status_labels_json': json.dumps(trip_status_labels),
            'trip_status_values_json': json.dumps(trip_status_values),
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

    customers = (
        Customer.objects
        .prefetch_related('contacts')
        .order_by('-created_at')
    )

    return render(request, 'customer_list.html', {'customers': customers})


@login_required
@require_http_methods(["POST"])
def add_customer(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    try:
        customer_name = request.POST.get('customerName')
        phone_number = request.POST.get('phoneNumber')
        location = request.POST.get('location')
        
        # Get contact persons arrays
        contact_names = request.POST.getlist('contact_names[]')
        contact_phones = request.POST.getlist('contact_phones[]')

        if not customer_name or not phone_number:
            return JsonResponse({'success': False, 'error': 'Customer name & phone required'}, status=400)

        if Customer.objects.filter(phone_number=phone_number).exists():
            return JsonResponse({'success': False, 'error': 'Phone already exists'}, status=400)

        # Start atomic transaction
        with transaction.atomic():
            customer = Customer.objects.create(
                customer_name=customer_name,
                phone_number=phone_number,
                location=location,
                is_active=True
            )

            contacts_payload = []
            
            # Create contact persons if provided
            for i in range(len(contact_names)):
                name = contact_names[i].strip()
                phone = contact_phones[i].strip()
                
                if name and phone:  # Only create if both are provided
                    contact = CustomerContactPerson.objects.create(
                        customer=customer,
                        name=name,
                        phone_number=phone
                    )
                    contacts_payload.append({
                        'name': contact.name,
                        'phone': contact.phone_number
                    })

            payload = {
                'id': customer.id,
                'name': customer.customer_name,
                'phone': customer.phone_number,
                'location': customer.location or '',
                'contacts': contacts_payload,
                'joinDate': customer.created_at.strftime('%b %d, %Y'),
                'status': 'Active',
                'trips_booked': 0,
                'trips_completed': 0,
                'trips_pending': 0
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
    """Display loads based on user role"""
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')

    # Get loads based on user role
    if request.user.role == 'traffic_person':
        # Traffic person only sees their own pending loads
        loads = Load.objects.filter(
            created_by=request.user,
            status='pending'
        )
    else:
        # Admin sees ALL pending loads from ALL users
        loads = Load.objects.filter(status='pending')

    loads = loads.select_related(
        'customer', 'vehicle_type', 'driver', 'vehicle'
    ).order_by('-created_at')

    tds_rate = TDSRate.objects.first()
    
    # Get customers with their contact persons
    customers = Customer.objects.filter(is_active=True).prefetch_related('contacts').order_by('customer_name')
    vehicle_types = VehicleType.objects.all().order_by('name')

    context = {
        'loads': loads,
        'customers': customers,
        'vehicle_types': vehicle_types,
        'tds_rate': tds_rate.rate if tds_rate else 2,
    }
    return render(request, 'load_list.html', context)

@login_required
@require_http_methods(["GET"])
def load_requests_api(request, load_id):
    """API endpoint to get LoadRequest data for a specific load - accessible to admin and load creator"""
    try:
        # Get the load
        load = Load.objects.get(id=load_id)
        
        # Check permissions: Admin can access any load, traffic person only their own
        if request.user.role == 'traffic_person' and load.created_by != request.user:
            return JsonResponse({
                'error': 'Access denied. You can only view requests for loads you created.'
            }, status=403)
        
        # Admin users (staff or role='admin') can access any load requests
        # Traffic persons can only access their own load requests
        
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


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def accept_load_request(request, load_id, request_id):
    """API to accept a load request directly from admin dashboard"""
    if request.method == "POST":
        try:
            print(f"DEBUG: accept_load_request called - load_id={load_id}, request_id={request_id}")
            
            # Get only pending LoadRequest objects for this load
            loadrequest = get_object_or_404(
                LoadRequest, 
                id=request_id, 
                load_id=load_id, 
                status='pending'
            )
            
            data = json.loads(request.body)
            vehicle_id = data.get('vehicle_id')
            driver_id = data.get('driver_id')
            
            if not vehicle_id or not driver_id:
                return JsonResponse({
                    "success": False, 
                    "message": "Vehicle ID and Driver ID are required"
                }, status=400)
            
            # Get vehicle and driver
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id, owner=loadrequest.vendor)
                driver = Driver.objects.get(id=driver_id, owner=loadrequest.vendor)
            except (Vehicle.DoesNotExist, Driver.DoesNotExist):
                return JsonResponse({
                    "success": False, 
                    "message": "Vehicle or driver not found or does not belong to vendor"
                }, status=404)
            
            # Update load request status
            loadrequest.status = 'accepted'
            loadrequest.save()
            
            # Assign to load
            load = loadrequest.load
            load.vehicle = vehicle
            load.driver = driver
            load.assigned_at = timezone.now()
            load.status = 'assigned'
            
            # Update trip status to "confirmed" (vendor has accepted and assigned)
            load.update_trip_status('confirmed', user=request.user, send_notification=True)
            
            # ✅ SEND FIREBASE + DB NOTIFICATION TO VENDOR
            notification, success = send_trip_assigned_notification(
                vendor=loadrequest.vendor, 
                load=load, 
                vehicle=vehicle, 
                driver=driver
            )
            
            # Reject other pending requests for this load
            rejected_requests = LoadRequest.objects.filter(
                load=load, 
                status='pending'
            ).exclude(id=request_id)
            rejected_requests.update(status='rejected')
            
            # Send rejection notifications
            for req in rejected_requests:
                try:
                    send_trip_rejected_notification(vendor=req.vendor, load=load)
                except:
                    # Fallback DB notification
                    Notification.objects.create(
                        recipient=req.vendor,
                        notification_type='trip_rejected',
                        title="Trip Request Rejected",
                        message=f"Your request for Load #{load.load_id} has been rejected by admin.",
                        related_trip=load,
                        is_read=False
                    )
            
            return JsonResponse({
                "success": True, 
                "message": "Load assigned successfully! Notification sent to vendor.",
                "data": {
                    "load_id": load.load_id,
                    "vendor_name": loadrequest.vendor.full_name,
                    "vendor_phone": loadrequest.vendor.phone_number,
                    "vehicle_reg_no": vehicle.reg_no,
                    "driver_name": driver.full_name,
                    "trip_status": load.trip_status,
                }
            }, status=200)
            
        except LoadRequest.DoesNotExist:
            return JsonResponse({
                "success": False, 
                "message": "Load request not found or already processed"
            }, status=404)
        except Exception as e:
            print(f"Error in accept_load_request: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                "success": False, 
                "message": f"Error: {str(e)}"
            }, status=500)

# ✅ FIXED: accept_load_request_with_assignment view
@csrf_exempt
@login_required
@require_http_methods(["POST"])
def accept_load_request_with_assignment(request, load_id, request_id):
    """Alternative accept endpoint with transaction safety"""
    try:
        load = get_object_or_404(Load, id=load_id, created_by=request.user)
        loadrequest = get_object_or_404(LoadRequest, id=request_id, load=load, status='pending')
        
        data = json.loads(request.body)
        vehicle_id = data.get('vehicle_id')
        driver_id = data.get('driver_id')
        
        if not vehicle_id or not driver_id:
            return JsonResponse({
                "success": False, 
                "error": "Please select vehicle and driver"
            }, status=400)
        
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, owner=loadrequest.vendor)
        driver = get_object_or_404(Driver, id=driver_id, owner=loadrequest.vendor)
        
        with transaction.atomic():
            # Assign load
            load.driver = driver
            load.vehicle = vehicle
            load.status = 'assigned'
            load.assigned_at = timezone.now()
            load.trip_status = 'confirmed'  # Update trip status to confirmed
            load.save()
            
            # Accept request
            loadrequest.status = 'accepted'
            loadrequest.save()
            
            # ✅ SEND NOTIFICATION
            send_trip_assigned_notification(
                vendor=loadrequest.vendor, 
                load=load, 
                vehicle=vehicle, 
                driver=driver
            )
            
            # Reject other requests
            LoadRequest.objects.filter(
                load=load, 
                status='pending'
            ).exclude(id=request_id).update(status='rejected')
        
        return JsonResponse({
            "success": True, 
            "message": "Load assigned successfully!",
            "driver_name": driver.full_name,
            "vehicle_reg": vehicle.reg_no
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "error": str(e)
        }, status=500)

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

            # =========================
            # 1. Customer
            # =========================
            customer_id = request.POST.get('customer')
            if not customer_id:
                return JsonResponse({'success': False, 'error': 'Customer is required'}, status=400)

            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid customer'}, status=400)

            # =========================
            # 2. Vehicle Type
            # =========================
            vehicle_type_id = request.POST.get('vehicleType')
            if not vehicle_type_id:
                return JsonResponse({'success': False, 'error': 'Vehicle type is required'}, status=400)

            try:
                vehicle_type = VehicleType.objects.get(id=vehicle_type_id)
            except VehicleType.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid vehicle type'}, status=400)

            # =========================
            # 3. Locations
            # =========================
            pickup_location = request.POST.get('pickupLocation', '').strip()
            drop_location = request.POST.get('dropLocation', '').strip()

            if not pickup_location or not drop_location:
                return JsonResponse(
                    {'success': False, 'error': 'Both pickup & drop locations are required'},
                    status=400
                )

            # =========================
            # 4. Dates
            # =========================
            pickup_date_str = request.POST.get('pickupDate')
            if not pickup_date_str:
                return JsonResponse({'success': False, 'error': 'Pickup date is required'}, status=400)

            try:
                pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid pickup date format'}, status=400)

            drop_date = None
            drop_date_str = request.POST.get('dropDate', '').strip()
            if drop_date_str:
                try:
                    drop_date = datetime.strptime(drop_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid drop date format'}, status=400)

            # =========================
            # 5. Time (Optional)
            # =========================
            time_obj = None
            time_str = request.POST.get('time', '').strip()
            if time_str:
                try:
                    time_obj = datetime.strptime(time_str, '%I:%M %p').time()
                except ValueError:
                    return JsonResponse(
                        {'success': False, 'error': 'Invalid time format. Use: 02:30 PM'},
                        status=400
                    )

            # =========================
            # 6. Total Trip Amount
            # =========================
            total_amount_str = request.POST.get('total_amount', '').replace(',', '').strip()

            if total_amount_str:
                try:
                    total_amount = Decimal(total_amount_str)
                    if total_amount <= 0:
                        return JsonResponse(
                            {'success': False, 'error': 'Amount must be greater than 0'},
                            status=400
                        )
                except:
                    return JsonResponse(
                        {'success': False, 'error': 'Invalid amount format'},
                        status=400
                    )
            else:
                total_amount = Decimal('0.00')

            final_payment = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # =========================
            # 7. First & Second Payment
            # =========================
            first_half_str = request.POST.get('first_half_payment', '').replace(',', '').strip()
            second_half_str = request.POST.get('second_half_payment', '').replace(',', '').strip()

            if total_amount > 0:
                # First half
                if first_half_str:
                    try:
                        first_half_payment = Decimal(first_half_str).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                    except:
                        first_half_payment = (total_amount * Decimal('0.90')).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                else:
                    first_half_payment = (total_amount * Decimal('0.90')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )

                # Second half
                if second_half_str:
                    try:
                        second_half_payment = Decimal(second_half_str).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                    except:
                        second_half_payment = (total_amount * Decimal('0.10')).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                else:
                    second_half_payment = (total_amount * Decimal('0.10')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
            else:
                first_half_payment = Decimal('0.00')
                second_half_payment = Decimal('0.00')

            # =========================
            # 8. Optional Fields
            # =========================
            contact_person_name = request.POST.get('contactPersonName', '').strip() or None
            contact_person_phone = request.POST.get('contactPersonPhone', '').strip() or None
            weight = request.POST.get('weight', '').strip() or None
            material = request.POST.get('material', '').strip() or None
            notes = request.POST.get('notes', '').strip() or None
            apply_tds = request.POST.get('apply_tds') == 'on' and total_amount > 0

            # =========================
            # 9. Create Load
            # =========================
            load = Load.objects.create(
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
                apply_tds=apply_tds,

                price_per_unit=total_amount,
                final_payment=final_payment,
                first_half_payment=first_half_payment,
                second_half_payment=second_half_payment,

                created_by=request.user,
                status='pending',
                trip_status='pending'
            )

            # =========================
            # 10. Success Response
            # =========================
            return JsonResponse({
                'success': True,
                'message': f'Load {load.load_id} created successfully!',
                'load': {
                    'id': load.id,
                    'load_id': load.load_id,
                    'price_per_unit': str(load.price_per_unit),
                    'final_payment': str(load.final_payment),
                    'first_half_payment': str(load.first_half_payment),
                    'second_half_payment': str(load.second_half_payment),
                    'total_trip_amount': str(load.total_trip_amount),
                    'total_trip_amount_formatted': load.total_trip_amount_formatted,
                }
            })

    except Exception:
        print("=== ADD LOAD ERROR ===")
        traceback.print_exc()
        print("=== END ERROR ===")

        return JsonResponse(
            {'success': False, 'error': 'Failed to create load. Please try again.'},
            status=500
        )

@login_required
@require_GET
def get_customer_contact_persons(request):
    """API endpoint to get all customers with their contact persons"""
    try:
        customers = Customer.objects.filter(is_active=True).prefetch_related('contacts')
        
        contact_persons_dict = {}
        for customer in customers:
            contact_persons = list(customer.contacts.values('id', 'name', 'phone_number'))
            # Add customer's own phone as primary contact
            contact_persons_dict[customer.id] = contact_persons
        
        return JsonResponse({
            'success': True,
            'contact_persons': contact_persons_dict
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
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
    ).order_by('-date_joined')

    return render(request, 'vendor_list.html', {'vendors': vendors})


@login_required
@require_http_methods(["POST"])
def toggle_vendor_block(request, vendor_id):
    try:
        if not request.user.is_staff:
            return JsonResponse(
                {'success': False, 'error': 'Unauthorized'},
                status=403
            )

        vendor = CustomUser.objects.get(id=vendor_id, role='vendor')

        vendor.is_blocked = not vendor.is_blocked
        vendor.save(update_fields=["is_blocked"])

        action = "blocked" if vendor.is_blocked else "unblocked"

        return JsonResponse({
            'success': True,
            'message': f'Vendor {vendor.full_name} has been {action} successfully.',
            'is_blocked': vendor.is_blocked,
            'status': 'Blocked' if vendor.is_blocked else 'Active'
        })

    except CustomUser.DoesNotExist:
        return JsonResponse(
            {'success': False, 'error': 'Vendor not found'},
            status=404
        )

@login_required
@require_http_methods(["POST"])
def add_vendor(request):
    """Add new vendor - handles both AJAX and regular POST"""
    try:
        # Extract fields
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()

        # Validation
        if not full_name:
            return JsonResponse({'success': False, 'error': 'Full name is required.'}, status=400)

        if not phone:
            return JsonResponse({'success': False, 'error': 'Phone number is required.'}, status=400)

        if not email:
            return JsonResponse({'success': False, 'error': 'Email is required.'}, status=400)

        if not password:
            return JsonResponse({'success': False, 'error': 'Password is required.'}, status=400)

        if len(password) < 6:
            return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters long.'}, status=400)

        # Validate phone number format (10 digits)
        if not phone.isdigit() or len(phone) != 10:
            return JsonResponse({'success': False, 'error': 'Phone number must be 10 digits.'}, status=400)

        # Check duplicate phone
        if CustomUser.objects.filter(phone_number=phone).exists():
            return JsonResponse({
                'success': False,
                'error': f'A vendor with phone number {phone} already exists.'
            }, status=400)

        # Check duplicate email
        if CustomUser.objects.filter(email=email).exists():
            return JsonResponse({
                'success': False,
                'error': f'Email {email} is already registered.'
            }, status=400)

        # Optional fields
        address = request.POST.get('address', '').strip() or None
        pan_number = request.POST.get('pan_number', '').strip() or None
        vehicle_number = request.POST.get('vehicle_number', '').strip() or None
        tds_file = request.FILES.get('tds_declaration')
        profile_image = request.FILES.get('profile_image')

        # Validate PAN number if provided
        if pan_number:
            if len(pan_number) != 10:
                return JsonResponse({
                    'success': False,
                    'error': 'PAN number must be 10 characters long.'
                }, status=400)
            
            # Check duplicate PAN
            if CustomUser.objects.filter(pan_number=pan_number).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'PAN number {pan_number} is already registered.'
                }, status=400)

        # Validate vehicle number if provided
        if vehicle_number:
            # Check duplicate vehicle number
            if CustomUser.objects.filter(vehicle_number=vehicle_number).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'Vehicle number {vehicle_number} is already registered.'
                }, status=400)

        # Create vendor
        with transaction.atomic():
            vendor = CustomUser(
                username=None,
                full_name=full_name,
                phone_number=phone,
                email=email.lower(),
                address=address,
                pan_number=pan_number,
                vehicle_number=vehicle_number,
                role='vendor',
                created_by=request.user,
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            vendor.set_password(password)

            if tds_file:
                vendor.tds_declaration = tds_file
            
            if profile_image:
                vendor.profile_image = profile_image

            vendor.save()

        return JsonResponse({
            'success': True,
            'message': f'Vendor "{vendor.full_name}" has been created successfully!',
            'vendor': {
                'id': vendor.id,
                'full_name': vendor.full_name,
                'email': vendor.email,
                'phone_number': vendor.phone_number,
                'address': vendor.address or '-',
                'pan_number': vendor.pan_number or '-',
                'vehicle_number': vendor.vehicle_number or '-',
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
        if not request.user.is_staff:
            return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

        vendor = get_object_or_404(
            CustomUser,
            id=vendor_id,
            role='vendor'
        )

        vendor.is_active = not vendor.is_active
        vendor.save(update_fields=['is_active'])

        return JsonResponse({
            'success': True,
            'message': f'Vendor "{vendor.full_name}" has been {"activated" if vendor.is_active else "deactivated"} successfully.',
            'is_active': vendor.is_active
        })
    except Http404:
        return JsonResponse({'success': False, 'error': 'Vendor not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Failed to update vendor status: {str(e)}'}, status=500)


@login_required
def vehicle_list(request):
    if not request.user.is_staff:
        return redirect('admin_login')

    # Vehicles: still only those whose owner was created by this admin
    vehicles = Vehicle.objects.select_related('owner').order_by('-id')

    # Vendors: ALL active vendors (role='vendor')
    vendors = CustomUser.objects.filter(role='vendor', is_active=True).order_by('full_name')
    
    # Vehicle types from VehicleType model
    vehicle_types = VehicleType.objects.all().order_by('name')

    return render(request, 'vehicle_list.html', {
        'vehicles': vehicles,
        'vendors': vendors,
        'vehicle_types': vehicle_types  # Add this
    })

@login_required
@require_POST
def add_vehicle(request):
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    try:
        reg_no = request.POST.get('reg_no')
        owner_id = request.POST.get('owner')
        vehicle_type = request.POST.get('type')
        load_capacity = request.POST.get('load_capacity')
        location = request.POST.get('location')
        to_locations_json = request.POST.get('to_locations')
        
        # Parse to_locations if provided
        to_locations = []
        if to_locations_json:
            try:
                to_locations = json.loads(to_locations_json)
            except json.JSONDecodeError:
                pass
        
        # Create vehicle
        vehicle = Vehicle(
            reg_no=reg_no,
            owner_id=owner_id,
            type=vehicle_type,
            load_capacity=load_capacity if load_capacity else None,
            location=location if location else None,
            to_location=to_locations
        )
        
        # Handle file uploads
        if 'insurance_doc' in request.FILES:
            vehicle.insurance_doc = request.FILES['insurance_doc']
        if 'rc_doc' in request.FILES:
            vehicle.rc_doc = request.FILES['rc_doc']
        
        vehicle.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Vehicle added successfully',
            'vehicle': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': vehicle.owner.full_name,
                'type': vehicle.type,
            },
            'vehicle_data': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': vehicle.owner.full_name,
                'owner_phone': vehicle.owner.phone_number,
                'type': vehicle.type,
                'load_capacity': str(vehicle.load_capacity) if vehicle.load_capacity else '',
                'location': vehicle.location or '',
                'to_locations': vehicle.to_location,
                'hasInsurance': bool(vehicle.insurance_doc),
                'hasRC': bool(vehicle.rc_doc),
                'status': vehicle.status,
                'status_label': vehicle.get_status_display()
            }
        })
        
    except IntegrityError:
        return JsonResponse({'success': False, 'error': 'Vehicle with this registration number already exists'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

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
    """Display trip management page for admin or traffic person"""
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')

    # Get trips based on user role
    if request.user.role == 'traffic_person':
        # Traffic person only sees their own trips
        trips = Load.objects.filter(
            created_by=request.user
        ).exclude(
            status='pending'
        )
    else:
        # Admin sees ALL trips from ALL users
        trips = Load.objects.exclude(status='pending')

    trips = trips.select_related(
        'driver', 'vehicle', 'vehicle_type', 'customer', 'created_by'
    ).order_by('-updated_at')

    return render(request, 'trip_management.html', {'trips': trips})

@api_view(['POST'])
def update_trip_location(request, trip_id):
    """
    Update current location for a trip
    """
    try:
        load = Load.objects.get(id=trip_id)
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    
    location = request.data.get('location', '').strip()
    
    if not location:
        return JsonResponse({'success': False, 'error': 'Location is required'}, status=400)
    
    # Update the location
    load.current_location = location
    load.updated_at = timezone.now()
    load.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Location updated successfully',
        'updated_at': load.updated_at.isoformat(),
        'location': location
    })

@login_required
@require_http_methods(["GET"])
def get_trip_details_api(request, trip_id):
    """API endpoint to get detailed trip information"""
    try:
        # Admin can access any trip, traffic person only their own
        if request.user.role == 'traffic_person':
            load = Load.objects.select_related(
                'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 'driver__owner'
            ).get(id=trip_id, created_by=request.user)
        else:
            # Admin can access any trip
            load = Load.objects.select_related(
                'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 'driver__owner'
            ).get(id=trip_id)
        
        # Progress mapping
        status_progress = {
            'pending': 0,
            'loaded': 12.5,
            'lr_uploaded': 25,
            'in_transit': 50,
            'unloading': 62.5,
            'pod_uploaded': 75,
            'payment_completed': 100,
            'hold': 75,  # Hold is at same progress as pod_uploaded
        }
        progress = status_progress.get(load.trip_status, 0)

        # Payment status
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

        # Get all holding charges with details
        holding_charges_list = []
        all_holding_charges = load.holding_charge_entries.all().order_by('created_at')
        total_holding_charges = Decimal('0.00')
        
        for charge in all_holding_charges:
            holding_charges_list.append({
                'id': charge.id,
                'amount': float(charge.amount),
                'trip_stage': charge.trip_stage,
                'trip_stage_display': dict(Load.TRIP_STATUS_CHOICES).get(charge.trip_stage, charge.trip_stage),
                'reason': charge.reason,
                'added_by': charge.added_by.full_name if charge.added_by else 'System',
                'created_at': charge.created_at.isoformat(),
                'created_at_display': charge.created_at.strftime('%b %d, %Y %I:%M %p')
            })
            total_holding_charges += charge.amount

        # Get first half payment paid date
        first_half_payment_date = None
        if load.first_half_payment_paid_at:
            first_half_payment_date = load.first_half_payment_paid_at.strftime('%b %d, %Y %I:%M %p')

        data = {
            'id': load.id,
            'load_id': load.load_id,
            'trip_status': load.trip_status,
            'trip_status_display': load.get_trip_status_display(),

            'pickup_location': load.pickup_location,
            'drop_location': load.drop_location,
            'pickup_date': load.pickup_date.strftime('%b %d, %Y'),
            'drop_date': load.drop_date.strftime('%b %d, %Y') if load.drop_date else 'TBD',
            'time': load.time.strftime('%I:%M %p') if load.time else 'Not specified',

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

            # Payment details
            'final_payment': float(load.final_payment),
            'first_half_payment': float(load.first_half_payment or Decimal('0')),
            'second_half_payment': float(load.second_half_payment or Decimal('0')),
            'holding_charges': float(total_holding_charges),
            'holding_charges_list': holding_charges_list,
            'total_amount': float(load.final_payment) + float(total_holding_charges),
            'final_payment_paid': final_payment_paid,
            'holding_charges_added_at': load.holding_charges_added_at.isoformat() if load.holding_charges_added_at else None,
            'holding_charges_added_at_status': load.holding_charges_added_at_status or '',
            
            # First half payment status (ADD THIS)
            'first_half_payment_paid': load.first_half_payment_paid,
            'first_half_payment_paid_at': first_half_payment_date,

            'weight': load.weight or 'N/A',
            'material': load.material or 'N/A',
            'distance': 'Calculating...',
            'current_location': 'Location tracking not available',
            'notes': load.notes or '',
            'current_location': load.current_location or 'N/A',
            

            'progress': progress,
            'comments': comments,

            'created_at': load.created_at.strftime('%b %d, %Y %I:%M %p'),
            'last_updated': load.updated_at.strftime('%b %d, %Y %I:%M %p'),
            
            # Show creator information for admin
            'created_by_name': load.created_by.full_name if load.created_by else 'System',
            'created_by_role': load.created_by.role if load.created_by else 'N/A',
            
            # LR Document
            'lr_document': load.lr_document.url if load.lr_document else None,
            'lr_document_name': load.lr_document.name if load.lr_document else None,
            
            # POD Document
            'pod_document': load.pod_document.url if load.pod_document else None,
            'pod_document_name': load.pod_document.name if load.pod_document else None,
            
            # All timestamps in ISO format for JavaScript parsing
            'pending_at': load.created_at.isoformat() if load.created_at else None,
            'assigned_at': load.assigned_at.isoformat() if load.assigned_at else None,
            'loaded_at': load.loaded_at.isoformat() if load.loaded_at else None,
            'lr_uploaded_at': load.lr_uploaded_at.isoformat() if load.lr_uploaded_at else None,
            'in_transit_at': load.in_transit_at.isoformat() if load.in_transit_at else None,
            'unloading_at': load.unloading_at.isoformat() if load.unloading_at else None,
            'pod_uploaded_at': load.pod_uploaded_at.isoformat() if load.pod_uploaded_at else None,
            'payment_completed_at': load.payment_completed_at.isoformat() if load.payment_completed_at else None,
            'pod_received_at': load.pod_received_at.isoformat() if load.pod_received_at else None,
            'hold_at': load.hold_at.isoformat() if load.hold_at else None,
            'hold_reason': load.hold_reason or '',
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
        load = Load.objects.select_related('driver__owner').get(id=trip_id, created_by=request.user)
        
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
                'error': 'LR can only be uploaded when trip status is "Reach Loading Point"'
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
        previous_status = load.trip_status
        load.lr_document = lr_document
        load.lr_uploaded_at = timezone.now()
        
        # Update trip status to lr_uploaded
        load.update_trip_status('lr_uploaded', user=request.user)
        load.save()
        
        # Send notification to vendor
        if load.driver and load.driver.owner:
            try:
                from .notifications import send_trip_status_update_notification
                send_trip_status_update_notification(
                    vendor=load.driver.owner,
                    load=load,
                    previous_status=previous_status,
                    new_status='lr_uploaded'
                )
            except Exception as e:
                print(f"Error sending LR upload notification: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'LR document uploaded successfully',
            'document_url': load.lr_document.url,
            'document_name': load.lr_document.name,
            'notification_sent': bool(load.driver and load.driver.owner)
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
    """Update trip status - can skip to any status"""
    try:
        import json
        load = Load.objects.select_related('driver__owner').get(id=trip_id, created_by=request.user)
        
        # Get new status from request body
        try:
            body = json.loads(request.body)
            new_status = body.get('new_status')
        except (json.JSONDecodeError, AttributeError):
            new_status = None
        
        # If no status provided, use old behavior (next status)
        if not new_status:
            # Define status flow
            status_flow = [
                'pending', 'loaded', 'lr_uploaded',
                'in_transit', 'unloading', 'pod_uploaded', 'payment_completed'
            ]
            
            try:
                current_index = status_flow.index(load.trip_status)
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid current trip status'}, status=400)
            
            if current_index >= len(status_flow) - 1:
                return JsonResponse({'success': False, 'error': 'Trip is already at final stage'}, status=400)
            
            new_status = status_flow[current_index + 1]
        
        # Validate the new status
        valid_statuses = [
            'pending', 'loaded', 'lr_uploaded',
            'in_transit', 'unloading', 'pod_uploaded', 'payment_completed', 'hold'
        ]
        
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False, 
                'error': f'Invalid status: {new_status}'
            }, status=400)
        
        # Check if status is same as current
        if new_status == load.trip_status:
            return JsonResponse({
                'success': False, 
                'error': f'Trip is already at {load.get_trip_status_display()} status'
            }, status=400)
        
        # For LR uploaded status, check if document exists
        if new_status == 'lr_uploaded':
            if not load.lr_document:
                return JsonResponse({
                    'success': False, 
                    'error': 'Please upload LR document before updating to LR Uploaded status',
                    'requires_lr_upload': True
                }, status=400)
        
        # For POD uploaded status, check if document exists
        if new_status == 'pod_uploaded':
            if not load.pod_document:
                return JsonResponse({
                    'success': False, 
                    'error': 'Please upload POD document before updating to POD Uploaded status',
                    'requires_pod_upload': True
                }, status=400)
        
        # For hold status, require hold reason
        if new_status == 'hold':
            hold_reason = body.get('hold_reason', '').strip()
            if not hold_reason:
                return JsonResponse({
                    'success': False, 
                    'error': 'Hold reason is required when setting status to Hold'
                }, status=400)
            load.hold_reason = hold_reason
        
        # Update to new status
        previous_status = load.trip_status
        load.update_trip_status(new_status, user=request.user)
        
        # Save the model to persist hold_reason
        load.save()
        
        # Send notification to vendor
        if load.driver and hasattr(load.driver, 'owner') and load.driver.owner:
            try:
                send_trip_status_update_notification(
                    vendor=load.driver.owner,
                    load=load,
                    previous_status=previous_status,
                    new_status=new_status
                )
            except Exception as e:
                print(f"Error sending notification: {e}")
                # Don't fail the request if notification fails
        
        # Get timestamp for the main status update
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
        timestamp = getattr(load, field_name) if field_name and hasattr(load, field_name) else load.updated_at
        timestamp_str = timestamp.strftime('%b %d, %I:%M %p') if timestamp else 'Just now'
        
        # Determine the message to show
        status_messages = {
            'pending': 'Trip status updated to Pending',
            'loaded': 'Trip status updated to Reach Loading Point',
            'lr_uploaded': 'LR Uploaded status updated successfully',
            'in_transit': 'Trip status updated to In Transit',
            'unloading': 'Reached unloading point! Ready for POD upload.',
            'pod_uploaded': 'POD uploaded successfully! Ready for final payment.',
            'payment_completed': 'Payment completed successfully! Trip is now complete.',
            'hold': 'Trip has been put on hold.',
        }
        
        message = status_messages.get(new_status, f'Trip status updated to {load.get_trip_status_display()}')

        return JsonResponse({
            'success': True,
            'message': message,
            'new_status': new_status,
            'new_status_display': load.get_trip_status_display(),
            'timestamp': timestamp_str,
            'notification_sent': True,
            'vendor_notified': bool(load.driver and load.driver.owner)
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
        
        # Send notification to the other party
        if is_admin and load.driver and load.driver.owner:
            # Admin commented, notify vendor
            try:
                from .notifications import send_trip_comment_notification
                send_trip_comment_notification(
                    vendor=load.driver.owner,
                    load=load,
                    comment=comment_text,
                    commenter_name=request.user.full_name
                )
            except Exception as e:
                print(f"Error sending comment notification: {e}")
        elif is_vendor and load.created_by:
            # Vendor commented, notify admin
            # You might want to add a separate function for admin notifications
            # For now, we'll just log it
            print(f"Vendor {request.user.full_name} commented on load {load.load_id}")
        
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
        load = Load.objects.select_related('driver__owner').get(id=trip_id, created_by=request.user)
        
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
        previous_status = load.trip_status
        load.pod_document = pod_document
        load.pod_uploaded_at = timezone.now()
        
        # Update trip status to pod_uploaded
        load.update_trip_status('pod_uploaded', user=request.user)
        load.save()
        
        # Send notification to vendor
        if load.driver and load.driver.owner:
            try:
                from .notifications import send_trip_status_update_notification
                send_trip_status_update_notification(
                    vendor=load.driver.owner,
                    load=load,
                    previous_status=previous_status,
                    new_status='pod_uploaded'
                )
            except Exception as e:
                print(f"Error sending POD upload notification: {e}")
        
        return JsonResponse({
            'success': True,
            'message': 'POD document uploaded successfully',
            'document_url': load.pod_document.url,
            'document_name': load.pod_document.name,
            'notification_sent': bool(load.driver and load.driver.owner)
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error uploading POD document: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
def payment_management(request):
    """Display payment management page for admin or traffic person"""
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')

    # Show payments based on user role
    if request.user.role == 'traffic_person':
        # Traffic person only sees their own payments
        trips = Load.objects.filter(
            created_by=request.user,
        ).exclude(
            status='pending'
        ).select_related(
            'driver', 'vehicle', 'vehicle_type', 'customer'
        ).order_by('-updated_at')
    else:
        # Admin sees all payments
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
        # Admin can access any payment, traffic person only their own
        if request.user.role == 'traffic_person':
            load = Load.objects.select_related(
                'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 
                'driver__owner'
            ).get(id=trip_id, created_by=request.user)
        else:
            # Admin can access any payment
            load = Load.objects.select_related(
                'customer', 'driver', 'vehicle', 'vehicle_type', 'created_by', 
                'driver__owner', 
            ).get(id=trip_id)
        
        # Determine payment status
        final_payment_paid = load.trip_status == 'payment_completed'

        # Get payment dates
        final_payment_date = None
        if hasattr(load, 'payment_completed_at') and load.payment_completed_at:
            final_payment_date = load.payment_completed_at.strftime('%b %d, %Y %I:%M %p')
        
        first_half_payment_date = None
        if load.first_half_payment_paid_at:
            first_half_payment_date = load.first_half_payment_paid_at.strftime('%b %d, %Y %I:%M %p')

        # Calculate adjustment
        adjustment_amount = Decimal('0.00')
        adjustment_type = 'none'  # 'increase', 'decrease', or 'none'
        
        if load.confirmed_paid_amount and load.before_payment_amount:
            adjustment_amount = load.confirmed_paid_amount - load.before_payment_amount
            if adjustment_amount > 0:
                adjustment_type = 'increase'
            elif adjustment_amount < 0:
                adjustment_type = 'decrease'

        # Get holding charges
        holding_charges = load.get_total_holding_charges()
        
        # Get holding charges list
        holding_charges_list = []
        for charge in load.holding_charge_entries.all().order_by('-created_at'):
            holding_charges_list.append({
                'id': charge.id,
                'amount': float(charge.amount),
                'trip_stage': charge.trip_stage,
                'trip_stage_display': charge.get_trip_stage_display(),
                'reason': charge.reason,
                'added_by': charge.added_by.full_name if charge.added_by else 'System',
                'created_at': charge.created_at.strftime('%b %d, %Y %I:%M %p'),
                'created_at_display': charge.created_at.strftime('%d %b %Y, %I:%M %p')
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

            'vehicle_no': load.vehicle.reg_no if load.vehicle else 'Not Assigned',
            'vehicle_type': load.vehicle_type.name,
            'driver_name': load.driver.full_name if load.driver else 'Not Assigned',
            'driver_phone': load.driver.phone_number if load.driver else 'N/A',

            'customer_name': load.customer.customer_name,
            'customer_phone': load.customer.phone_number,

            'vendor_name': load.driver.owner.full_name if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'Not Assigned',
            'vendor_phone': load.driver.owner.phone_number if load.driver and hasattr(load.driver, 'owner') and load.driver.owner else 'N/A',

            # Payment details
            'final_payment': float(load.final_payment),
            'total_amount': float(load.final_payment),
            'first_half_payment': float(getattr(load, 'first_half_payment', 0) or 0),
            'second_half_payment': float(getattr(load, 'second_half_payment', 0) or 0),
            'before_amount': float(getattr(load, 'before_payment_amount', 0) or 0),
            'confirmed_amount': float(getattr(load, 'confirmed_paid_amount', 0) or 0),
            'final_payment_paid': final_payment_paid,
            'final_payment_date': final_payment_date,
            
            # First half payment status
            'first_half_payment_paid': load.first_half_payment_paid,
            'first_half_payment_paid_at': first_half_payment_date,
            
            # Payment adjustment info
            'adjustment_amount': float(adjustment_amount),
            'adjustment_type': adjustment_type,
            'adjustment_percentage': float((adjustment_amount / load.before_payment_amount * 100) if load.before_payment_amount > 0 else 0),
            'payment_adjustment_reason': load.payment_adjustment_reason,
            
            # Holding charges
            'holding_charges': float(holding_charges),
            'holding_charges_added_at': load.holding_charges_added_at.strftime('%b %d, %Y %I:%M %p') if load.holding_charges_added_at else None,
            'holding_charges_added_at_status': load.holding_charges_added_at_status,
            'holding_charges_list': holding_charges_list,

            # Show creator information for admin
            'created_by_name': load.created_by.full_name if load.created_by else 'System',
            'created_by_role': load.created_by.role if load.created_by else 'N/A',

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
def mark_final_payment_paid_api(request, trip_id):
    """Mark final payment as paid"""
    try:
        # Admin can access any trip, traffic person only their own
        if request.user.role == 'traffic_person':
            load = Load.objects.select_related('driver__owner').get(id=trip_id, created_by=request.user)
        else:
            # Admin can access any trip
            load = Load.objects.select_related('driver__owner').get(id=trip_id)
        
        # Determine expected before amount (default to second half if first half exists)
        try:
            from decimal import Decimal, ROUND_HALF_UP
            import json
            from django.utils import timezone

            # Calculate total trip amount including holding charges
            total_trip_amount = load.total_trip_amount
            
            # Determine remaining amount before final payment
            remaining_amount = total_trip_amount
            if load.first_half_payment_paid:
                remaining_amount = total_trip_amount - load.first_half_payment
            
            # Read confirmed amount and adjustment reason from POST (form) or JSON body
            confirmed_amount_str = None
            adjustment_reason = None
            
            if request.content_type == 'application/json':
                # JSON request
                try:
                    payload = json.loads(request.body.decode('utf-8') or '{}')
                    confirmed_amount_str = payload.get('confirmed_amount') or payload.get('confirmed_paid_amount')
                    adjustment_reason = payload.get('adjustment_reason')
                except Exception as e:
                    print(f"Error parsing JSON: {e}")
            else:
                # Form data
                confirmed_amount_str = request.POST.get('confirmed_amount') or request.POST.get('confirmed_paid_amount')
                adjustment_reason = request.POST.get('adjustment_reason')

            if confirmed_amount_str:
                confirmed_amount = Decimal(str(confirmed_amount_str)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                # If no confirmed amount provided, use the remaining amount
                confirmed_amount = remaining_amount
            
            # Calculate adjustment
            adjustment = confirmed_amount - remaining_amount
            
            # Only require adjustment reason if there's actually an adjustment
            if adjustment != Decimal('0.00') and not adjustment_reason:
                return JsonResponse({
                    'success': False, 
                    'error': 'adjustment_reason_required',
                    'message': 'Please provide a reason for the payment adjustment'
                }, status=400)
            
            # If no adjustment, clear any previous adjustment reason
            if adjustment == Decimal('0.00'):
                adjustment_reason = None

            # Save previous expected amount and confirmed amount on the load
            load.before_payment_amount = remaining_amount
            load.confirmed_paid_amount = confirmed_amount
            load.payment_adjustment_reason = adjustment_reason
            
            # Mark both payments as paid
            load.first_half_payment_paid = True
            load.first_half_payment_paid_at = timezone.now()
            
            # Save the model
            load.save()

            # Update status to payment_completed WITH notification
            previous_status = load.trip_status
            load.update_trip_status('payment_completed', user=request.user, send_notification=True)

            return JsonResponse({
                'success': True,
                'message': 'Final payment marked as paid',
                'notification_sent': bool(load.driver and load.driver.owner),
                'payment_date': load.payment_completed_at.strftime('%b %d, %Y %I:%M %p') if hasattr(load, 'payment_completed_at') and load.payment_completed_at else None,
                'before_amount': float(remaining_amount),  # What was expected before adjustment
                'confirmed_amount': float(confirmed_amount),  # What was actually paid
                'adjustment': float(adjustment),  # Difference
                'adjustment_reason': adjustment_reason,
                'remaining_amount': 0.00,  # Remaining amount is now 0 after final payment
                'first_half_payment_paid': True,  # Mark first half as paid too
                'first_half_payment_paid_at': load.first_half_payment_paid_at.strftime('%b %d, %Y %I:%M %p') if load.first_half_payment_paid_at else None,
                'total_trip_amount': float(total_trip_amount)  # Total trip amount for reference
            })
        except Exception as e:
            print('Error processing payment amounts:', e)
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': 'Invalid amount provided'}, status=400)
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error marking final payment: {e}")
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)


@login_required
@require_http_methods(["POST"])
def mark_first_half_payment_paid_api(request, trip_id):
    """Mark first half payment as paid"""
    try:
        load = Load.objects.get(id=trip_id, created_by=request.user)
        
        # Check if first half payment exists
        if not load.first_half_payment or load.first_half_payment <= 0:
            return JsonResponse({
                'success': False, 
                'error': 'No first half payment amount set'
            }, status=400)
        
        # Toggle payment status
        if load.first_half_payment_paid:
            # Mark as unpaid
            load.mark_first_half_payment_unpaid()
            message = 'First half payment marked as unpaid'
            is_paid = False
        else:
            # Mark as paid
            load.mark_first_half_payment_paid(user=request.user)
            message = 'First half payment marked as paid'
            is_paid = True
        
        # Calculate remaining amount
        remaining_amount = load.total_trip_amount
        if is_paid:
            remaining_amount = load.total_trip_amount - load.first_half_payment
        
        return JsonResponse({
            'success': True,
            'message': message,
            'is_paid': is_paid,
            'first_half_amount': float(load.first_half_payment),
            'total_amount': float(load.total_trip_amount),
            'remaining_amount': float(remaining_amount),
            'paid_at': load.first_half_payment_paid_at.strftime('%b %d, %Y %I:%M %p') if load.first_half_payment_paid_at else None,
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error marking first half payment: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)




@login_required
@require_http_methods(["POST"])
def add_holding_charges_api(request, trip_id):
    """Add holding charges to a trip with stage and reason tracking"""
    try:
        # Get the load
        if request.user.role == 'traffic_person':
            load = Load.objects.get(id=trip_id, created_by=request.user)
        else:
            load = Load.objects.get(id=trip_id)
        
        # Parse JSON data
        try:
            data = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            data = {}
        
        # Get the amount from request data
        amount = data.get('amount') or request.POST.get('amount', '')
        reason = data.get('reason') or request.POST.get('reason', '')
        trip_stage = data.get('trip_stage') or request.POST.get('trip_stage', load.trip_status)
        
        if not amount:
            return JsonResponse({
                'success': False,
                'error': 'Holding charges amount is required'
            }, status=400)
        
        if not reason:
            return JsonResponse({
                'success': False,
                'error': 'Reason for holding charges is required'
            }, status=400)
        
        try:
            holding_charge_amount = Decimal(str(amount))
            if holding_charge_amount < 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Holding charges cannot be negative'
                }, status=400)
            
            holding_charge_amount = holding_charge_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            return JsonResponse({
                'success': False,
                'error': 'Invalid amount format'
            }, status=400)
        
        # Validate trip stage
        valid_stages = [choice[0] for choice in Load.TRIP_STATUS_CHOICES]
        if trip_stage not in valid_stages:
            trip_stage = load.trip_status
        
        # Create HoldingCharge record with tracking info
        holding_charge = HoldingCharge.objects.create(
            load=load,
            amount=holding_charge_amount,
            trip_stage=trip_stage,
            reason=reason,
            added_by=request.user
        )
        
        # Update load's total holding charges (auto-calculated by HoldingCharge.save())
        load.refresh_from_db()
        
        # Set holding_charges_added_at to earliest charge if not set
        if not load.holding_charges_added_at:
            load.holding_charges_added_at = timezone.now()
            load.holding_charges_added_at_status = trip_stage
            load.save()
        
        # Get all holding charges for this load
        all_charges = load.holding_charge_entries.all().order_by('created_at')
        charges_list = [
            {
                'id': charge.id,
                'amount': float(charge.amount),
                'trip_stage': charge.trip_stage,
                'trip_stage_display': dict(Load.TRIP_STATUS_CHOICES).get(charge.trip_stage, charge.trip_stage),
                'reason': charge.reason,
                'added_by': charge.added_by.full_name if charge.added_by else 'System',
                'created_at': charge.created_at.isoformat(),
                'created_at_display': charge.created_at.strftime('%b %d, %Y %I:%M %p')
            }
            for charge in all_charges
        ]
        
        # Calculate the new total
        new_total = float(load.final_payment) + float(load.get_total_holding_charges())
        
        return JsonResponse({
            'success': True,
            'message': f'Holding charge of ₹{holding_charge_amount:,.2f} added successfully',
            'holding_charge': {
                'id': holding_charge.id,
                'amount': float(holding_charge_amount),
                'trip_stage': trip_stage,
                'trip_stage_display': dict(Load.TRIP_STATUS_CHOICES).get(trip_stage, trip_stage),
                'reason': reason,
                'added_by': request.user.full_name,
                'created_at': holding_charge.created_at.isoformat(),
                'created_at_display': holding_charge.created_at.strftime('%b %d, %Y %I:%M %p')
            },
            'total_holding_charges': float(load.get_total_holding_charges()),
            'total_amount': new_total,
            'all_charges': charges_list
        })
        
    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Trip not found'}, status=404)
    except Exception as e:
        print(f"Error adding holding charges: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_holding_charge_api(request, charge_id):
    """Delete a holding charge record"""
    try:
        # Get the holding charge
        holding_charge = HoldingCharge.objects.select_related('load', 'added_by').get(id=charge_id)
        load = holding_charge.load
        
        # Permission check: only admin, staff, or the person who added the charge
        if not (request.user.is_staff or request.user == holding_charge.added_by or request.user == load.created_by):
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to delete this charge'
            }, status=403)
        
        # Delete the charge
        holding_charge.delete()
        
        # Update load's total holding charges
        load.update_holding_charges_total()
        
        # Get updated charges list
        all_charges = load.holding_charge_entries.all().order_by('created_at')
        charges_list = [
            {
                'id': charge.id,
                'amount': float(charge.amount),
                'trip_stage': charge.trip_stage,
                'trip_stage_display': dict(Load.TRIP_STATUS_CHOICES).get(charge.trip_stage, charge.trip_stage),
                'reason': charge.reason,
                'added_by': charge.added_by.full_name if charge.added_by else 'System',
                'created_at': charge.created_at.isoformat(),
                'created_at_display': charge.created_at.strftime('%b %d, %Y %I:%M %p')
            }
            for charge in all_charges
        ]
        
        # Calculate new total
        new_total = float(load.final_payment) + float(load.get_total_holding_charges())
        
        return JsonResponse({
            'success': True,
            'message': 'Holding charge deleted successfully',
            'total_holding_charges': float(load.get_total_holding_charges()),
            'total_amount': new_total,
            'all_charges': charges_list
        })
        
    except Exception as e:
        print(f"Error deleting holding charge: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': 'Server error'}, status=500)

@login_required
def reassign_trips(request):
    """Display reassign trips page for admin or traffic person"""
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        messages.error(request, "Access denied.")
        return redirect('admin_login')

    # Get trips based on user role
    if request.user.role == 'traffic_person':
        # Traffic person only sees their own trips (any status except pending)
        trips = Load.objects.filter(
            created_by=request.user
        ).exclude(status='pending')
    else:
        # Admin sees ALL trips they created (any status)
        trips = Load.objects.filter(created_by=request.user)

    trips = trips.select_related(
        'driver', 'vehicle', 'vehicle_type', 'customer'
    ).order_by('-created_at')

    # Get traffic persons for reassignment
    traffic_persons = CustomUser.objects.filter(
        role='traffic_person',
        is_active=True
    ).order_by('full_name')

    context = {
        'trips': trips,
        'traffic_persons': traffic_persons,
    }
    return render(request, 'reassign_trips.html', context)


@login_required
@require_http_methods(["POST"])
def reassign_trips_action(request):
    """API endpoint to reassign selected trips to a traffic person"""
    try:
        data = json.loads(request.body)
        trip_ids = data.get('trip_ids', [])
        traffic_person_id = data.get('traffic_person_id')
        note = data.get('note', '')

        if not trip_ids:
            return JsonResponse({'success': False, 'error': 'No trips selected'}, status=400)

        if not traffic_person_id:
            return JsonResponse({'success': False, 'error': 'No traffic person selected'}, status=400)

        try:
            traffic_person = CustomUser.objects.get(
                id=traffic_person_id, 
                role='traffic_person', 
                is_active=True
            )
        except CustomUser.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Invalid traffic person selected'}, status=400)

        # Reassign trips
        reassigned_count = 0
        
        with transaction.atomic():
            for trip_id in trip_ids:
                try:
                    trip = Load.objects.get(id=trip_id)
                    
                    # Update the created_by field to reassign
                    trip.created_by = traffic_person
                    trip.save()
                    reassigned_count += 1
                    
                    # Add note if provided
                    if note:
                        TripComment.objects.create(
                            load=trip,
                            sender=request.user,
                            sender_type='admin',
                            comment=f"Trip reassigned to {traffic_person.full_name}. Note: {note}"
                        )
                        
                except Load.DoesNotExist:
                    continue

        return JsonResponse({
            'success': True,
            'message': f'Successfully reassigned {reassigned_count} trip(s) to {traffic_person.full_name}',
            'reassigned_count': reassigned_count,
        })

    except Exception as e:
        print(f"Error reassigning trips: {e}")
        return JsonResponse({'success': False, 'error': 'Server error while reassigning trips'}, status=500)
    

def forgot_password_view(request):
    """Handle forgot password request"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            return render(request, 'forgot_password.html', {
                'error': 'Please enter your email address'
            })
        
        try:
            # Find user by email
            user = CustomUser.objects.get(email=email)
            
            # Build reset URL - simple user ID based
            reset_url = request.build_absolute_uri(
                f'/reset-password/{user.id}/'
            )
            
            # Send email
            subject = "Password Reset Request - RoadFleet"
            message = f"""
Hello {user.full_name or 'User'},

You requested a password reset for your RoadFleet account.

Please click the link below to reset your password:
{reset_url}

If you didn't request this reset, please ignore this email.

Best regards,
RoadFleet Team
"""
            
            try:
                # Print to console for debugging
                print(f"Sending reset email to: {user.email}")
                print(f"Reset URL: {reset_url}")
                
                # Send actual email
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                
                print(f"Reset email sent successfully to: {user.email}")
                
                return render(request, 'forgot_password.html', {
                    'success': 'Password reset instructions have been sent to your email. Please check your inbox.'
                })
                
            except Exception as e:
                print(f"Email error: {e}")
                return render(request, 'forgot_password.html', {
                    'error': 'Failed to send email. Please try again later.'
                })
                
        except CustomUser.DoesNotExist:
            # Don't reveal whether email exists
            return render(request, 'forgot_password.html', {
                'success': 'If the email exists, password reset instructions have been sent to your email.'
            })
        except Exception as e:
            print(f"Unexpected error: {e}")
            return render(request, 'forgot_password.html', {
                'error': 'An unexpected error occurred. Please try again.'
            })
    
    # GET request - show forgot password form
    return render(request, 'forgot_password.html')

def reset_password_view(request, user_id):
    """Handle password reset - simple user ID based"""
    try:
        print(f"DEBUG: Reset password attempt - user_id: {user_id}")
        
        # Get user
        user = CustomUser.objects.get(id=user_id)
        print(f"DEBUG: Found user: {user.email}")
        
        if request.method == 'POST':
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            
            print(f"DEBUG: POST request - password: {bool(password)}, confirm_password: {bool(confirm_password)}")
            
            if not password or not confirm_password:
                return render(request, 'reset_password.html', {
                    'error': 'Please fill in all fields',
                    'user_id': user_id
                })
            
            if password != confirm_password:
                return render(request, 'reset_password.html', {
                    'error': 'Passwords do not match',
                    'user_id': user_id
                })
            
            if len(password) < 6:
                return render(request, 'reset_password.html', {
                    'error': 'Password must be at least 6 characters long',
                    'user_id': user_id
                })
            
            # Update password
            user.set_password(password)
            user.save()
            
            print(f"DEBUG: Password reset successful for user: {user.email}")
            
            # Send confirmation email
            subject = "Password Reset Successful - RoadFleet"
            message = f"""
Hello {user.full_name or 'User'},

Your RoadFleet password has been successfully reset.

If you did not make this change, please contact support immediately.

Best regards,
RoadFleet Team
"""
            try:
                # Send confirmation email
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                print("DEBUG: Confirmation email sent")
            except Exception as e:
                print(f"DEBUG: Confirmation email error: {e}")
            
            return render(request, 'reset_password.html', {
                'success': 'Password has been reset successfully! You can now login with your new password.',
                'show_login_link': True
            })
        
        # GET request - show reset form
        return render(request, 'reset_password.html', {
            'user_id': user_id
        })
        
    except CustomUser.DoesNotExist:
        print(f"DEBUG: User not found with ID: {user_id}")
        return render(request, 'reset_password.html', {
            'error': 'Invalid reset link'
        })
    except Exception as e:
        print(f"DEBUG: Unexpected error in reset_password_view: {e}")
        return render(request, 'reset_password.html', {
            'error': 'An error occurred. Please try again.'
        })

@login_required
def edit_load(request, load_id):
    """Edit existing load"""
    if not (request.user.is_staff or request.user.role == 'admin' or request.user.role == 'traffic_person'):
        return redirect('admin_login')
    
    try:
        load = Load.objects.get(id=load_id)
        
        # Check permissions: Admin can edit any load, traffic person only their own
        if request.user.role == 'traffic_person' and load.created_by != request.user:
            messages.error(request, "You don't have permission to edit this load.")
            return redirect('load_list')
        
        customers = Customer.objects.filter(is_active=True).order_by('customer_name')
        vehicle_types = VehicleType.objects.all().order_by('name')
        
        context = {
            'load': load,
            'customers': customers,
            'vehicle_types': vehicle_types,
        }
        return render(request, 'edit_load.html', context)
        
    except Load.DoesNotExist:
        messages.error(request, "Load not found.")
        return redirect('load_list')

@login_required
@require_http_methods(["POST"])
def update_load(request, load_id):
    """API endpoint to update load (same logic as add_load)"""
    try:
        load = Load.objects.get(id=load_id)

        # Permission check
        if request.user.role == 'traffic_person' and load.created_by != request.user:
            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

        with transaction.atomic():

            # =========================
            # 1. Customer
            # =========================
            customer_id = request.POST.get('customer')
            if not customer_id:
                return JsonResponse({'success': False, 'error': 'Customer is required'}, status=400)

            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid customer'}, status=400)

            # =========================
            # 2. Vehicle Type
            # =========================
            vehicle_type_id = request.POST.get('vehicleType')
            if not vehicle_type_id:
                return JsonResponse({'success': False, 'error': 'Vehicle type is required'}, status=400)

            try:
                vehicle_type = VehicleType.objects.get(id=vehicle_type_id)
            except VehicleType.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid vehicle type'}, status=400)

            # =========================
            # 3. Locations
            # =========================
            pickup_location = request.POST.get('pickupLocation', '').strip()
            drop_location = request.POST.get('dropLocation', '').strip()

            if not pickup_location or not drop_location:
                return JsonResponse(
                    {'success': False, 'error': 'Both pickup & drop locations are required'},
                    status=400
                )

            # =========================
            # 4. Dates
            # =========================
            pickup_date_str = request.POST.get('pickupDate')
            if not pickup_date_str:
                return JsonResponse({'success': False, 'error': 'Pickup date is required'}, status=400)

            try:
                pickup_date = datetime.strptime(pickup_date_str, '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Invalid pickup date format'}, status=400)

            drop_date = None
            drop_date_str = request.POST.get('dropDate', '').strip()
            if drop_date_str:
                try:
                    drop_date = datetime.strptime(drop_date_str, '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Invalid drop date format'}, status=400)

            # =========================
            # 5. Time (Optional)
            # =========================
            time_obj = None
            time_str = request.POST.get('time', '').strip()
            if time_str:
                try:
                    time_obj = datetime.strptime(time_str, '%I:%M %p').time()
                except ValueError:
                    return JsonResponse(
                        {'success': False, 'error': 'Invalid time format. Use: 02:30 PM'},
                        status=400
                    )

            # =========================
            # 6. Total Trip Amount
            # =========================
            total_amount_str = request.POST.get('total_amount', '').replace(',', '').strip()

            if total_amount_str:
                try:
                    total_amount = Decimal(total_amount_str)
                    if total_amount <= 0:
                        return JsonResponse(
                            {'success': False, 'error': 'Amount must be greater than 0'},
                            status=400
                        )
                except:
                    return JsonResponse(
                        {'success': False, 'error': 'Invalid amount format'},
                        status=400
                    )
            else:
                total_amount = Decimal('0.00')

            final_payment = total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            # =========================
            # 7. First & Second Payment (90/10)
            # =========================
            first_half_str = request.POST.get('first_half_payment', '').replace(',', '').strip()
            second_half_str = request.POST.get('second_half_payment', '').replace(',', '').strip()

            if total_amount > 0:
                # First half
                if first_half_str:
                    try:
                        first_half_payment = Decimal(first_half_str).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                    except:
                        first_half_payment = (total_amount * Decimal('0.90')).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                else:
                    first_half_payment = (total_amount * Decimal('0.90')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )

                # Second half
                if second_half_str:
                    try:
                        second_half_payment = Decimal(second_half_str).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                    except:
                        second_half_payment = (total_amount * Decimal('0.10')).quantize(
                            Decimal('0.01'), rounding=ROUND_HALF_UP
                        )
                else:
                    second_half_payment = (total_amount * Decimal('0.10')).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
            else:
                first_half_payment = Decimal('0.00')
                second_half_payment = Decimal('0.00')

            # =========================
            # 8. Optional Fields
            # =========================
            contact_person_name = request.POST.get('contactPersonName', '').strip() or None
            contact_person_phone = request.POST.get('contactPersonPhone', '').strip() or None
            weight = request.POST.get('weight', '').strip() or None
            material = request.POST.get('material', '').strip() or None
            notes = request.POST.get('notes', '').strip() or None
            apply_tds = request.POST.get('apply_tds') == 'on' and total_amount > 0

            # =========================
            # 9. Update Load
            # =========================
            load.customer = customer
            load.contact_person_name = contact_person_name
            load.contact_person_phone = contact_person_phone
            load.vehicle_type = vehicle_type
            load.pickup_location = pickup_location
            load.drop_location = drop_location
            load.pickup_date = pickup_date
            load.drop_date = drop_date
            load.time = time_obj
            load.weight = weight
            load.material = material
            load.notes = notes
            load.apply_tds = apply_tds

            load.price_per_unit = total_amount
            load.final_payment = final_payment
            load.first_half_payment = first_half_payment
            load.second_half_payment = second_half_payment

            load.save()

            return JsonResponse({
                'success': True,
                'message': f'Load {load.load_id} updated successfully!',
                'load': {
                    'id': load.id,
                    'load_id': load.load_id,
                    'price_per_unit': str(load.price_per_unit),
                    'final_payment': str(load.final_payment),
                    'first_half_payment': str(load.first_half_payment),
                    'second_half_payment': str(load.second_half_payment),
                }
            })

    except Load.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Load not found'}, status=404)

    except Exception:
        print("=== UPDATE LOAD ERROR ===")
        traceback.print_exc()
        print("=== END ERROR ===")

        return JsonResponse(
            {'success': False, 'error': 'Failed to update load. Please try again.'},
            status=500
        )

@login_required
def edit_driver(request, driver_id):
    """Edit existing driver"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    try:
        driver = Driver.objects.get(id=driver_id, created_by=request.user)
        vendors = CustomUser.objects.filter(role='vendor', is_active=True).order_by('full_name')
        
        context = {
            'driver': driver,
            'vendors': vendors,
        }
        return render(request, 'edit_driver.html', context)
        
    except Driver.DoesNotExist:
        messages.error(request, "Driver not found or you don't have permission to edit.")
        return redirect('driver_list')

@login_required
@require_http_methods(["POST"])
def update_driver(request, driver_id):
    """API endpoint to update driver"""
    try:
        driver = Driver.objects.get(id=driver_id, created_by=request.user)
        
        # Validate required fields
        full_name = request.POST.get('fullname', '').strip()
        phone_number = request.POST.get('phonenumber', '').strip()
        owner_id = request.POST.get('owner')
        
        if not full_name:
            return JsonResponse({
                'success': False, 
                'error': 'Full name is required'
            }, status=400)
        
        if not phone_number:
            return JsonResponse({
                'success': False, 
                'error': 'Phone number is required'
            }, status=400)
        
        if not owner_id:
            return JsonResponse({
                'success': False, 
                'error': 'Owner is required'
            }, status=400)
        
        # Check if phone number already exists (excluding current driver)
        if Driver.objects.filter(phone_number=phone_number).exclude(id=driver_id).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Another driver with this phone number already exists'
            }, status=400)
        
        try:
            owner = CustomUser.objects.get(id=owner_id, role='vendor')
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid owner selected'
            }, status=400)
        
        # Update basic fields
        driver.full_name = full_name
        driver.phone_number = phone_number
        driver.owner = owner
        
        # Handle file uploads - only update if new file is provided
        file_fields = {
            'pan_document': request.FILES.get('pan_document'),
            'aadhar_document': request.FILES.get('aadhar_document'),
            'rc_document': request.FILES.get('rc_document'),
        }
        
        for field, file_obj in file_fields.items():
            if file_obj:
                # Delete old file if exists
                old_file = getattr(driver, field)
                if old_file:
                    old_file.delete(save=False)
                setattr(driver, field, file_obj)
            # Check if file should be removed
            elif request.POST.get(f'remove_{field}') == 'true':
                old_file = getattr(driver, field)
                if old_file:
                    old_file.delete(save=False)
                setattr(driver, field, None)  # Set to None to remove the file
        
        driver.save()
        
        return JsonResponse({
            'success': True,
           
            'driver': {
                'id': driver.id,
                'full_name': driver.full_name,
                'phone_number': driver.phone_number,
                'owner_name': owner.full_name,
                'owner_phone': owner.phone_number,
                'hasPan': bool(driver.pan_document),
                'hasAadhar': bool(driver.aadhar_document),
                'hasRC': bool(driver.rc_document),
            }
        })
        
    except Driver.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Driver not found'}, status=404)
    except Exception as e:
        print(f"Error updating driver: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)  # Return actual error for debugging
        }, status=500)

@login_required
def edit_vehicle(request, vehicle_id):
    """Edit existing vehicle"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
        vendors = CustomUser.objects.filter(role='vendor', is_active=True).order_by('full_name')
        
        context = {
            'vehicle': vehicle,
            'vendors': vendors,
        }
        return render(request, 'edit_vehicle.html', context)
        
    except Vehicle.DoesNotExist:
        messages.error(request, "Vehicle not found.")
        return redirect('vehicle_list')

@login_required
@require_http_methods(["POST"])
def update_vehicle(request, vehicle_id):
    """API endpoint to update vehicle"""
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
        
        # Validate required fields
        reg_no = request.POST.get('reg_no', '').strip().upper()
        owner_id = request.POST.get('owner')
        
        if not reg_no:
            return JsonResponse({
                'success': False, 
                'error': 'Registration number is required'
            }, status=400)
        
        if not owner_id:
            return JsonResponse({
                'success': False, 
                'error': 'Owner is required'
            }, status=400)
        
        # Check if registration number already exists (excluding current vehicle)
        if Vehicle.objects.filter(reg_no=reg_no).exclude(id=vehicle_id).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Another vehicle with this registration number already exists'
            }, status=400)
        
        try:
            owner = CustomUser.objects.get(id=owner_id, role='vendor')
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Invalid owner selected'
            }, status=400)
        
        # Update basic fields
        vehicle.reg_no = reg_no
        vehicle.owner = owner
        
        # Handle file uploads - only update if new file is provided
        file_fields = {
            'insurance_doc': request.FILES.get('insurance_doc'),
            'rc_doc': request.FILES.get('rc_doc'),
        }
        
        for field, file_obj in file_fields.items():
            if file_obj:
                # Delete old file if exists
                old_file = getattr(vehicle, field)
                if old_file:
                    old_file.delete(save=False)
                setattr(vehicle, field, file_obj)
            # Check if file should be removed
            elif request.POST.get(f'remove_{field}') == 'true':
                old_file = getattr(vehicle, field)
                if old_file:
                    old_file.delete(save=False)
                setattr(vehicle, field, None)  # Set to None to remove the file
        
        vehicle.save()
        
        return JsonResponse({
            'success': True,
           
            'vehicle': {
                'id': vehicle.id,
                'reg_no': vehicle.reg_no,
                'owner_name': owner.full_name,
                'owner_phone': owner.phone_number,
                'hasInsurance': bool(vehicle.insurance_doc),
                'hasRC': bool(vehicle.rc_doc),
            }
        })
        
    except Vehicle.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vehicle not found'}, status=404)
    except Exception as e:
        print(f"Error updating vehicle: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)  # Return actual error for debugging
        }, status=500)

@login_required
def edit_customer(request, customer_id):
    """Edit existing customer with contact persons"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Get all contact persons for this customer
        contact_persons = CustomerContactPerson.objects.filter(customer=customer)
        
        context = {
            'customer': customer,
            'contact_persons': contact_persons,
        }
        return render(request, 'edit_customer.html', context)
        
    except Customer.DoesNotExist:
        messages.error(request, "Customer not found.")
        return redirect('customer_list')

@login_required
@require_http_methods(["POST"])
def update_customer(request, customer_id):
    """API endpoint to update customer with contact persons"""
    try:
        customer = get_object_or_404(Customer, id=customer_id)
        
        # Validate required fields
        customer_name = request.POST.get('customerName', '').strip()
        phone_number = request.POST.get('phoneNumber', '').strip()
        
        if not customer_name:
            return JsonResponse({
                'success': False, 
                'error': 'Customer name is required'
            }, status=400)
        
        if not phone_number:
            return JsonResponse({
                'success': False, 
                'error': 'Phone number is required'
            }, status=400)
        
        # Check if phone number already exists (excluding current customer)
        if Customer.objects.filter(phone_number=phone_number).exclude(id=customer_id).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Another customer with this phone number already exists'
            }, status=400)
        
        # Start atomic transaction
        with transaction.atomic():
            # Update basic customer fields
            customer.customer_name = customer_name
            customer.phone_number = phone_number
            customer.location = request.POST.get('location', '').strip() or None
            customer.save()
            
            # Delete existing contact persons
            CustomerContactPerson.objects.filter(customer=customer).delete()
            
            # Get new contact persons data
            contact_names = request.POST.getlist('contact_names[]')
            contact_phones = request.POST.getlist('contact_phones[]')
            
            contact_persons = []
            
            # Create new contact persons if provided
            for i in range(len(contact_names)):
                name = contact_names[i].strip()
                phone = contact_phones[i].strip()
                
                if name and phone:  # Only create if both are provided
                    contact = CustomerContactPerson.objects.create(
                        customer=customer,
                        name=name,
                        phone_number=phone
                    )
                    contact_persons.append({
                        'name': contact.name,
                        'phone': contact.phone_number
                    })
        
        return JsonResponse({
            'success': True,
            'message': f'{customer_name} updated successfully!',
            'customer': {
                'id': customer.id,
                'name': customer.customer_name,
                'phone': customer.phone_number,
                'location': customer.location or '',
                'contacts': contact_persons,
                'joinDate': customer.created_at.strftime('%b %d, %Y'),
                'status': 'Active' if customer.is_active else 'Inactive',
                'trips_booked': 0,  # You can update these with actual values
                'trips_completed': 0,
                'trips_pending': 0
            }
        })
        
    except Customer.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Customer not found'}, status=404)
    except Exception as e:
        print(f"Error updating customer: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def edit_vendor(request, vendor_id):
    """Edit existing vendor"""
    if not request.user.is_staff:
        return redirect('admin_login')
    
    try:
        vendor = CustomUser.objects.get(id=vendor_id, role='vendor', created_by=request.user)
        
        context = {
            'vendor': vendor,
        }
        return render(request, 'edit_vendor.html', context)
        
    except CustomUser.DoesNotExist:
        messages.error(request, "Vendor not found.")
        return redirect('vendor_list')

@login_required
@require_http_methods(["POST"])
def update_vendor(request, vendor_id):
    """API endpoint to update vendor"""
    try:
        vendor = CustomUser.objects.get(id=vendor_id, role='vendor', created_by=request.user)
        
        # Validate required fields
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        
        if not full_name:
            return JsonResponse({
                'success': False, 
                'error': 'Full name is required'
            }, status=400)
        
        if not phone:
            return JsonResponse({
                'success': False, 
                'error': 'Phone number is required'
            }, status=400)

        if not email:
            return JsonResponse({
                'success': False, 
                'error': 'Email is required'
            }, status=400)
        
        # Validate phone number format (10 digits)
        if not phone.isdigit() or len(phone) != 10:
            return JsonResponse({'success': False, 'error': 'Phone number must be 10 digits.'}, status=400)

        # Check if phone number already exists (excluding current vendor)
        if CustomUser.objects.filter(phone_number=phone).exclude(id=vendor_id).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Another vendor with this phone number already exists'
            }, status=400)

        # Check if email already exists (excluding current vendor)
        if CustomUser.objects.filter(email=email.lower()).exclude(id=vendor_id).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Another vendor with this email already exists'
            }, status=400)
        
        # Update basic fields
        vendor.full_name = full_name
        vendor.phone_number = phone
        vendor.email = email.lower()
        
        # Validate and update PAN number if provided
        pan_number = request.POST.get('pan_number', '').strip() or None
        if pan_number:
            if len(pan_number) != 10:
                return JsonResponse({
                    'success': False,
                    'error': 'PAN number must be 10 characters long.'
                }, status=400)
            
            # Check duplicate PAN (excluding current vendor)
            if CustomUser.objects.filter(pan_number=pan_number).exclude(id=vendor_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Another vendor with this PAN number already exists'
                }, status=400)
        
        vendor.pan_number = pan_number
        
        # Validate and update vehicle number if provided
        vehicle_number = request.POST.get('vehicle_number', '').strip() or None
        if vehicle_number:
            # Check duplicate vehicle number (excluding current vendor)
            if CustomUser.objects.filter(vehicle_number=vehicle_number).exclude(id=vendor_id).exists():
                return JsonResponse({
                    'success': False, 
                    'error': 'Another vendor with this vehicle number already exists'
                }, status=400)
        
        vendor.vehicle_number = vehicle_number
        vendor.address = request.POST.get('address', '').strip() or None
        
        # Handle password change if provided
        new_password = request.POST.get('password', '').strip()
        if new_password:
            if len(new_password) < 6:
                return JsonResponse({'success': False, 'error': 'Password must be at least 6 characters long.'}, status=400)
            vendor.set_password(new_password)
        
        # Handle profile photo upload
        profile_image = request.FILES.get('profile_image')
        if profile_image:
            # Delete old profile image if exists and is not default
            if vendor.profile_image and vendor.profile_image.name != 'profile_images/default_avatar.png':
                vendor.profile_image.delete(save=False)
            vendor.profile_image = profile_image
        
        # Handle TDS declaration file upload
        tds_declaration = request.FILES.get('tds_declaration')
        if tds_declaration:
            # Delete old TDS file if exists
            if vendor.tds_declaration:
                vendor.tds_declaration.delete(save=False)
            vendor.tds_declaration = tds_declaration
        
        vendor.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Vendor {vendor.full_name} updated successfully!',
            'vendor': {
                'id': vendor.id,
                'full_name': vendor.full_name,
                'email': vendor.email,
                'phone_number': vendor.phone_number,
                'pan_number': vendor.pan_number or '',
                'vehicle_number': vendor.vehicle_number or '',
                'address': vendor.address or '',
            }
        })
        
    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Vendor not found'}, status=404)
    except Exception as e:
        print(f"Error updating vendor: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
    

# assign vendor
@login_required
def get_vendors_list(request):
    """Get list of all vendors for assignment"""
    try:
        vendors = CustomUser.objects.filter(role='vendor', is_active=True).values(
            'id', 'full_name', 'email', 'phone_number', 'address'
        )
        
        vendors_list = list(vendors)
        return JsonResponse({
            'success': True,
            'vendors': vendors_list
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@login_required
def assign_vendor_to_load(request, load_id):
    """Assign a vendor to a load"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False, 
            'error': 'Invalid request method'
        })
    
    try:
        data = json.loads(request.body)
        vendor_id = data.get('vendor_id')
        
        if not vendor_id:
            return JsonResponse({
                'success': False, 
                'error': 'Vendor ID is required'
            })
        
        # Get the load
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Load not found'
            })
        
        # Get the vendor
        try:
            vendor = CustomUser.objects.get(id=vendor_id, role='vendor', is_active=True)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': 'Vendor not found'
            })
        
        # Check if load is already assigned
        if load.status == 'assigned':
            return JsonResponse({
                'success': False, 
                'error': 'Load is already assigned'
            })
        
        # Create a LoadRequest for this vendor
        load_request, created = LoadRequest.objects.get_or_create(
            load=load,
            vendor=vendor,
            defaults={
                'message': f'Manually assigned by admin {request.user.full_name}',
                'status': 'accepted'
            }
        )
        
        if not created:
            # Update existing request
            load_request.status = 'accepted'
            load_request.message = f'Manually assigned by admin {request.user.full_name}'
            load_request.save()
        
        # Update load status to indicate vendor assigned but vehicle/driver not yet selected
        load.status = 'confirmed'
        load.save()
        
        # Send notification to vendor
        notification_message = ""
        try:
            from .notifications import send_trip_assigned_notification
            
            notification, notification_success = send_trip_assigned_notification(
                vendor=vendor,
                load=load,
                vehicle=None,
                driver=None
            )
            
            if notification_success:
                notification_message = " and notification sent to vendor"
        except ImportError as e:
            print(f"❌ Cannot import notifications module: {e}")
            notification_message = " but notification module not available"
        except Exception as e:
            print(f"❌ Error sending assignment notification: {e}")
            notification_message = " but notification failed"
        
        return JsonResponse({
            'success': True,
            'message': f'Vendor {vendor.full_name} assigned successfully{notification_message}',
            'load_id': load.load_id,
            'vendor_name': vendor.full_name,
            'notification_sent': bool(notification_message and "sent" in notification_message)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False, 
            'error': 'Invalid JSON data'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': str(e)
        })


@require_http_methods(["POST"])
def update_pod_received_date(request, trip_id):
    """
    API endpoint to update POD received date and time
    """
    try:
        load = Load.objects.get(id=trip_id)
        
        # Parse request body
        data = json.loads(request.body)
        pod_received_datetime_str = data.get('pod_received_at')
        
        if not pod_received_datetime_str:
            return JsonResponse({
                'success': False,
                'error': 'POD received date and time is required'
            }, status=400)
        
        # Parse the datetime string (format: YYYY-MM-DDTHH:MM)
        try:
            # Convert from local datetime string to datetime object
            pod_received_datetime = datetime.strptime(pod_received_datetime_str, '%Y-%m-%dT%H:%M')
            # Make it timezone aware
            pod_received_datetime = timezone.make_aware(pod_received_datetime)
        except ValueError as e:
            return JsonResponse({
                'success': False,
                'error': f'Invalid date format: {str(e)}'
            }, status=400)
        
        # Update the field
        load.pod_received_at = pod_received_datetime
        load.save()
        
        # Format for display
        formatted_date = pod_received_datetime.strftime('%b %d, %Y %I:%M %p')
        
        return JsonResponse({
            'success': True,
            'message': 'POD received date updated successfully',
            'pod_received_at': formatted_date,
            'pod_received_at_raw': pod_received_datetime.isoformat()
        })
        
    except Load.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Trip not found'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)