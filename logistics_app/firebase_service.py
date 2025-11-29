# logistics_app/firebase_service.py
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import os
import json

class FirebaseService:
    def __init__(self):
        # Initialize Firebase app with service account
        service_account_path = os.path.join(settings.BASE_DIR, 'firebase-service-account.json')
        
        if not os.path.exists(service_account_path):
            raise Exception("Firebase service account file not found")
        
        # Initialize Firebase app (only once)
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
    
    def send_notification_to_user(self, user, title, body, data=None):
        """
        Send notification to a specific user's device
        """
        if not user.fcm_token:
            print(f"No FCM token for user: {user.email}")
            return None
        
        try:
            # Create the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=user.fcm_token,
            )
            
            # Send the message
            response = messaging.send(message)
            print(f"Successfully sent message: {response}")
            return response
            
        except Exception as e:
            print(f"Error sending FCM message: {e}")
            return None

# Create singleton instance
firebase_service = FirebaseService()