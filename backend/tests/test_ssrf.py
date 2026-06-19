import unittest
from unittest.mock import patch
import socket
from app.services.smart_meter_service import is_safe_url

class TestSSRFProtection(unittest.TestCase):
    @patch("socket.getaddrinfo")
    def test_safe_external_urls(self, mock_getaddrinfo):
        # Mock DNS resolution to return a public IP (Google DNS)
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 0))
        ]
        self.assertTrue(is_safe_url("https://api.enedis.fr", allow_private=False))
        self.assertTrue(is_safe_url("https://example.com/api/v1", allow_private=False))

    @patch("socket.getaddrinfo")
    def test_private_ips_blocked_in_production(self, mock_getaddrinfo):
        # Private and loopback ranges should be blocked in production mode
        
        # Test Loopback
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        self.assertFalse(is_safe_url("http://localhost", allow_private=False))
        
        # Test 192.168
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.0.1", 0))]
        self.assertFalse(is_safe_url("http://192.168.0.1", allow_private=False))
        
        # Test 10.x
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]
        self.assertFalse(is_safe_url("http://10.0.0.5", allow_private=False))

        # Test Link-local
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 0))]
        self.assertFalse(is_safe_url("http://169.254.169.254", allow_private=False))

    def test_unsafe_schemes_blocked_always(self):
        # Non-HTTP protocols must always be blocked
        self.assertFalse(is_safe_url("file:///etc/passwd", allow_private=False))
        self.assertFalse(is_safe_url("file:///etc/passwd", allow_private=True))
        self.assertFalse(is_safe_url("ftp://127.0.0.1/data", allow_private=False))
        self.assertFalse(is_safe_url("gopher://localhost", allow_private=True))

    @patch("socket.getaddrinfo")
    def test_private_ips_allowed_in_debug(self, mock_getaddrinfo):
        # Private/loopback ranges are acceptable in local development mode
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 0))]
        self.assertTrue(is_safe_url("http://127.0.0.1", allow_private=True))
        self.assertTrue(is_safe_url("http://localhost:8000/api", allow_private=True))
        
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.100", 0))]
        self.assertTrue(is_safe_url("http://192.168.1.100", allow_private=True))
