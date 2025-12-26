# accounts/utils.py
import random
import requests
from django.conf import settings

def generate_otp():
    otp = str(random.randint(100000, 999999))
    print("DEBUG: Generated OTP (hidden)")  # don't print OTP
    return otp


def send_otp_fast2sms(phone_number, otp):
    print("DEBUG: Entered send_otp_fast2sms()")
    print("DEBUG: Phone number received:", phone_number)

    api_key = getattr(settings, "FAST2SMS_API_KEY", None)
    print("DEBUG: FAST2SMS_API_KEY exists:", bool(api_key))

    if not api_key:
        print("ERROR: FAST2SMS_API_KEY is missing")
        raise Exception("FAST2SMS_API_KEY not configured")

    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "route": "otp",
        "variables_values": otp,
        "numbers": phone_number,
    }

    print("DEBUG: Payload prepared (OTP hidden)")

    headers = {
        "authorization": api_key,
        "Content-Type": "application/json",
    }

    print("DEBUG: Sending request to Fast2SMS...")

    response = requests.post(url, json=payload, headers=headers)

    print("DEBUG: Fast2SMS status code:", response.status_code)
    print("DEBUG: Fast2SMS response:", response.text)

    return response.json()
