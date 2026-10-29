"""Tests for exception hierarchy."""
import unittest

from open_pico_local_api.exceptions.pico_device_error import PicoDeviceError
from open_pico_local_api.exceptions.pico_connection_error import PicoConnectionError
from open_pico_local_api.exceptions.pico_timeout_error import PicoTimeoutError


class TestExceptionHierarchy(unittest.TestCase):

    def test_pico_device_error_is_exception(self):
        self.assertTrue(issubclass(PicoDeviceError, Exception))

    def test_pico_connection_error_is_pico_device_error(self):
        self.assertTrue(issubclass(PicoConnectionError, PicoDeviceError))

    def test_pico_timeout_error_is_pico_device_error(self):
        self.assertTrue(issubclass(PicoTimeoutError, PicoDeviceError))

    def test_pico_connection_error_not_builtin_connection_error(self):
        self.assertFalse(issubclass(PicoConnectionError, ConnectionError))

    def test_pico_timeout_error_not_builtin_timeout_error(self):
        self.assertFalse(issubclass(PicoTimeoutError, TimeoutError))

    def test_pico_connection_error_can_be_raised_and_caught(self):
        with self.assertRaises(PicoConnectionError):
            raise PicoConnectionError("test")

    def test_pico_timeout_error_can_be_raised_and_caught(self):
        with self.assertRaises(PicoTimeoutError):
            raise PicoTimeoutError("test")

    def test_pico_connection_error_caught_as_pico_device_error(self):
        with self.assertRaises(PicoDeviceError):
            raise PicoConnectionError("test")

    def test_pico_timeout_error_caught_as_pico_device_error(self):
        with self.assertRaises(PicoDeviceError):
            raise PicoTimeoutError("test")

    def test_exception_message_preserved(self):
        msg = "connection refused"
        exc = PicoConnectionError(msg)
        self.assertEqual(str(exc), msg)


if __name__ == "__main__":
    unittest.main()
