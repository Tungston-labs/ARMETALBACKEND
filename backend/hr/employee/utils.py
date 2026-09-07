import requests
import logging

logger = logging.getLogger(__name__)

def send_push_notification(user, title, message):
    token = getattr(user, 'fcm_token', None)
    if not token:
        logger.warning(f"No FCM token for user {user.id}")
        return

    payload = {
        "to": token,
        "notification": {
            "title": title,
            "body": message
        }
    }

    headers = {
        "Authorization": "key=YOUR_FIREBASE_SERVER_KEY",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post("https://fcm.googleapis.com/fcm/send", json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Push notification sent to user {user.id} with title '{title}'")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send push notification to user {user.id}: {e}")
