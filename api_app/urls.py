# urls.py
from django.urls import path
from .views import RegisterView, LoginView, VehicleTypeListView, AddVehicleView, AddDriverView, get_all_loads, SendVendorRequestView, get_all_vehicles, update_vehicle, delete_vehicle
from .views import *
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),  # Use custom LoginView
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('vehicle_types/', VehicleTypeListView.as_view(), name='vehicle_types'),
    path('add_vehicle/', AddVehicleView.as_view(), name='add-vehicle'),
    path('add_driver/', AddDriverView.as_view(), name='drivers'),
    path("loads/", get_all_loads, name="get_all_loads"),
    path('loads/<int:load_id>/send_request/', SendVendorRequestView.as_view(), name='send-vendor-request'),
    path("vehicles/", get_all_vehicles, name="get_all_vehicles"),
    path("vehicles/update/<int:vehicle_id>/", update_vehicle),
    path("vehicles/delete/<int:vehicle_id>/", delete_vehicle),
    path("drivers/", list_drivers, name="list-drivers"),
    path("drivers/update/<int:driver_id>/", update_driver, name="update-driver"),
    path("drivers/delete/<int:driver_id>/", delete_driver, name="delete-driver"),
    path('load/<int:load_id>/send-message/', SendTripMessage.as_view(), name='send_trip_message'),
    path('load/<int:load_id>/messages/', LoadAllMessages.as_view(), name='load_all_messages'),
    path("ongoing_trips/", VendorOngoingTrips.as_view(), name="vendor-ongoing-trips"),
    path("load/<int:load_id>/request_confirmation/",VendorAcceptedLoadDetails.as_view(),name="vendor-accepted-load-details"),
    path("load/<int:id>/trip_status/", VendorTripDetailsView.as_view(), name="vendor-load-details"),
    path("load/<int:id>/upload_lr/", VendorLRUploadView.as_view(), name="vendor-upload-lr"),
    path("load/<int:id>/upload_pod/", VendorPODUploadView.as_view(), name="vendor-upload-pod"),
    path("change_password/", VendorProfileUpdateView.as_view(), name="vendor-change-password"),
    path('loads/filter_options/', LoadFilterOptionsView.as_view(), name='load-filter-options'),
    path('loads/filtered/', FilteredLoadsView.as_view(), name='filtered-loads'),
    path('save-fcm-token/', SaveFCMTokenView.as_view(), name='save-fcm-token'),

 
]