import os
import unittest
from unittest.mock import patch
from app.line_bot import verify_signature

class TestLineBot(unittest.TestCase):
    def setUp(self):
        os.environ["LINE_CHANNEL_SECRET"] = "test_secret"
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test_token"

    def test_signature_verification_failure(self):
        body = b"hello world"
        signature = "invalidsignature"
        self.assertFalse(verify_signature(body, signature))

if __name__ == '__main__':
    unittest.main()
