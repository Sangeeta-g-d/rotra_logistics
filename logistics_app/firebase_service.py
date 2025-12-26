# firebase_service.py
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)

class FirebaseService:
    _initialized = False
    
    @classmethod
    def initialize(cls):
        if not cls._initialized:
            try:
                # Path to your service account JSON file
                cred_path = os.path.join(settings.BASE_DIR, 'firebase-service-account.json')
                
                if not os.path.exists(cred_path):
                    logger.error(f"Firebase service account file not found at: {cred_path}")
                    return False
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                cls._initialized = True
                logger.info("Firebase Admin SDK initialized successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {e}")
                return False
        return True
    
    @classmethod
    def send_push_notification(cls, fcm_token, title, body, data=None):
        """Send push notification to a specific device"""
        try:
            if not cls.initialize():
                logger.error("Firebase not initialized")
                return False
            
            if not fcm_token:
                logger.warning("No FCM token provided")
                return False
            
            # Create the message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=fcm_token,
                data=data or {}
            )
            
            # Send the message
            response = messaging.send(message)
            logger.info(f"Firebase notification sent successfully: {response}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending Firebase notification: {e}")
            return False