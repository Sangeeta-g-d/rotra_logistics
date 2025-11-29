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
    
class VehicleTypeListView(APIView):
    def get(self,request):
        types = VehicleType.objects.all().order_by('name')
        serializer = VehicleTypeSerializer(types, many=True)
        return Response({
            'status': True,
            'message' : 'Vehicle types retrieved successfully.',
            'data' : serializer.data

        }, status=status.HTTP_200_OK)
    
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
    loads = Load.objects.all().order_by('-created_at')   # fetch all
    serializer = LoadDetailsSerializer(loads, many=True)

    return Response({
        "status": True,
        "message": "All loads fetched successfully.",
        "data": serializer.data
    }, status=200)


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

        # 1️⃣ Loads where vendor has sent a request and it is not rejected
        requested_loads = Load.objects.filter(
            requests__vendor=vendor,
            requests__status__in=["pending", "accepted"]
        ).distinct()

        # 2️⃣ Loads assigned to vendor
        assigned_loads = Load.objects.filter(
            driver__owner=vendor
        ) | Load.objects.filter(
            vehicle__owner=vendor
        )

        assigned_loads = assigned_loads.distinct()

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
    
class VendorTripDetailsView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorTripDetailsSerializer
    lookup_field = "id"

    def get_queryset(self):
        vendor = self.request.user
        return Load.objects.filter(requests__vendor=vendor)
    
class VendorLRUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        vendor = request.user

        # Verify vendor is owner of this load request
        load = get_object_or_404(
            Load, 
            id=id, 
            requests__vendor=vendor, 
            requests__status="accepted"
        )

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
                "message": "LR can only be uploaded when trip status is 'Loaded'"
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

        return Response({
            "success": True,
            "message": "LR uploaded successfully",
            "lr_document": load.lr_document.url if load.lr_document else None,
            "lr_number": load.lr_number,
            "lr_uploaded_at": load.lr_uploaded_at.isoformat() if load.lr_uploaded_at else None
        }, status=200)


class VendorPODUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, id):
        vendor = request.user

        # Verify vendor is allowed to upload POD
        load = get_object_or_404(
            Load, 
            id=id, 
            requests__vendor=vendor, 
            requests__status="accepted"
        )

        # Check if POD is already uploaded
        if load.pod_document:
            return Response({
                "success": False,
                "message": "POD document already uploaded"
            }, status=400)

        # Only allow upload if status is 'unloading'
        if load.trip_status != 'unloading':
            return Response({
                "success": False,
                "message": "POD can only be uploaded when trip status is 'Unloading'"
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

        # Save the file to the model
        load.pod_document = pod_document
        load.pod_uploaded_at = timezone.now()
        load.pod_uploaded_by = vendor

        # Update trip status to pod_uploaded
        load.update_trip_status(
            new_status="pod_uploaded",
            user=vendor
        )

        return Response({
            "success": True,
            "message": "POD uploaded successfully",
            "pod_document": load.pod_document.url if load.pod_document else None,
            "pod_uploaded_at": load.pod_uploaded_at.isoformat() if load.pod_uploaded_at else None
        }, status=200)
    
class VendorProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        serializer = VendorProfileUpdateSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Vendor profile updated successfully"},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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