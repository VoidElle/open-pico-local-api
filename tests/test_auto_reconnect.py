"""Tests for auto_reconnect decorator."""
import unittest
from unittest.mock import MagicMock

from exceptions.pico_connection_error import PicoConnectionError
from utils.auto_reconnect import auto_reconnect


def _make_client(auto_reconnect_enabled=True, max_attempts=3, delay=0.0):
    """Return a minimal mock object that looks like PicoClient."""
    client = MagicMock()
    client._auto_reconnect = auto_reconnect_enabled
    client._max_reconnect_attempts = max_attempts
    client._reconnect_delay = delay
    client._connected = True
    client.verbose = False
    return client


class TestAutoReconnectDecorator(unittest.TestCase):

    def test_passthrough_when_disabled(self):
        client = _make_client(auto_reconnect_enabled=False)

        @auto_reconnect
        def my_method(_client):
            return "ok"

        result = my_method(client)
        self.assertEqual(result, "ok")
        client.connect.assert_not_called()

    def test_success_on_first_try(self):
        client = _make_client()

        @auto_reconnect
        def my_method(_client):
            return 42

        result = my_method(client)
        self.assertEqual(result, 42)

    def test_reconnects_on_connection_error(self):
        client = _make_client(max_attempts=3, delay=0.0)
        attempts = []

        @auto_reconnect
        def my_method(_client):
            attempts.append(1)
            if len(attempts) < 3:
                raise PicoConnectionError("dropped")
            return "recovered"

        result = my_method(client)
        self.assertEqual(result, "recovered")
        self.assertEqual(len(attempts), 3)

    def test_raises_after_max_attempts(self):
        client = _make_client(max_attempts=2, delay=0.0)

        @auto_reconnect
        def always_fails(_client):
            raise PicoConnectionError("always down")

        with self.assertRaises(PicoConnectionError):
            always_fails(client)

    def test_non_connection_error_not_retried(self):
        client = _make_client(max_attempts=5, delay=0.0)
        calls = []

        @auto_reconnect
        def my_method(_client):
            calls.append(1)
            raise ValueError("logic error")

        with self.assertRaises(ValueError):
            my_method(client)

        self.assertEqual(len(calls), 1)  # Only called once, no retries

    def test_connects_when_not_connected(self):
        client = _make_client()
        client._connected = False

        @auto_reconnect
        def my_method(_client):
            return "done"

        my_method(client)
        client.connect.assert_called()


if __name__ == "__main__":
    unittest.main()
