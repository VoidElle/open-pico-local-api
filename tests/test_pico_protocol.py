"""Tests for PicoProtocol (utils/pico_protocol.py)."""
import asyncio
import inspect
import json
import unittest

import open_pico_local_api.utils.pico_protocol as pico_protocol_module
from open_pico_local_api.utils.pico_protocol import PicoProtocol


class TestPicoProtocol(unittest.IsolatedAsyncioTestCase):

    @staticmethod
    def _make_protocol(callbacks=None, verbose=False):
        q = asyncio.Queue()
        return PicoProtocol(
            response_queue=q,
            event_callbacks=callbacks or {},
            verbose=verbose,
        ), q

    def test_uses_inspect_iscoroutinefunction(self):
        source = inspect.getsource(pico_protocol_module)
        self.assertIn("inspect.iscoroutinefunction", source)
        self.assertNotIn("asyncio.iscoroutinefunction", source)

    async def test_datagram_received_puts_in_queue(self):
        proto, q = self._make_protocol()
        payload = json.dumps({"cmd": "stato_sync", "res": 1}).encode()

        # Need a running loop for create_task
        proto.datagram_received(payload, ("10.0.0.1", 40070))

        # Drain pending tasks
        await asyncio.sleep(0)

        self.assertFalse(q.empty())
        response, addr = q.get_nowait()
        self.assertEqual(response["cmd"], "stato_sync")

    async def test_sync_callback_invoked(self):
        called = []

        def cb(resp):
            called.append(resp)

        proto, _ = self._make_protocol(callbacks={"test_cmd": cb})
        payload = json.dumps({"cmd": "test_cmd"}).encode()
        proto.datagram_received(payload, ("10.0.0.1", 40070))
        await asyncio.sleep(0.01)

        self.assertTrue(len(called) > 0)
        self.assertEqual(called[0]["cmd"], "test_cmd")

    async def test_async_callback_invoked(self):
        called = []

        async def async_cb(resp):
            called.append(resp)

        proto, _ = self._make_protocol(callbacks={"async_cmd": async_cb})
        payload = json.dumps({"cmd": "async_cmd"}).encode()
        proto.datagram_received(payload, ("10.0.0.1", 40070))
        await asyncio.sleep(0.01)

        self.assertTrue(len(called) > 0)

    async def test_invalid_json_no_raise(self):
        proto, _ = self._make_protocol()
        proto.datagram_received(b"{{broken json", ("10.0.0.1", 40070))

    async def test_callback_exception_does_not_crash_protocol(self):
        def bad_cb():
            raise RuntimeError("callback exploded")

        proto, _ = self._make_protocol(callbacks={"bad_cmd": bad_cb})
        payload = json.dumps({"cmd": "bad_cmd"}).encode()
        proto.datagram_received(payload, ("10.0.0.1", 40070))
        await asyncio.sleep(0.01)  # Should not raise


if __name__ == "__main__":
    unittest.main()
