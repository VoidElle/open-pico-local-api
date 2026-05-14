"""Tests for PicoAutoDiscovery helpers (no network required)."""
import unittest
from typing import Any, cast

from pico_auto_discovery import _build_probe, _is_valid_pico_response, PicoAutoDiscovery
from shared_transport_manager import SharedTransportManager
import json
import asyncio


class TestBuildProbe(unittest.TestCase):

    def test_returns_bytes(self):
        result = _build_probe("1234")
        self.assertIsInstance(result, bytes)

    def test_valid_json(self):
        result = _build_probe("9999")
        parsed = json.loads(result.decode("utf-8"))
        self.assertIsInstance(parsed, dict)

    def test_contains_pin(self):
        parsed = json.loads(_build_probe("5678").decode("utf-8"))
        self.assertEqual(parsed["pin"], "5678")

    def test_contains_discovery_idp(self):
        parsed = json.loads(_build_probe("0").decode("utf-8"))
        self.assertEqual(parsed["idp"], 0)

    def test_contains_cmd(self):
        parsed = json.loads(_build_probe("0").decode("utf-8"))
        self.assertEqual(parsed["cmd"], "stato_sync")


class TestIsValidPicoResponse(unittest.TestCase):

    @staticmethod
    def _valid() -> dict[str, Any]:
        return {"idp": 0, "fw_ver": "3.2.1", "mod": 1, "cmd": "stato_sync"}

    def test_valid_response_accepted(self):
        self.assertTrue(_is_valid_pico_response(self._valid()))

    def test_non_dict_rejected(self):
        invalid_inputs: list[Any] = ["not a dict", None, []]
        for inp in invalid_inputs:
            self.assertFalse(_is_valid_pico_response(inp))

    def test_wrong_idp_rejected(self):
        r = self._valid()
        r["idp"] = 99
        self.assertFalse(_is_valid_pico_response(r))

    def test_missing_fw_ver_rejected(self):
        r = self._valid()
        del r["fw_ver"]
        self.assertFalse(_is_valid_pico_response(r))

    def test_missing_mod_rejected(self):
        r = self._valid()
        del r["mod"]
        self.assertFalse(_is_valid_pico_response(r))


class TestSubnetScanValidation(unittest.IsolatedAsyncioTestCase):

    async def test_ipv6_subnet_raises_value_error(self):
        with self.assertRaises(ValueError):
            await PicoAutoDiscovery._subnet_scan(
                probe=b"",
                manager=cast(SharedTransportManager, cast(object, None)),
                unmatched_queue=asyncio.Queue(),
                discovered=set(),
                subnet="fd00::/64",
                device_port=40070,
                timeout=0.01,
                max_concurrent=1,
                verbose=False,
            )

    async def test_invalid_subnet_raises_value_error(self):
        with self.assertRaises(ValueError):
            await PicoAutoDiscovery._subnet_scan(
                probe=b"",
                manager=cast(SharedTransportManager, cast(object, None)),
                unmatched_queue=asyncio.Queue(),
                discovered=set(),
                subnet="not_a_subnet",
                device_port=40070,
                timeout=0.01,
                max_concurrent=1,
                verbose=False,
            )


if __name__ == "__main__":
    unittest.main()
