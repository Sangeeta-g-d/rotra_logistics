import firebase_admin
from firebase_admin import credentials, messaging
import os
from django.conf import settings
import logging
import json
from django.utils import timezone

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def initialize_firebase():
    try:
        # Try multiple possible locations for the service account file
        possible_paths = [
            os.path.join(settings.BASE_DIR, 'firebase-service-account.json'),
            os.path.join(settings.BASE_DIR, 'rotra_logistics', 'firebase-service-account.json'),
            os.path.join(os.path.dirname(__file__), 'firebase-service-account.json'),
        ]
        
        cred_path = None
        for path in possible_paths:
            if os.path.exists(path):
                cred_path = path
                logger.info(f"✅ Found service account file at: {path}")
                break
        
        if not cred_path:
            logger.error("❌ Firebase service account file not found in any location")
            logger.info("Please download service account JSON from Firebase Console and save as 'firebase-service-account.json'")
            return False
        
        # Initialize Firebase
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("✅ Firebase Admin SDK initialized successfully")
        return True
        
    except ValueError as e:
        if "already exists" in str(e):
            logger.info("✅ Firebase app already initialized")
            return True
        else:
            logger.error(f"❌ Firebase initialization error: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase: {e}")
        return False

# Initialize on import
firebase_initialized = initialize_firebase()

class FirebaseService:
    
    @staticmethod
    def send_push_notification(fcm_token, title, body, data=None):
        """Send push notification using Firebase Admin SDK"""
        if not firebase_initialized:
            logger.error("❌ Firebase not initialized")
            return False
            
        try:
            # Validate token
            if not fcm_token:
                logger.error("❌ No FCM token provided")
                return False
                
            if fcm_token.startswith('fcm_mock_'):
                logger.error(f"❌ Mock FCM token: {fcm_token}")
                return False
            
            logger.info(f"📤 Sending FCM notification to: {fcm_token[:20]}...")
            logger.info(f"📝 Title: {title}, Body: {body}")
            
            # Create message
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=fcm_token,
                data=data or {},
                webpush=messaging.WebpushConfig(
                    notification=messaging.WebpushNotification(
                        icon='/static/images/logo.png',
                        badge='/static/images/badge.png',
                    ),
                    fcm_options=messaging.WebpushFCMOptions(
                        link='/trip-management/',
                    ),
                ),
            )
            
            # Send message
            response = messaging.send(message)
            logger.info(f"✅ FCM notification sent successfully: {response}")
            return True
            
        except messaging.UnregisteredError as e:
            logger.error(f"❌ FCM token not registered (user uninstalled app): {e}")
            # You might want to remove this token from your database
            return False
            
        except messaging.SenderIdMismatchError as e:
            logger.error(f"❌ FCM sender ID mismatch: {e}")
            return False
            
        except messaging.ThirdPartyAuthError as e:
            logger.error(f"❌ FCM third party auth error: {e}")
            return False
            
        except messaging.InvalidArgumentError as e:
            logger.error(f"❌ FCM invalid argument: {e}")
            return False
            
        except messaging.InternalError as e:
            logger.error(f"❌ FCM internal error: {e}")
            return False
            
        except messaging.UnavailableError as e:
            logger.error(f"❌ FCM service unavailable: {e}")
            return False
            
        except Exception as e:
            logger.error(f"❌ FCM unexpected error: {e}")
            return False
    
    @staticmethod
    def send_reassignment_notification(traffic_person, trip_count, reassigned_trips_info, assigned_by):
        """Send notification for trip reassignment"""
        try:
            logger.info(f"🎯 Preparing reassignment notification for: {traffic_person.email}")
            
            if not traffic_person.fcm_token:
                logger.warning(f"❌ No FCM token for user: {traffic_person.email}")
                return False
                
            if traffic_person.fcm_token.startswith('fcm_mock_'):
                logger.warning(f"❌ Mock FCM token for user: {traffic_person.email}")
                return False
            
            title = "🚛 Trips Reassigned"
            body = f"{trip_count} trip(s) assigned to you by {assigned_by}"
            
            # Prepare data payload
            data = {
                'type': 'trip_reassigned',
                'trip_count': str(trip_count),
                'assigned_by': assigned_by,
                'click_action': '/trip-management/',
                'timestamp': str(timezone.now().isoformat())
            }
            
            # Add trip details if available
            if reassigned_trips_info:
                trip_details = []
                for trip_info in reassigned_trips_info[:3]:  # Show first 3 trips
                    trip_details.append(f"{trip_info['load_id']}: {trip_info['pickup']} → {trip_info['drop']}")
                data['trip_details'] = json.dumps(trip_details)
            
            logger.info(f"📨 Sending reassignment notification: {title} - {body}")
            
            success = FirebaseService.send_push_notification(
                traffic_person.fcm_token, 
                title, 
                body, 
                data
            )
            
            if success:
                logger.info(f"✅ Reassignment notification sent successfully to {traffic_person.email}")
            else:
                logger.error(f"❌ Failed to send reassignment notification to {traffic_person.email}")
                
            return success
            
        except Exception as e:
            logger.error(f"💥 Error in send_reassignment_notification: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    @staticmethod
    def test_notification(fcm_token):
        """Test function to verify FCM setup"""
        logger.info("🧪 Testing FCM notification...")
        return FirebaseService.send_push_notification(
            fcm_token,
            "Test Notification 🎉",
            "This is a test notification from Rotra Logistics",
            {'type': 'test', 'timestamp': str(timezone.now().isoformat())}
        )