import os
import firebase_admin
from firebase_admin import credentials, messaging

# Get absolute path to serviceAccountKey.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # This is backend/user
cred_path = os.path.join(BASE_DIR, "serviceAccountKey.json")

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

def send_push_notification(token, title, body):
    if not token:
        return
    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token
    )
    return messaging.send(message)
