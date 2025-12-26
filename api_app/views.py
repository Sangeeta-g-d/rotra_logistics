# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .serializers import RegisterSerializer, VehicleTypeSerializer, VehicleSerializer, DriverSerializer, LoadDetailsSerializer, LoadRequestSerializer, PhoneNumberTokenObtainPairSerializer, TripCommentSerializer
from .serializers import VendorAcceptedLoadDetailsSerializer, VendorTripDetailsSerializer, LRUploadSerializer, PODUploadSerializer, VendorProfileUpdateSerializer, LoadFilterOptionsSerializer
from rest_framework.generics import RetrieveAPIView
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from logistics_app.models import CustomUser, VehicleType, Vehicle, Driver, Load, LoadRequest, TripComment
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from logistics_app.models import PhoneOTP
from .utils import generate_otp, send_otp_fast2sms

# send OTP
class SendOTPAPIView(APIView):
    permission_classes = []

    def post(self, request):
        print("DEBUG: SendOTPAPIView called")
        print("DEBUG: Incoming request data:", request.data)

        phone_number = request.data.get("phone_number")

        if not phone_number:
            print("ERROR: Phone number missing")
            return Response({"error": "Phone number required"}, status=400)

        # Clean phone number
        phone_number = phone_number.replace("+91", "").replace(" ", "")
        print("DEBUG: Cleaned phone number:", phone_number)

        user_exists = CustomUser.objects.filter(phone_number=phone_number).exists()
        print("DEBUG: User exists:", user_exists)

        if not user_exists:
            print("ERROR: User not found for phone number")
            return Response({"error": "User not found"}, status=404)

        otp = generate_otp()

        PhoneOTP.objects.create(
            phone_number=phone_number,
            otp=otp
        )
        print("DEBUG: OTP saved to database")

        send_otp_fast2sms(phone_number, otp)

        print("DEBUG: OTP flow completed successfully")

        return Response({
            "message": "OTP sent successfully"
        }, status=200)




class VerifyOTPAPIView(APIView):
    permission_classes = []

    def post(self, request):
        phone_number = request.data.get("phone_number")
        otp = request.data.get("otp")

        try:
            otp_obj = PhoneOTP.objects.filter(
                phone_number=phone_number,
                otp=otp,
                is_verified=False
            ).latest("created_at")
        except PhoneOTP.DoesNotExist:
            return Response({"error": "Invalid OTP"}, status=400)

        if otp_obj.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        user = CustomUser.objects.get(phone_number=phone_number)

        otp_obj.is_verified = True
        otp_obj.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Login successful",
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "role": user.role,
                "phone_number": user.phone_number,
            }
        }, status=200)



# views.py
@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(APIView):
    permission_classes = [AllowAny]   # Anyone can access
    authentication_classes = []       # No auth required

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            refresh = RefreshToken.for_user(user)

            data = {
                'user_id': user.id,
                'full_name': user.full_name,
                'email': user.email,
                'phone_number': user.phone_number,
                'role': user.role,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'tds_declaration': request.build_absolute_uri(user.tds_declaration.url) if user.tds_declaration else None
            }

            return Response({
                'status': True,
                'message': 'User registered successfully.',
                'data': data
            }, status=status.HTTP_201_CREATED)

        return Response({
            'status': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PhoneNumberTokenObtainPairSerializer(data=request.data)

        if not serializer.is_valid():
            return Response({
                "status": False,
                "message": "Invalid phone number or password.",
                "errors": serializer.errors
            }, status=400)

        return Response(serializer.validated_data, status=200)


@method_decorator(csrf_exempt, name='dispatch')  
class VehicleTypeListView(APIView):
    def get(self,request):
        types = VehicleType.objects.all().order_by('name')
        serializer = VehicleTypeSerializer(types, many=True)
        return Response({
            'status': True,
            'message' : 'Vehicle types retrieved successfully.',
            'data' : serializer.data

        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class AddVehicleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        data["owner"] = request.user.id   # Auto-assign logged-in user

        serializer = VehicleSerializer(data=data)

        if serializer.is_valid():
            serializer.save(owner=request.user)  
            return Response({
                "status": True,
                "message": "Vehicle added successfully!",
                "vehicle": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')    
class AddDriverView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Only vendors can add drivers
        if user.role != "vendor":
            return Response({
                "status": False,
                "message": "Only vendors can add drivers."
            }, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        data["owner"] = user.id      # vendor ID
        data["created_by"] = user.id  # who created

        serializer = DriverSerializer(data=data)

        if serializer.is_valid():
            driver = serializer.save(owner=user, created_by=user)

            return Response({
                "status": True,
                "message": "Driver added successfully.",
                "driver": DriverSerializer(driver).data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "status": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_loads(request):
    # Exclude loads that already have any accepted LoadRequest
    loads = Load.objects.exclude(requests__status='accepted').order_by('-created_at')   # fetch all
    serializer = LoadDetailsSerializer(
        loads, 
        many=True,
        context={"vendor": request.user}  # Pass vendor context
    )

    return Response({
        "status": True,
        "message": "All loads fetched successfully.",
        "data": serializer.data
    }, status=200)

@method_decorator(csrf_exempt, name='dispatch')
class SendVendorRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_id):
        try:
            load = Load.objects.get(id=load_id)
        except Load.DoesNotExist:
            return Response({'status': False, 'message': 'Load not found.'}, 
                            status=status.HTTP_404_NOT_FOUND)

        # Prevent duplicate requests from same vendor
        if LoadRequest.objects.filter(load=load, vendor=request.user).exists():
            return Response({
                'status': False, 
                'message': 'You have already sent a request for this load.'
            }, status=status.HTTP_400_BAD_REQUEST)

        message = request.data.get('message', '').strip()

        load_request = LoadRequest.objects.create(
            load=load,
            vendor=request.user,
            message=message or None
        )

        serializer = LoadRequestSerializer(load_request)
        return Response({
            'status': True,
            'message': 'Request sent successfully!',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_vehicles(request):
    vehicles = Vehicle.objects.all().order_by("-created_at")
    serializer = VehicleSerializer(vehicles, many=True)

    return Response({
        "status": True,
        "message": "Vehicle list fetched successfully.",
        "data": serializer.data
    }, status=200)

@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_vehicle(request, vehicle_id):
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response({
            "status": False,
            "message": "Vehicle not found."
        }, status=404)

    # partial=True so user can update only location
    serializer = VehicleSerializer(vehicle, data=request.data, partial=True)
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": True,
            "message": "Vehicle updated successfully.",
            "data": serializer.data
        }, status=200)

    return Response({
        "status": False,
        "message": "Validation failed.",
        "errors": serializer.errors
    }, status=400)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_vehicle(request, vehicle_id):
    try:
        vehicle = Vehicle.objects.get(id=vehicle_id)
    except Vehicle.DoesNotExist:
        return Response({
            "status": False,
            "message": "Vehicle not found."
        }, status=404)

    vehicle.delete()

    return Response({
        "status": True,
        "message": "Vehicle deleted successfully."
    }, status=200)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_drivers(request):
    drivers = Driver.objects.filter(owner=request.user).order_by("-created_at")
    serializer = DriverSerializer(drivers, many=True)
    
    return Response({
        "status": True,
        "message": "Driver list fetched successfully.",
        "data": serializer.data
    }, status=200)

@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_driver(request, driver_id):
    try:
        driver = Driver.objects.get(id=driver_id, owner=request.user)
    except Driver.DoesNotExist:
        return Response({
            "status": False,
            "message": "Driver not found."
        }, status=404)

    serializer = DriverSerializer(driver, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": True,
            "message": "Driver updated successfully.",
            "data": serializer.data
        }, status=200)

    return Response({
        "status": False,
        "message": "Validation failed.",
        "errors": serializer.errors
    }, status=400)

@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_driver(request, driver_id):
    try:
        driver = Driver.objects.get(id=driver_id, owner=request.user)
    except Driver.DoesNotExist:
        return Response({
            "status": False,
            "message": "Driver not found."
        }, status=404)

    driver.delete()

    return Response({
        "status": True,
        "message": "Driver deleted successfully."
    }, status=200)


@method_decorator(csrf_exempt, name='dispatch')
class SendTripMessage(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, load_id):
        load = get_object_or_404(Load, id=load_id)

        comment_text = request.data.get("comment")
        if not comment_text:
            return Response({"error": "Message cannot be empty"},
                            status=status.HTTP_400_BAD_REQUEST)

        comment_obj = TripComment.objects.create(
            load=load,
            sender=request.user,
            comment=comment_text
        )

        serializer = TripCommentSerializer(comment_obj)
        return Response(
            {"message": "Message sent", "data": serializer.data},
            status=status.HTTP_201_CREATED
        )

@method_decorator(csrf_exempt, name='dispatch')  
class LoadAllMessages(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, load_id):
        load = get_object_or_404(Load, id=load_id)

        messages = TripComment.objects.filter(load=load).order_by("created_at")

        serializer = TripCommentSerializer(messages, many=True)
        return Response(serializer.data, status=200)
    
class VendorOngoingTrips(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = request.user
        
        # Define statuses that indicate a trip is completed/finished
        COMPLETED_STATUSES = [
            'payment_completed',
            'completed',
            'finished',
            'closed'
        ]
        
        # 1️⃣ Loads where vendor has sent a request and it is not rejected
        requested_loads = Load.objects.filter(
            requests__vendor=vendor,
            requests__status__in=["pending", "accepted"]
        ).exclude(
            trip_status__in=COMPLETED_STATUSES  # Exclude completed trips
        ).distinct()

        # 2️⃣ Loads assigned to vendor (vehicle or driver)
        assigned_loads = Load.objects.filter(
            Q(driver__owner=vendor) | Q(vehicle__owner=vendor)
        ).exclude(
            trip_status__in=COMPLETED_STATUSES  # Exclude completed trips
        ).distinct()

        # Combine results
        loads = (requested_loads | assigned_loads).distinct().order_by('-created_at')

        # 👇 IMPORTANT: pass vendor in context so serializer can return request_status
        serializer = LoadDetailsSerializer(
            loads,
            many=True,
            context={"vendor": vendor}
        )

        return Response({
            "status": True,
            "message": "Vendor ongoing trips fetched successfully.",
            "data": serializer.data
        }, status=200)

@method_decorator(csrf_exempt, name='dispatch') 
class VendorAcceptedLoadDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, load_id):
        vendor = request.user

        # Fetch the vendor's request for this load
        load_request = LoadRequest.objects.filter(
            vendor=vendor,
            load_id=load_id,
            status="accepted"
        ).first()

        if not load_request:
            return Response({
                "status": False,
                "message": "This load is not accepted or not assigned to you."
            }, status=400)

        load = load_request.load

        serializer = VendorAcceptedLoadDetailsSerializer(
            load,
            context={"vendor": vendor}
        )

        return Response({
            "status": True,
            "message": "Accepted load details fetched successfully.",
            "data": serializer.data
        }, status=200)

@method_decorator(csrf_exempt, name='dispatch') 
class VendorTripDetailsView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorTripDetailsSerializer
    lookup_field = "id"

    def get_queryset(self):
        vendor = self.request.user
        return Load.objects.filter(requests__vendor=vendor)

@method_decorator(csrf_exempt, name='dispatch')
class VendorLRUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        vendor = request.user
        
        try:
            # First check if load exists
            load = Load.objects.get(id=id)
        except Load.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Load with ID {id} does not exist"
            }, status=404)
        
        # Check ALL possible ways vendor can be authorized
        # 1. Check LoadRequest (vendor sent request - accept ANY status for testing)
        load_request = LoadRequest.objects.filter(
            load=load,
            vendor=vendor,
            # Accept ANY status for now - remove "accepted" filter
        ).first()
        
        # 2. Check if load is assigned to vendor's vehicle
        vehicle_assigned = load.vehicle and load.vehicle.owner == vendor
        
        # 3. Check if load is assigned to vendor's driver
        driver_assigned = load.driver and load.driver.owner == vendor
        
        # Vendor is NOT authorized through any method
        if not load_request and not vehicle_assigned and not driver_assigned:
            return Response({
                "success": False,
                "message": "You are not authorized to upload LR for this load. No request or assignment found."
            }, status=403)
        
        # If we have a load_request, check its status
        if load_request:
            print(f"DEBUG: LoadRequest found with status: {load_request.status}")
            # For now, accept ANY status (pending, accepted, etc.)
            # Remove this check temporarily:
            # if load_request.status != "accepted":
            #     return Response({
            #         "success": False,
            #         "message": f"Your request for this load is {load_request.status}, not accepted"
            #     }, status=403)
        
        # Check if LR is already uploaded
        if load.lr_document:
            return Response({
                "success": False,
                "message": "LR document already uploaded"
            }, status=400)

        # Only allow upload if status is 'loaded'
        if load.trip_status != 'loaded':
            return Response({
                "success": False,
                "message": f"LR can only be uploaded when trip status is 'Loaded'. Current status: {load.trip_status}"
            }, status=400)

        # Check if file is provided
        if 'lr_document' not in request.FILES:
            return Response({
                "success": False,
                "message": "No file provided"
            }, status=400)

        lr_document = request.FILES['lr_document']
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if lr_document.content_type not in allowed_types:
            return Response({
                "success": False,
                "message": "File must be PDF, JPG, or PNG"
            }, status=400)
        
        # Validate file size (max 10MB)
        if lr_document.size > 10 * 1024 * 1024:
            return Response({
                "success": False,
                "message": "File size must be less than 10MB"
            }, status=400)

        try:
            # Save the file to the model
            load.lr_document = lr_document
            load.lr_uploaded_at = timezone.now()
            load.lr_uploaded_by = vendor
            
            # Get LR number if provided
            lr_number = request.data.get("lr_number", "").strip()
            if lr_number:
                load.lr_number = lr_number

            # Update trip status to lr_uploaded
            load.update_trip_status(
                new_status="lr_uploaded",
                user=vendor,
                lr_number=lr_number
            )
            
            load.save()

            return Response({
                "success": True,
                "message": "LR uploaded successfully",
                "data": {
                    "load_id": load.id,
                    "lr_document": load.lr_document.url if load.lr_document else None,
                    "lr_number": load.lr_number,
                    "lr_uploaded_at": load.lr_uploaded_at.isoformat() if load.lr_uploaded_at else None,
                    "trip_status": load.trip_status,
                    "uploaded_by": vendor.full_name,
                    "load_request_status": load_request.status if load_request else "direct_assignment"
                }
            }, status=200)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error uploading LR: {str(e)}"
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class VendorPODUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        vendor = request.user
        
        try:
            load = Load.objects.get(id=id)
        except Load.DoesNotExist:
            return Response({
                "success": False,
                "message": f"Load with ID {id} does not exist"
            }, status=404)
        
        # Check ALL possible ways vendor can be authorized
        load_request = LoadRequest.objects.filter(
            load=load,
            vendor=vendor,
        ).first()
        
        vehicle_assigned = load.vehicle and load.vehicle.owner == vendor
        driver_assigned = load.driver and load.driver.owner == vendor
        
        # Vendor is NOT authorized through any method
        if not load_request and not vehicle_assigned and not driver_assigned:
            return Response({
                "success": False,
                "message": "You are not authorized to upload POD for this load. No request or assignment found."
            }, status=403)
        
        # Check if POD is already uploaded
        if load.pod_document:
            return Response({
                "success": False,
                "message": "POD document already uploaded"
            }, status=400)

        # Define the required workflow sequence
        required_status_sequence = ['loaded', 'lr_uploaded', 'in_transit', 'unloading']
        
        # Get the current status index
        current_status = load.trip_status
        current_index = required_status_sequence.index(current_status) if current_status in required_status_sequence else -1
        
        # Check if current status is valid for POD upload
        if current_status != 'unloading':
            # Provide helpful message about what needs to be completed first
            if current_status == 'loaded':
                return Response({
                    "success": False,
                    "message": "Cannot upload POD yet. LR needs to be uploaded first."
                }, status=400)
            elif current_status == 'lr_uploaded':
                return Response({
                    "success": False,
                    "message": "Cannot upload POD yet. Trip must be 'In Transit' first."
                }, status=400)
            elif current_status == 'in_transit':
                return Response({
                    "success": False,
                    "message": "Cannot upload POD yet. Trip status must be 'Unloading' first."
                }, status=400)
            else:
                # For any other status, show what's expected
                return Response({
                    "success": False,
                    "message": f"Cannot upload POD. Current status is '{current_status}'. Expected workflow: loaded → lr_uploaded → in_transit → unloading → pod_uploaded"
                }, status=400)

        # Check if file is provided
        if 'pod_document' not in request.FILES:
            return Response({
                "success": False,
                "message": "No file provided"
            }, status=400)

        pod_document = request.FILES['pod_document']
        
        # Validate file type
        allowed_types = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
        if pod_document.content_type not in allowed_types:
            return Response({
                "success": False,
                "message": "File must be PDF, JPG, or PNG"
            }, status=400)
        
        # Validate file size (max 10MB)
        if pod_document.size > 10 * 1024 * 1024:
            return Response({
                "success": False,
                "message": "File size must be less than 10MB"
            }, status=400)

        try:
            # Save the file to the model
            load.pod_document = pod_document
            load.pod_uploaded_at = timezone.now()
            load.pod_uploaded_by = vendor
            
            # Get tracking details if provided - store exactly as provided
            tracking_details = request.data.get("tracking_details", "").strip()
            if tracking_details:
                # Store exactly what user provided
                load.tracking_details = tracking_details

            # Update trip status to pod_uploaded
            load.update_trip_status(
                new_status="pod_uploaded",
                user=vendor
            )
            
            load.save()

            return Response({
                "success": True,
                "message": "POD uploaded successfully",
                "data": {
                    "load_id": load.id,
                    "pod_document": load.pod_document.url if load.pod_document else None,
                    "pod_uploaded_at": load.pod_uploaded_at.isoformat() if load.pod_uploaded_at else None,
                    "trip_status": load.trip_status,
                    "tracking_details": load.tracking_details,
                    "uploaded_by": vendor.full_name,
                    "load_request_status": load_request.status if load_request else "direct_assignment"
                }
            }, status=200)

        except Exception as e:
            return Response({
                "success": False,
                "message": f"Error uploading POD: {str(e)}"
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')    
class VendorProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        serializer = VendorProfileUpdateSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "status": True,
                "message": "Profile updated successfully.",
                "data": {
                    "id": user.id,
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "profile_image": request.build_absolute_uri(user.profile_image.url) if user.profile_image else None,
                }
            }, status=status.HTTP_200_OK)

        return Response({
            "status": False,
            "message": "Failed to update profile.",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

@method_decorator(csrf_exempt, name='dispatch')
class LoadFilterOptionsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get all available filter options for loads dynamically from database
        """
        try:
            # Get unique locations (from pickup_location)
            locations = Load.objects.filter(
                pickup_location__isnull=False
            ).exclude(
                pickup_location=''
            ).values_list(
                'pickup_location', flat=True
            ).distinct().order_by('pickup_location')
            
            # Get unique destinations (from drop_location)
            destinations = Load.objects.filter(
                drop_location__isnull=False
            ).exclude(
                drop_location=''
            ).values_list(
                'drop_location', flat=True
            ).distinct().order_by('drop_location')
            
            # Get unique vehicle types
            vehicle_types = VehicleType.objects.all().values_list('name', flat=True).order_by('name')
            
            # Get unique load capacities from weight field
            load_capacities = Load.objects.filter(
                weight__isnull=False
            ).exclude(
                weight=''
            ).values_list(
                'weight', flat=True
            ).distinct().order_by('weight')
            
            # Prepare response data
            data = {
                'locations': list(locations),
                'destinations': list(destinations),
                'vehicle_types': list(vehicle_types),
                'load_capacities': list(load_capacities),
            }
            
            serializer = LoadFilterOptionsSerializer(data)
            
            return Response({
                'status': True,
                'message': 'Filter options retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error retrieving filter options: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')        
class FilteredLoadsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get loads with optional filters
        Use consistent parameter names:
        - from_location (for pickup_location)
        - to_location (for drop_location)
        - vehicle_type
        - load_capacity
        """
        try:
            # Get filter parameters from query params
            from_location = request.GET.get('from_location')
            to_location = request.GET.get('to_location')  # Use this instead of drop_location
            vehicle_type = request.GET.get('vehicle_type')
            load_capacity = request.GET.get('load_capacity')
            pickup_date = request.GET.get('pickup_date')  # Add date filtering
            drop_date = request.GET.get('drop_date')
            
            # Start with all loads
            loads = Load.objects.all()
            
            # Apply filters only if they are provided
            if from_location:
                loads = loads.filter(pickup_location__icontains=from_location)
            
            if to_location:
                loads = loads.filter(drop_location__icontains=to_location)
            
            if vehicle_type:
                # Filter by vehicle type name
                loads = loads.filter(vehicle_type__name__icontains=vehicle_type)
            
            if load_capacity:
                # Exact match for weight since we're using values from dropdown
                loads = loads.filter(weight=load_capacity)

            if pickup_date:
                loads = loads.filter(pickup_date=pickup_date)
            
            if drop_date:
                loads = loads.filter(drop_date=drop_date)
            
            # Order by creation date (newest first)
            loads = loads.order_by('-created_at')
            
            serializer = LoadDetailsSerializer(
                loads, 
                many=True,
                context={"vendor": request.user}
            )
            
            return Response({
                'status': True,
                'message': 'Filtered loads retrieved successfully',
                'data': {
                    'filters_applied': {
                        'from_location': from_location,
                        'to_location': to_location,
                        'vehicle_type': vehicle_type,
                        'load_capacity': load_capacity,
                    },
                    'loads': serializer.data,
                    'total_count': loads.count()
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error filtering loads: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@method_decorator(csrf_exempt, name='dispatch')       
class SaveFCMTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token')
        
        if not fcm_token:
            return Response({
                "status": False,
                "message": "FCM token is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Save token to user
        request.user.fcm_token = fcm_token
        request.user.save()
        
        return Response({
            "status": True,
            "message": "FCM token saved successfully"
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class VendorProfileView(APIView):
    """
    API endpoint to get vendor profile details from CustomUser model only
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user = request.user
            
            # Check if user is a vendor
            if user.role != 'vendor':
                return Response({
                    'status': False,
                    'message': 'Access denied. Vendor role required.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Get profile image URL
            profile_image_url = None
            if user.profile_image and hasattr(user.profile_image, 'url'):
                if user.profile_image.url:
                    # Build absolute URL for the image
                    profile_image_url = request.build_absolute_uri(user.profile_image.url)
            
            # Prepare response data matching your UI design
            profile_data = {
                'status': True,
                'message': 'Profile fetched successfully',
                'data': {
                    # Main profile info (matching your UI)
                    'full_name': user.full_name or '',
                    'email': user.email,
                    'phone_number': user.phone_number or '',
                    
                    # Role info
                    'role': user.role,
                    'role_display': user.get_role_display(),
                    
                    # Profile image
                    'profile_image': profile_image_url,
                    
                    # Additional info from CustomUser
                    'address': user.address or '',
                    'pan_number': user.pan_number or '',
                    
                    # TDS declaration if exists
                    'tds_declaration': request.build_absolute_uri(user.tds_declaration.url) if user.tds_declaration and hasattr(user.tds_declaration, 'url') else None,
                    
                    # Account status
                    'is_active': user.is_active,
                    'date_joined': user.date_joined.strftime('%Y-%m-%d %H:%M:%S') if user.date_joined else None,
                    'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
                    
                    # App version (static - you can make this dynamic from settings)
                    'app_version': 'RoadFleet v2.0.0',
                    'support_contact': '+91 XXXXXXXXXX'  # Add your support contact
                }
            }
            
            return Response(profile_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error fetching profile: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')        
class VendorDashboardCountsDetailedView(APIView):
    """
    Alternative: Count ALL vendor-related loads (requests + assignments)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            vendor = request.user
            
            if vendor.role != 'vendor':
                return Response({
                    'status': False,
                    'message': 'Access denied. Vendor role required.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            from django.db.models import Q
            
            # 1. ACTIVE TRIPS: Loads with ACCEPTED requests
            active_trips_count = Load.objects.filter(
                requests__vendor=vendor,
                requests__status="accepted"
            ).distinct().count()
            
            # 2. NEW PENDING LOADS: Count only new/pending loads related to vendor
            #    - Loads vendor has requested (pending)
            #    - Loads assigned to vendor's vehicles/drivers but still in 'pending' status
            all_vendor_loads_count = Load.objects.filter(
                
                status='pending'
            ).distinct().count()
            
            # 3. (Optional) Count loads by request status
            pending_requests = LoadRequest.objects.filter(
                vendor=vendor,
                status='pending'
            ).count()
            
            accepted_requests = LoadRequest.objects.filter(
                vendor=vendor,
                status='accepted'
            ).count()
            
            rejected_requests = LoadRequest.objects.filter(
                vendor=vendor,
                status='rejected'
            ).count()
            
            return Response({
                'status': True,
                'message': 'Dashboard counts fetched successfully',
                'data': {
                    'active_trips': active_trips_count,
                    'new_loads': all_vendor_loads_count,  # ALL vendor-related loads
                    'counts_by_status': {
                        'pending_requests': pending_requests,
                        'accepted_requests': accepted_requests,
                        'rejected_requests': rejected_requests,
                    }
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error fetching dashboard counts: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')       
class VendorTripsByStatusView(APIView):
    """
    API to filter vendor trips by trip_status
    Uses the specific statuses from your timestamp_fields
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = request.user
        
        # Define allowed trip statuses based on your timestamp_fields
        # These are the statuses BEFORE pod_uploaded and payment_completed
        ALLOWED_STATUSES = [
            'pending',
            'loaded',
            'lr_uploaded', 
            'first_half_payment',
            'in_transit',
            'unloading',
        ]
        
        # Get status from query parameter
        trip_status = request.GET.get('trip_status')
        
        if not trip_status:
            return Response({
                "status": False,
                "message": "trip_status parameter is required. Example: /api/trips/by-status/?trip_status=loaded"
            }, status=400)
        
        # Validate the status
        if trip_status not in ALLOWED_STATUSES:
            return Response({
                "status": False,
                "message": f"Invalid trip_status. Allowed values: {', '.join(ALLOWED_STATUSES)}"
            }, status=400)
        
        # Get loads filtered by specific trip status
        # 1️⃣ Loads where vendor has sent a request and it is not rejected
        requested_loads = Load.objects.filter(
            requests__vendor=vendor,
            requests__status__in=["pending", "accepted"],
            trip_status=trip_status
        ).distinct()

        # 2️⃣ Loads assigned to vendor (vehicle or driver)
        assigned_loads = Load.objects.filter(
            Q(driver__owner=vendor) | Q(vehicle__owner=vendor),
            trip_status=trip_status
        ).distinct()

        # Combine results
        loads = (requested_loads | assigned_loads).distinct().order_by('-created_at')

        # Serialize data with vendor context
        serializer = LoadDetailsSerializer(
            loads,
            many=True,
            context={"vendor": vendor}
        )

        return Response({
            "status": True,
            "message": f"Trips with status '{trip_status}' fetched successfully.",
            "data": {
                "trip_status": trip_status,
                "status_display": self.get_status_display(trip_status),
                "trips": serializer.data,
                "count": loads.count(),
                "has_timestamp_field": trip_status in self.get_timestamp_fields(),
                "timestamp_field": self.get_timestamp_field(trip_status)
            }
        }, status=200)

    def get_status_display(self, status):
        """Convert status code to display name"""
        status_map = {
            'pending': 'Pending',
            'loaded': 'Loaded',
            'lr_uploaded': 'LR Uploaded',
            'first_half_payment': 'First Half Payment',
            'in_transit': 'In Transit',
            'unloading': 'Unloading',
            'pod_uploaded': 'POD Uploaded',
            'payment_completed': 'Payment Completed',
        }
        return status_map.get(status, status.title())
    
    def get_timestamp_fields(self):
        """Return all timestamp fields"""
        return {
            'pending': 'pending_at',
            'loaded': 'loaded_at',
            'lr_uploaded': 'lr_uploaded_at',
            'first_half_payment': 'first_half_payment_at',
            'in_transit': 'in_transit_at',
            'unloading': 'unloading_at',
            'pod_uploaded': 'pod_uploaded_at',
            'payment_completed': 'payment_completed_at',
        }
    
    def get_timestamp_field(self, status):
        """Get the timestamp field name for a status"""
        fields = self.get_timestamp_fields()
        return fields.get(status)

@method_decorator(csrf_exempt, name='dispatch')    
class TripStatusOptionsView(APIView):
    """
    API to get all available trip status options
    Returns only status values in array (excluding pod_uploaded and payment_completed)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Define ongoing statuses only (exclude pod_uploaded and payment_completed)
        STATUS_VALUES = [
            'pending',
            'loaded',
            'lr_uploaded',
            'first_half_payment',
            'in_transit',
            'unloading',
        ]
        
        return Response({
            "status": True,
            "message": "Trip status options fetched successfully",
            "data": STATUS_VALUES  # Just the array of status strings
        }, status=200)

@method_decorator(csrf_exempt, name='dispatch')
class VendorTripHistoryView(APIView):
    """
    API to get vendor's trip history - completed loads only
    Shows pod_uploaded and payment_completed status loads with POD file details
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        vendor = request.user
        
        # Define completed statuses
        COMPLETED_STATUSES = [
            'pod_uploaded',
            'payment_completed',
        ]
        
        # Get loads where vendor has sent a request and it's accepted
        requested_loads = Load.objects.filter(
            requests__vendor=vendor,
            requests__status="accepted",
            trip_status__in=COMPLETED_STATUSES
        ).distinct()

        # Get loads assigned to vendor (vehicle or driver)
        assigned_loads = Load.objects.filter(
            Q(driver__owner=vendor) | Q(vehicle__owner=vendor),
            trip_status__in=COMPLETED_STATUSES
        ).distinct()

        # Combine results
        loads = (requested_loads | assigned_loads).distinct().order_by('-created_at')

        # Get counts by status
        status_counts = {}
        for status in COMPLETED_STATUSES:
            count = Load.objects.filter(
                Q(requests__vendor=vendor, requests__status="accepted") |
                Q(driver__owner=vendor) |
                Q(vehicle__owner=vendor),
                trip_status=status
            ).distinct().count()
            status_counts[status] = count

        # Prepare detailed response with POD file information
        trip_history = []
        
        for load in loads:
            # Get load request info
            load_request = LoadRequest.objects.filter(
                load=load, 
                vendor=vendor
            ).first()
            
            # Build POD file URL
            pod_file_url = None
            if load.pod_document:
                pod_file_url = request.build_absolute_uri(load.pod_document.url)
            
            # Build LR file URL if exists
            lr_file_url = None
            if load.lr_document:
                lr_file_url = request.build_absolute_uri(load.lr_document.url)
            
            # Prepare trip data with POD information
            trip_data = {
                "id": load.id,
                "load_id": load.load_id,
                "pickup_location": load.pickup_location,
                "drop_location": load.drop_location,
                "weight": load.weight,
                "price_per_unit": load.price_per_unit,
                "trip_status": load.trip_status,
                "status_display": self.get_status_display(load.trip_status),
                "pickup_date": load.pickup_date,
                "drop_date": load.drop_date,
                "created_at": load.created_at,
                
                # POD file information
                "pod_uploaded": load.pod_document is not None,
                "pod_file_url": pod_file_url,
                "pod_uploaded_at": load.pod_uploaded_at,
                "pod_uploaded_by": load.pod_uploaded_by.full_name if load.pod_uploaded_by else None,
                "tracking_details": load.tracking_details,
                
                # LR file information
                "lr_uploaded": load.lr_document is not None,
                "lr_file_url": lr_file_url,
                "lr_uploaded_at": load.lr_uploaded_at,
                "lr_number": load.lr_number,
                
                # Vehicle and driver info
                "vehicle_number": load.vehicle.reg_no if load.vehicle else None,
                "driver_name": load.driver.full_name if load.driver else None,
                "driver_phone": load.driver.phone_number if load.driver else None,
                
                # Request status
                "request_status": load_request.status if load_request else "assigned",
                "request_created_at": load_request.created_at if load_request else load.created_at,
                
                # Timeline dates
                "timeline": {
                    "loaded_at": load.loaded_at,
                    "lr_uploaded_at": load.lr_uploaded_at,
                    "in_transit_at": load.in_transit_at,
                    "unloading_at": load.unloading_at,
                    "pod_uploaded_at": load.pod_uploaded_at,
                    "payment_completed_at": load.payment_completed_at,
                }
            }
            trip_history.append(trip_data)

        return Response({
            "status": True,
            "message": "Trip history fetched successfully",
            "data": {
                "trips": trip_history,
                "total_count": loads.count(),
                "status_counts": status_counts,
                "status_display": {
                    'pod_uploaded': 'POD Uploaded',
                    'payment_completed': 'Payment Completed',
                },
                "summary": {
                    "total_completed_trips": sum(status_counts.values()),
                    "pod_uploaded_count": status_counts.get('pod_uploaded', 0),
                    "payment_completed_count": status_counts.get('payment_completed', 0),
                    "trips_with_pod": loads.filter(pod_document__isnull=False).count(),
                    "trips_without_pod": loads.filter(pod_document__isnull=True).count(),
                }
            }
        }, status=200)

    def get_status_display(self, status):
        """Convert status code to display name"""
        status_map = {
            'pending': 'Pending',
            'loaded': 'Loaded',
            'lr_uploaded': 'LR Uploaded',
            'first_half_payment': 'First Half Payment',
            'in_transit': 'In Transit',
            'unloading': 'Unloading',
            'pod_uploaded': 'POD Uploaded',
            'payment_completed': 'Payment Completed',
        }
        return status_map.get(status, status.title())

@method_decorator(csrf_exempt, name='dispatch')
class AcceptLoadRequestView(APIView):
    """
    API endpoint for admin to accept a load request and assign vehicle/driver
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, load_id, request_id):
        try:
            # Get the load request
            load_request = LoadRequest.objects.get(
                id=request_id,
                load_id=load_id,
                status='pending'
            )
            
            # Get the load
            load = load_request.load
            
            # Get vehicle and driver from request data
            vehicle_id = request.data.get('vehicle_id')
            driver_id = request.data.get('driver_id')
            
            if not vehicle_id or not driver_id:
                return Response({
                    'status': False,
                    'message': 'Vehicle ID and Driver ID are required'
                }, status=400)
            
            try:
                # Get vehicle and driver
                vehicle = Vehicle.objects.get(id=vehicle_id, owner=load_request.vendor)
                driver = Driver.objects.get(id=driver_id, owner=load_request.vendor)
                
                # Update load request status
                load_request.status = 'accepted'
                load_request.save()
                
                # Assign vehicle and driver to load
                load.vehicle = vehicle
                load.driver = driver
                load.assigned_at = timezone.now()
                load.status = 'assigned'
                load.save()
                
                # Send notification to vendor
                send_trip_assigned_notification(
                    vendor=load_request.vendor,
                    load=load,
                    vehicle=vehicle,
                    driver=driver
                )
                
                # Reject other pending requests for this load
                LoadRequest.objects.filter(
                    load=load,
                    status='pending'
                ).exclude(
                    id=request_id
                ).update(status='rejected')
                
                # Send rejection notifications to other vendors
                rejected_requests = LoadRequest.objects.filter(
                    load=load,
                    status='rejected'
                ).exclude(id=request_id)
                
                for req in rejected_requests:
                    send_trip_rejected_notification(
                        vendor=req.vendor,
                        load=load
                    )
                
                return Response({
                    'status': True,
                    'message': 'Load assigned successfully',
                    'data': {
                        'load_id': load.load_id,
                        'vendor_name': load_request.vendor.full_name,
                        'vehicle_reg_no': vehicle.reg_no,
                        'driver_name': driver.full_name,
                    }
                }, status=200)
                
            except Vehicle.DoesNotExist:
                return Response({
                    'status': False,
                    'message': 'Vehicle not found or does not belong to vendor'
                }, status=404)
            except Driver.DoesNotExist:
                return Response({
                    'status': False,
                    'message': 'Driver not found or does not belong to vendor'
                }, status=404)
                
        except LoadRequest.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Load request not found or already processed'
            }, status=404)
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class RejectLoadRequestView(APIView):
    """
    API endpoint for admin to reject a load request
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, load_id, request_id):
        try:
            load_request = LoadRequest.objects.get(
                id=request_id,
                load_id=load_id,
                status='pending'
            )
            
            load_request.status = 'rejected'
            load_request.save()
            
            # Send rejection notification
            send_trip_rejected_notification(
                vendor=load_request.vendor,
                load=load_request.load
            )
            
            return Response({
                'status': True,
                'message': 'Load request rejected successfully'
            }, status=200)
            
        except LoadRequest.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Load request not found or already processed'
            }, status=404)
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class UserNotificationsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Get notifications for current user
            notifications = Notification.objects.filter(
                recipient=request.user
            ).order_by('-created_at')
            
            # Prepare response data
            notification_data = []
            for notification in notifications:
                notification_data.append({
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'type': notification.notification_type,
                    'type_display': notification.get_notification_type_display(),
                    'is_read': notification.is_read,
                    'created_at': notification.created_at,
                    'trip_id': notification.related_trip.id if notification.related_trip else None,
                    'trip_load_id': notification.related_trip.load_id if notification.related_trip else None,
                })
            
            # Get unread count
            unread_count = notifications.filter(is_read=False).count()
            
            return Response({
                'status': True,
                'message': 'Notifications fetched successfully',
                'data': {
                    'notifications': notification_data,
                    'unread_count': unread_count,
                    'total_count': notifications.count()
                }
            }, status=200)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error fetching notifications: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class MarkNotificationReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=request.user
            )
            
            notification.is_read = True
            notification.save()
            
            return Response({
                'status': True,
                'message': 'Notification marked as read'
            }, status=200)
            
        except Notification.DoesNotExist:
            return Response({
                'status': False,
                'message': 'Notification not found'
            }, status=404)
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class MarkAllNotificationsReadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Mark all notifications as read for current user
            updated_count = Notification.objects.filter(
                recipient=request.user,
                is_read=False
            ).update(is_read=True)
            
            return Response({
                'status': True,
                'message': f'Marked {updated_count} notifications as read'
            }, status=200)
            
        except Exception as e:
            return Response({
                'status': False,
                'message': f'Error: {str(e)}'
            }, status=500)

@method_decorator(csrf_exempt, name='dispatch')        
class LogoutView(APIView):
    """
    API endpoint to logout vendor by clearing FCM token
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            # Clear the FCM token
            request.user.fcm_token = None
            request.user.save()
            
            # Optional: Add any other logout logic here
            # Example: Invalidate refresh token if needed
            
            return Response({
                "status": True,
                "message": "Logged out successfully. FCM token cleared."
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "status": False,
                "message": f"Error during logout: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)