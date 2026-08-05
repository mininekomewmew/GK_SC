import os
import hmac
import hashlib
import base64
import requests

def verify_signature(body: bytes, signature: str) -> bool:
    channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
    if not channel_secret:
        return False
    hash_val = hmac.new(
        channel_secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).digest()
    expected_signature = base64.b64encode(hash_val).decode('utf-8')
    return hmac.compare_digest(signature, expected_signature)

def reply_message(reply_token: str, text: str) -> bool:
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not access_token:
        return False
    url = "https://api.line.me/v2/bot/message/reply"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "replyToken": reply_token,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception:
        return False

def push_message(to_id: str, text: str) -> bool:
    access_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not access_token:
        return False
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    payload = {
        "to": to_id,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception:
        return False
