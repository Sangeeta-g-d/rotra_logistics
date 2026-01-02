# notifications.py
from .firebase_service import FirebaseService
from .models import Notification
import logging

logger = logging.getLogger(__name__)

def _send_notification(fcm_token, title, body, data):
    """Helper function to send notification"""
    success = False
    if fcm_token:
        success = FirebaseService.send_push_notification(fcm_token, title, body, data)
    else:
        logger.warning(f"No FCM token stored")
    return success

def send_trip_assigned_notification(vendor, load, vehicle, driver):
    """Send push notification when a trip is assigned to a vendor"""
    title = "🎉 Trip Assigned Successfully!"
    body = f"Your request for Load #{load.load_id} has been accepted."
    
    data = {
        "type": "trip_assigned",
        "load_id": str(load.id),
        "load_number": load.load_id,
        "vehicle_reg_no": vehicle.reg_no,
        "driver_name": driver.full_name,
        "trip_status": load.trip_status,
        "click_action": "FLUTTER_NOTIFICATION_CLICK"
    }
    
    success = _send_notification(vendor.fcm_token, title, body, data)
    
    # Also create a database notification
    notification = Notification.objects.create(
        recipient=vendor,
        notification_type='trip_assigned',
        title=title,
        message=body,
        related_trip=load,
        is_read=False
    )
    
    return notification, success

def send_trip_rejected_notification(vendor, load):
    """Send push notification when a trip request is rejected"""
    title = "Trip Request Rejected"
    body = f"Your request for Load #{load.load_id} has been rejected."
    
    data = {
        "type": "trip_rejected",
        "load_id": str(load.id),
        "load_number": load.load_id,
        "click_action": "FLUTTER_NOTIFICATION_CLICK"
    }
    
    success = _send_notification(vendor.fcm_token, title, body, data)
    
    notification = Notification.objects.create(
        recipient=vendor,
        notification_type='trip_rejected',
        title=title,
        message=body,
        related_trip=load,
        is_read=False
    )
    
    return notification, success

def send_trip_status_update_notification(vendor, load, previous_status, new_status, triggered_by_admin=True):
    """
    Send push notification when trip status is updated
    """
    # Status-specific messages
    status_messages = {
        'loaded': {
            'title': "🚚 Loaded Successfully",
            'body': f"Load #{load.load_id} has been loaded at pickup location.",
            'emoji': "🚚"
        },
        'lr_uploaded': {
            'title': "📄 LR Document Uploaded",
            'body': f"LR document has been uploaded for Load #{load.load_id}.",
            'emoji': "📄"
        },
        'in_transit': {
            'title': "🚛 In Transit",
            'body': f"Load #{load.load_id} is now in transit to destination.",
            'emoji': "🚛"
        },
        'unloading': {
            'title': "📦 Unloading Started",
            'body': f"Unloading has started for Load #{load.load_id} at destination.",
            'emoji': "📦"
        },
        'pod_uploaded': {
            'title': "✅ POD Uploaded",
            'body': f"Proof of Delivery uploaded for Load #{load.load_id}.",
            'emoji': "✅"
        },
        'payment_completed': {
            'title': "🎉 Trip Completed",
            'body': f"Trip completed! Final payment of ₹{load.final_payment} processed for Load #{load.load_id}.",
            'emoji': "🎉"
        },
        'pending': {
            'title': "⏳ Trip Status Updated",
            'body': f"Load #{load.load_id} status updated to {load.get_trip_status_display()}.",
            'emoji': "⏳"
        }
    }
    
    # Get message for this status
    msg_info = status_messages.get(new_status, {
        'title': f"Trip Status Updated",
        'body': f"Load #{load.load_id} status updated to {load.get_trip_status_display()}.",
        'emoji': "📝"
    })
    
    # Add who triggered the update
    triggered_by = "Admin" if triggered_by_admin else "System"
    body_with_trigger = f"{msg_info['body']} (Updated by {triggered_by})"
    
    title = f"{msg_info.get('emoji', '📝')} {msg_info['title']}"
    
    data = {
        "type": "trip_status_update",
        "load_id": str(load.id),
        "load_number": load.load_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "status_display": load.get_trip_status_display(),
        "click_action": "FLUTTER_NOTIFICATION_CLICK"
    }
    
    success = _send_notification(vendor.fcm_token, title, body_with_trigger, data)
    
    # Create database notification
    notification = Notification.objects.create(
        recipient=vendor,
        notification_type='trip_status_update',
        title=title,
        message=body_with_trigger,
        related_trip=load,
        is_read=False
    )
    
    return notification, success

def send_trip_comment_notification(vendor, load, comment, commenter_name):
    """Send push notification when a comment is added to a trip"""
    title = "💬 New Message on Your Trip"
    body = f"{commenter_name}: {comment[:100]}{'...' if len(comment) > 100 else ''}"
    
    data = {
        "type": "trip_comment",
        "load_id": str(load.id),
        "load_number": load.load_id,
        "commenter": commenter_name,
        "click_action": "FLUTTER_NOTIFICATION_CLICK"
    }
    
    success = _send_notification(vendor.fcm_token, title, body, data)
    
    notification = Notification.objects.create(
        recipient=vendor,
        notification_type='trip_comment',
        title=title,
        message=body,
        related_trip=load,
        is_read=False
    )
    
    return notification, success