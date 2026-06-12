"""Tests for SharedTransportManager and SharedPicoProtocol."""
import asyncio
import inspect
import json
import unittest
import unittest.mock

from open_pico_local_api.shared_transport_manager import SharedTransportManager, SharedPicoProtocol


class TestSharedTransportManagerUnit(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Reset singleton between tests
        SharedTransportManager._instance = None
        SharedTransportManager._lock = asyncio.Lock()

    async def test_singleton_returns_same_instance(self):
        a = await SharedTransportManager.get_instance()
        b = await SharedTransportManager.get_instance()
        self.assertIs(a, b)

    async def test_direct_instantiation_raises(self):
        # Singleton must already exist for the guard to fire
        await SharedTransportManager.get_instance()
        with self.assertRaises(RuntimeError):
            SharedTransportManager()

    async def test_not_initialized_by_default(self):
        mgr = await SharedTransportManager.get_instance()
        self.assertFalse(mgr.is_initialized)

    async def test_unmatched_queue_initially_none(self):
        mgr = await SharedTransportManager.get_instance()
        self.assertIsNone(mgr.unmatched_queue)

    async def test_set_and_clear_unmatched_queue(self):
        mgr = await SharedTransportManager.get_instance()
        q = asyncio.Queue()
        mgr.set_unmatched_queue(q)
        self.assertIs(mgr.unmatched_queue, q)
        mgr.clear_unmatched_queue()
        self.assertIsNone(mgr.unmatched_queue)

    async def test_get_device_registration_returns_none_for_unknown(self):
        mgr = await SharedTransportManager.get_instance()
        self.assertIsNone(mgr.get_device_registration("ghost"))

    async def test_find_device_by_idp_returns_none_when_empty(self):
        mgr = await SharedTransportManager.get_instance()
        self.assertIsNone(mgr.find_device_by_idp(999))

    async def test_register_device_and_lookup(self):
        mgr = await SharedTransportManager.get_instance()
        # Manually mark as initialized to skip UDP bind
        mgr._initialized = True

        q = asyncio.Queue()
        start, size = await mgr.register_device("dev1", "192.168.1.1", 40070, q)

        self.assertGreater(start, 0)
        self.assertEqual(size, mgr._idp_range_size)

        reg = mgr.get_device_registration("dev1")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.ip, "192.168.1.1")
        self.assertIs(reg.response_queue, q)

    async def test_find_device_by_idp_after_register(self):
        mgr = await SharedTransportManager.get_instance()
        mgr._initialized = True

        q = asyncio.Queue()
        start, size = await mgr.register_device("dev2", "192.168.1.2", 40070, q)

        self.assertEqual(mgr.find_device_by_idp(start), "dev2")
        self.assertEqual(mgr.find_device_by_idp(start + size - 1), "dev2")
        self.assertIsNone(mgr.find_device_by_idp(start + size))  # Just outside range

    async def test_register_same_device_twice_returns_same_range(self):
        mgr = await SharedTransportManager.get_instance()
        mgr._initialized = True

        q = asyncio.Queue()
        start1, size1 = await mgr.register_device("devX", "10.0.0.1", 40070, q)
        start2, size2 = await mgr.register_device("devX", "10.0.0.1", 40070, q)

        self.assertEqual(start1, start2)
        self.assertEqual(size1, size2)

    async def test_unregister_device(self):
        mgr = await SharedTransportManager.get_instance()
        mgr._initialized = True

        q = asyncio.Queue()
        await mgr.register_device("devY", "10.0.0.2", 40070, q)
        await mgr.unregister_device("devY")

        self.assertIsNone(mgr.get_device_registration("devY"))

    async def test_register_device_raises_when_not_initialized(self):
        mgr = await SharedTransportManager.get_instance()
        with self.assertRaises(RuntimeError):
            await mgr.register_device("devZ", "10.0.0.3", 40070, asyncio.Queue())


class TestSharedPicoProtocol(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        SharedTransportManager._instance = None
        SharedTransportManager._lock = asyncio.Lock()

    def test_run_callback_is_static(self):
        self.assertTrue(isinstance(
            inspect.getattr_static(SharedPicoProtocol, '_run_callback'),
            staticmethod
        ))

    async def test_run_callback_sync(self):
        called_with = []

        def sync_cb(response):
            called_with.append(response)

        await SharedPicoProtocol._run_callback(sync_cb, {"cmd": "test"})
        self.assertEqual(called_with, [{"cmd": "test"}])

    async def test_run_callback_async(self):
        called_with = []

        async def async_cb(response):
            called_with.append(response)

        await SharedPicoProtocol._run_callback(async_cb, {"cmd": "async_test"})
        self.assertEqual(called_with, [{"cmd": "async_test"}])

    async def test_run_callback_exception_does_not_propagate(self):
        def bad_cb():
            raise ValueError("boom")

        # Should not raise; warning is logged via _LOGGER (not print)
        with unittest.mock.patch("open_pico_local_api.shared_transport_manager._LOGGER"):
            await SharedPicoProtocol._run_callback(bad_cb, {})

    async def test_datagram_received_routes_to_device_queue(self):
        mgr = await SharedTransportManager.get_instance()
        mgr._initialized = True

        q = asyncio.Queue()
        start, _ = await mgr.register_device("routing_dev", "10.0.0.5", 40070, q)

        # Build a fake protocol with a mock transport
        protocol = SharedPicoProtocol(mgr, verbose=False)

        payload = json.dumps({"idp": start, "cmd": "stato_sync", "res": 1}).encode()
        protocol.datagram_received(payload, ("10.0.0.5", 40070))

        self.assertFalse(q.empty())
        response, addr = q.get_nowait()
        self.assertEqual(response["idp"], start)

    async def test_datagram_received_routes_to_unmatched_queue(self):
        mgr = await SharedTransportManager.get_instance()
        mgr._initialized = True

        unmatched = asyncio.Queue()
        mgr.set_unmatched_queue(unmatched)

        protocol = SharedPicoProtocol(mgr, verbose=False)
        payload = json.dumps({"idp": 0, "cmd": "stato_sync"}).encode()
        protocol.datagram_received(payload, ("10.0.0.99", 40070))

        self.assertFalse(unmatched.empty())

    async def test_datagram_received_invalid_json_no_raise(self):
        mgr = await SharedTransportManager.get_instance()
        protocol = SharedPicoProtocol(mgr, verbose=False)
        # Should not raise
        protocol.datagram_received(b"not json", ("10.0.0.1", 40070))

    async def test_uses_inspect_iscoroutinefunction(self):
        """Verify the module uses inspect.iscoroutinefunction, not asyncio's deprecated version."""
        import open_pico_local_api.shared_transport_manager as stm
        source = inspect.getsource(stm)
        self.assertIn("inspect.iscoroutinefunction", source)
        self.assertNotIn("asyncio.iscoroutinefunction", source)


if __name__ == "__main__":
    unittest.main()
