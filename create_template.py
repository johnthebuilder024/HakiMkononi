"""
Creates a Twilio Content Template for WhatsApp free-form replies.
Run once: python create_template.py
"""
import os, requests, json
from dotenv import load_dotenv
load_dotenv()

sid   = os.getenv('TWILIO_ACCOUNT_SID')
token = os.getenv('TWILIO_AUTH_TOKEN')

# Create a free-form text template with a single variable {{1}}
# This allows us to send any text as the value of {{1}}
url = "https://content.twilio.com/v1/Content"

payload = {
    "friendly_name": "hakimkononi_reply",
    "language": "en",
    "variables": {"1": "answer text"},
    "types": {
        "twilio/text": {
            "body": "{{1}}"
        }
    }
}

r = requests.post(url, auth=(sid, token), json=payload)
print(f"Status: {r.status_code}")
print(r.text[:1000])

if r.status_code == 201:
    data = r.json()
    template_sid = data.get('sid')
    print(f"\n✅ Template SID: {template_sid}")
    print(f"Add this to .env:  TWILIO_TEMPLATE_SID={template_sid}")
