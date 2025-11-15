from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_login_view, name='admin_login'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/<int:employee_id>/update/', views.update_employee, name='update_employee'),
    path('employees/<int:employee_id>/delete/', views.delete_employee, name='delete_employee'),
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.add_customer, name='add_customer'),
    path('customers/<int:pk>/delete/', views.delete_customer, name='delete_customer'),
    path('drivers/', views.driver_list, name='driver_list'),
    path('drivers/add/', views.add_driver, name='add_driver'),
    path('drivers/<int:driver_id>/update/', views.update_driver, name='update_driver'),
    path('drivers/<int:driver_id>/delete/', views.delete_driver, name='delete_driver'),
    path('drivers/<int:driver_id>/toggle-status/', views.toggle_driver_status, name='toggle_driver_status'),
    path('vehicle-types/', views.vehicle_type_list, name='vehicle_type_list'),
    path('add_vehicle_type/', views.add_vehicle_type, name='add_vehicle_type'),
    path('delete_vehicle_type/<int:pk>/', views.delete_vehicle_type, name='delete_vehicle_type'),
    path('vehicle_type_list_view/', views.vehicle_type_list_view, name='vehicle_type_list_view'),
    path('loads/', views.load_list, name='load_list'),
    path('loads/add/', views.add_load, name='add_load'),
    path('loads/<int:load_id>/delete/', views.delete_load, name='delete_load'),
    path('loads/<int:load_id>/update-status/', views.update_load_status, name='update_load_status'),
    path('loads/customer/<int:customer_id>/details/', views.get_customer_details, name='get_customer_details'),
    path('vendor/', views.vendor_list, name='vendor_list'),
    path('vendor/add/', views.add_vendor, name='add_vendor'),
    path('vendor/<int:vendor_id>/delete/', views.delete_vendor, name='delete_vendor'),
    path('vendor/<int:vendor_id>/get/', views.get_vendor, name='get_vendor'),
    path('vendor/<int:vendor_id>/toggle-status/', views.toggle_vendor_status, name='toggle_vendor_status'),
    path('vehicle/', views.vehicle_list, name='vehicle_list'),
    path('vehicle/add/', views.add_vehicle, name='add_vehicle'),
    path('vehicle/<int:vehicle_id>/delete/', views.delete_vehicle, name='delete_vehicle'),
    path('vehicle/<int:vehicle_id>/toggle-status/', views.toggle_vehicle_status, name='toggle_vehicle_status'),
    
    
    
]

