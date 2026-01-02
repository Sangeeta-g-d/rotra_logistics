import random
import requests
from django.conf import settings
from urllib.parse import quote
import requests
from django.conf import settings

def generate_otp():
    otp = str(random.randint(100000, 999999))
    print("DEBUG: OTP generated (hidden)")
    return otp


def send_otp_fast2sms(phone, otp):
    url = "https://www.fast2sms.com/dev/bulkV2"

    payload = {
        "route": "dlt",
        "sender_id": "RTRALG",  # EXACT DLT header
        "message": f"Your OTP for verification on ROTRA LOGISTICS is {otp}. Valid for 5 minutes. Do not share it with anyone.",
        "language": "english",
        "numbers": phone,
        "entity_id": "1001675418594733281",
        "template_id": "1007070782309739934",
    }

    headers = {
        "authorization": "FAST2SMS_API_KEY",
        "Content-Type": "application/json",
    }

    r = requests.post(url, json=payload, headers=headers, timeout=10)
    print(r.status_code, r.text)
    return r.json()