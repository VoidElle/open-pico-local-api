"""Smoke tests: run the cloud examples against the fake backend (no real cloud)."""
import asyncio
import contextlib
import functools
import importlib.util
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from aiohttp.test_utils import TestServer

from open_pico_local_api.cloud import PicoCloudClient
from tests.cloud.test_cloud_client import ANDROID_ID, make_backend

EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "cloud")
CREDS = ["--email", "a@b.c", "--password", "secret"]
DEVICE = CREDS + ["--serial", "ser1", "--pin", "1234"]
_real_sleep = asyncio.sleep


def load(name: str):
    if EXAMPLES not in sys.path:
        sys.path.insert(0, EXAMPLES)  # examples import their sibling _common
    spec = importlib.util.spec_from_file_location(f"cloud_example_{name}", os.path.join(EXAMPLES, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CloudExamplesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent = []
        self.server = TestServer(make_backend(self.sent))
        await self.server.start_server()

    async def asyncTearDown(self):
        await self.server.close()

    async def run_example(self, name: str, *argv: str) -> str:
        module = load(name)
        # Examples build the client with the default backend: point it at the fake one.
        module.PicoCloudClient = functools.partial(
            PicoCloudClient, base_url=str(self.server.make_url("")), device_id=ANDROID_ID, retry_delay=0)
        out = io.StringIO()
        # Examples wait ~6 s for the device to apply a command; skip the wait.
        with patch.object(sys, "argv", [name, *argv]), contextlib.redirect_stdout(out), \
                patch("asyncio.sleep", lambda *_: _real_sleep(0)):
            await module.main()
        return out.getvalue()

    def commands(self) -> list[dict]:
        return [json.loads(body["Cmd"]) for body in self.sent]

    async def test_login(self):
        out = await self.run_example("login", *CREDS)
        self.assertIn("Login OK.", out)

    async def test_list_devices(self):
        out = await self.run_example("list_devices", *CREDS)
        self.assertIn("Plant: HOME", out)
        self.assertIn("SER1", out)
        self.assertIn("SER2", out)
        raw = json.loads(await self.run_example("list_devices", *CREDS, "--json"))
        self.assertEqual([d["Serial"] for d in raw[0]["ListDevices"]], ["SER1", "SER2"])

    async def test_basic_cloud(self):
        out = await self.run_example("basic_cloud", *DEVICE)
        self.assertIn("Power ON | mode COMFORT_SUMMER", out)
        self.assertIn("Mode now:", out)
        self.assertEqual([c["cmd"] for c in self.commands()], ["upd_pico", "upd_pico"])
        self.assertEqual(self.sent[0]["Serial"], "SER1")

    async def test_simple_actions(self):
        out = await self.run_example("simple_actions", *DEVICE, "status")
        self.assertIn("ON | COMFORT_SUMMER", out)
        self.assertEqual(self.sent, [])
        out = await self.run_example("simple_actions", *DEVICE, "mode", "1")
        self.assertIn("mode 1: sent.", out)
        self.assertEqual(self.commands()[0]["mod"], 1)

    async def test_adaptive_cloud(self):
        out = await self.run_example("adaptive_cloud", *DEVICE)
        self.assertIn("want HEAT_RECOVERY/50%", out)
        self.assertIn(1, [c.get("mod") for c in self.commands()])  # HEAT_RECOVERY sent

    async def test_multi_device_cloud(self):
        out = await self.run_example("multi_device_cloud", *CREDS, "--pins", "ser1=1234", "--turn", "on")
        self.assertIn("2 PICO device(s)", out)
        self.assertIn("HOME/Bed: skipped (no PIN)", out)
        self.assertEqual([body["Serial"] for body in self.sent], ["SER1"])

    async def test_raw_log_cloud(self):
        log = logging.getLogger("open_pico_local_api.cloud.pico_cloud_client")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "traffic.log")
            try:
                await self.run_example("raw_log_cloud", *DEVICE, "--file", path)
            finally:  # the example attaches a handler to a global logger: detach and close it
                for handler in log.handlers[:]:
                    log.removeHandler(handler)
                    handler.close()
                log.propagate, log.level = True, logging.NOTSET
            with open(path) as f:
                traffic = f.read()
        self.assertIn("/apiTS/v2/Login", traffic)
        self.assertIn("GetPICOState", traffic)


if __name__ == "__main__":
    unittest.main()
