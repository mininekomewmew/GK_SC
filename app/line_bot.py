import os
import hmac
import hashlib
import base64
import requests

class LineClient:
    def __init__(self, channel_secret: str = None, access_token: str = None):
        self.channel_secret = channel_secret or os.environ.get("LINE_CHANNEL_SECRET", "")
        self.access_token = access_token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

    def verify_signature(self, body: bytes, signature: str) -> bool:
        if not self.channel_secret:
            return False
        hash_val = hmac.new(
            self.channel_secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(hash_val).decode('utf-8')
        return hmac.compare_digest(signature, expected_signature)

    def reply_message(self, reply_token: str, text: str) -> bool:
        if not self.access_token:
            return False
        url = "https://api.line.me/v2/bot/message/reply"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        payload = {
            "replyToken": reply_token,
            "messages": [{"type": "text", "text": str(text)}]
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

    def push_message(self, to_id: str, text: str) -> bool:
        if not self.access_token:
            return False
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        payload = {
            "to": to_id,
            "messages": [{"type": "text", "text": str(text)}]
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
