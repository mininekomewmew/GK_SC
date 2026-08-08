import os
import unittest
from app.line_bot import LineClient

class TestLineBot(unittest.TestCase):
    def setUp(self):
        os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_token"
        self.client = LineClient()

    def test_signature_verification_failure(self):
        body = b"hello world"
        signature = "invalidsignature"
        self.assertFalse(self.client.verify_signature(body, signature))

if __name__ == '__main__':
    unittest.main()
