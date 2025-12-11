# firebase_utils.py
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import json
import os
from pathlib import Path

# Initialize Firebase app (singleton pattern)
firebase_app = None

def initialize_firebase():
    """
    Initialize Firebase Admin SDK
    """
    global firebase_app
    
    if not firebase_admin._apps:
        try:
            # Path to your service account key file
            service_account_path = os.path.join(settings.BASE_DIR, 'firebase-service-account.json')
            
            # If JSON is stored as string in settings, write to file
            if hasattr(settings, 'FIREBASE_SERVICE_ACCOUNT_JSON'):
                with open(service_account_path, 'w') as f:
                    json.dump(settings.FIREBASE_SERVICE_ACCOUNT_JSON, f)
            
            cred = credentials.Certificate(service_account_path)
            firebase_app = firebase_admin.initialize_app(cred)
            print("Firebase initialized successfully")
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            firebase_app = None
    
    return firebase_app

def send_notification_to_device(fcm_token, title, body, data=None):
    """
    Send notification to a single device
    """
    try:
        if not fcm_token:
            return False, "No FCM token provided"
        
        if not firebase_app:
            initialize_firebase()
        
        # Create the notification
        notification = messaging.Notification(
            title=title,
            body=body
        )
        
        # Create the message
        message = messaging.Message(
            notification=notification,
            token=fcm_token,
            data=data or {}
        )
        
        # Send the message
        response = messaging.send(message)
        return True, response
    
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False, str(e)

def send_notification_to_topic(topic, title, body, data=None):
    """
    Send notification to all devices subscribed to a topic
    """
    try:
        if not firebase_app:
            initialize_firebase()
        
        # Create the notification
        notification = messaging.Notification(
            title=title,
            body=body
        )
        
        # Create the message
        message = messaging.Message(
            notification=notification,
            topic=topic,
            data=data or {}
        )
        
        # Send the message
        response = messaging.send(message)
        return True, response
    
    except Exception as e:
        print(f"Error sending topic notification: {e}")
        return False, str(e)

def send_notification_to_multiple_devices(fcm_tokens, title, body, data=None):
    """
    Send notification to multiple devices
    """
    try:
        if not fcm_tokens:
            return False, "No FCM tokens provided"
        
        if not firebase_app:
            initialize_firebase()
        
        # Create the notification
        notification = messaging.Notification(
            title=title,
            body=body
        )
        
        # Create the message
        message = messaging.MulticastMessage(
            notification=notification,
            tokens=fcm_tokens,
            data=data or {}
        )
        
        # Send the message
        response = messaging.send_multicast(message)
        return True, response
    
    except Exception as e:
        print(f"Error sending multicast notification: {e}")
        return False, str(e)