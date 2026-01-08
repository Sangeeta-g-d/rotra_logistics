import random
import requests
from django.conf import settings


def generate_otp():
    """
    Generate a 6-digit numeric OTP
    """
    otp = str(random.randint(100000, 999999))
    print(f"DEBUG: OTP generated → {otp}")
    return otp


def send_otp_fast2sms(phone_number, otp):
    """
    Send OTP using Fast2SMS DLT route
    Template ID: 206749
    """

    print("DEBUG: send_otp_fast2sms() called")
    print(f"DEBUG: Phone number → {phone_number}")
    print(f"DEBUG: OTP → {otp}")

    url = "https://www.fast2sms.com/dev/bulkV2"
    
    # Match the exact structure from your working URL
    payload = {
        "route": "dlt",
        "sender_id": "RTRALG",
        "message": "206749",  # This is your template ID, not the message text
        "variables_values": str(otp),  # Just the OTP value(s), pipe-separated if multiple
        "flash": "0",
        "numbers": phone_number
    }

    headers = {
        "authorization": settings.FAST2SMS_API_KEY,
        "Content-Type": "application/json"
    }

    print("DEBUG: Payload →", payload)

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=10
        )

        print("DEBUG: HTTP Status Code →", response.status_code)
        print("DEBUG: Raw Response →", response.text)

        response.raise_for_status()
        result = response.json()

        if not result.get("return"):
            print("❌ Fast2SMS rejected request")
            return {
                "success": False,
                "error": result
            }

        print("✅ OTP SMS sent successfully")
        return {
            "success": True,
            "response": result
        }

    except requests.exceptions.RequestException as e:
        print("❌ Fast2SMS request exception →", str(e))
        return {
            "success": False,
            "error": str(e)
        }