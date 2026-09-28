"""
Sets the Twilio WhatsApp sandbox webhook URL via the Twilio API.
No console UI needed.
"""
import os
from dotenv import load_dotenv
load_dotenv()

from twilio.rest import Client

sid   = os.getenv('TWILIO_ACCOUNT_SID')
token = os.getenv('TWILIO_AUTH_TOKEN')

NGROK_URL = "https://margin-comma-showgirl.ngrok-free.dev/api/whatsapp/"

client = Client(sid, token)

# List sandbox configuration
try:
    # Twilio stores sandbox config under the messaging service
    sandbox = client.messaging.v1.services.list(limit=20)
    print(f"Found {len(sandbox)} messaging services")
    for s in sandbox:
        print(f"  SID={s.sid}  friendly_name={s.friendly_name}")
except Exception as e:
    print(f"Messaging services: {e}")

# Try to update via the phone number / incoming webhook
try:
    numbers = client.incoming_phone_numbers.list(limit=20)
    print(f"\nIncoming numbers: {len(numbers)}")
    for n in numbers:
        print(f"  {n.phone_number}  sms_url={n.sms_url}")
except Exception as e:
    print(f"Incoming numbers: {e}")

# Try the correct Twilio sandbox endpoint
try:
    import requests
    # The correct endpoint for WhatsApp sandbox configuration
    endpoints_to_try = [
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Sandbox.json",
        f"https://chat.twilio.com/v2/Services",
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/IncomingPhoneNumbers.json",
    ]
    
    # The real sandbox config endpoint
    url = f"https://conversations.twilio.com/v1/Configuration/Webhooks"
    resp = requests.get(url, auth=(sid, token))
    print(f"\nConversations webhook config: {resp.status_code}")
    print(resp.text[:500])
    
    # Try updating it
    resp2 = requests.post(url, auth=(sid, token), data={
        "PreWebhookUrl": NGROK_URL,
        "PostWebhookUrl": NGROK_URL,
        "Method": "POST",
    })
    print(f"\nUpdate result: {resp2.status_code}")
    print(resp2.text[:500])

except Exception as e:
    print(f"Error: {e}")
