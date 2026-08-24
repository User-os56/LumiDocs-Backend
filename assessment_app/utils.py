import requests
from django.conf import settings

def send_verification_email(user_email, code):
    url = "https://api.brevo.com/v3/smtp/email"
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": settings.BREVO_API_KEY,  # Must be passed as 'api-key'
    }
    
    payload = {
        "sender": {"name": "LUMIERE", "email": settings.DEFAULT_FROM_EMAIL},
        "to": [{"email": user_email}],
        "subject": "Your LUMIERE Verification Code",
        "htmlContent": f"<p>Your verification code is: <strong>{code}</strong></p>"
    }
    
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()