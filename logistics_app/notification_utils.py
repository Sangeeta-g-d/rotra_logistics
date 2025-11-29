# logistics_app/notification_utils.py
from .models import CustomUser, Load, LoadRequest
from .firebase_service import firebase_service

def send_request_accepted_notification(load_request):
    """
    Send notification to vendor when their load request is accepted
    """
    vendor = load_request.vendor
    load = load_request.load
    
    title = "🎉 Load Request Accepted!"
    body = f"Your request for load {load.load_id} has been accepted"
    
    # Prepare data payload for the app
    data_payload = {
        'type': 'request_accepted',
        'load_id': str(load.id),
        'load_number': load.load_id,
        'click_action': 'FLUTTER_NOTIFICATION_CLICK',
        'screen': 'trip_details',
    }
    
    # Send via Firebase
    firebase_service.send_notification_to_user(
        user=vendor,
        title=title,
        body=body,
        data=data_payload
    )
    
    # Also save in database
    from .models import Notification
    Notification.objects.create(
        recipient=vendor,
        notification_type='trip_assigned',
        title=title,
        message=body,
        related_trip=load
    )

def send_request_rejected_notification(load_request):
    """
    Send notification to vendor when their load request is rejected
    """
    vendor = load_request.vendor
    load = load_request.load
    
    title = "❌ Load Request Rejected"
    body = f"Your request for load {load.load_id} was not accepted"
    
    data_payload = {
        'type': 'request_rejected',
        'load_id': str(load.id),
        'load_number': load.load_id,
        'click_action': 'FLUTTER_NOTIFICATION_CLICK',
    }
    
    firebase_service.send_notification_to_user(
        user=vendor,
        title=title,
        body=body,
        data=data_payload
    )