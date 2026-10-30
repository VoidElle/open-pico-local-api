"""Offline tests: fake backend that enforces the rolling-token counter."""
import json
import unittest

from aiohttp import web
from aiohttp.test_utils import TestServer

from open_pico_local_api.cloud import PicoCloudClient, PicoAuthError
from open_pico_local_api.cloud.crypto import PicoCipher
from open_pico_local_api import DeviceModeEnum, PicoDeviceError

ANDROID_ID = "0123456789abcdef"
# Real GetPICOState shape: flat backend ("db") fields + `lastpk` = last device packet as a JSON string.
STATE = {"cmd": "stato_sync", "frm": "db", "res": 1, "mod": 6, "on_off": 1, "spd_rich": 100,
         "name": "VMC - CG", "led_on_off_breve": 0, "reset": None, "timezone": None,
         "lastpk": json.dumps({"idp": 13398, "frm": "mst", "cmd": "stato_sync", "res": 1, "mod": 6,
                               "on_off": 1, "name": "Camera grande", "led_on_off_breve": 2, "fw_note": "RC00",
                               "v_tmpr": 21.5, "v_umd": 45.0, "memfree": 96828})}


def make_backend(sent: list) -> web.Application:
    cipher = PicoCipher(ANDROID_ID)
    state = {"counter": 1}

    async def login(req):
        body = await req.json()
        assert req.headers["Token"] == "Ga5mM61KCm5Bk18lhD5J999jC2Mu0Vaf"
        if cipher.decrypt(body["Password"]) != "secret":
            return web.json_response({"ResCode": 1})
        return web.json_response({"ResCode": 0, "ID": 7, "ListPlants": "[]",
                                  "Token": cipher.encrypt("sess_1").replace("\n", "")})

    def check_token(req):
        text, _, n = cipher.decrypt(req.headers["Token"]).rpartition("_")
        state["counter"] += 1
        return int(n) == state["counter"]

    async def get_state(req):
        if not check_token(req) or req.query["PIN"] != "1234":
            return web.json_response({"ResCode": 2}, status=400)
        return web.json_response({"ResCode": 0, "ResDescr": json.dumps(STATE)})

    async def send_cmd(req):
        if not check_token(req):
            return web.Response(status=401)
        sent.append(await req.json())
        return web.json_response({"ResCode": 0})

    async def plants(req):
        if not check_token(req):
            return web.Response(status=401)
        return web.json_response({"ResCode": 0, "ResDescr": json.dumps([
            {"LVPL_Id": 1, "LVPL_Name": "HOME", "ListDevices": [
                {"Serial": "SER1", "Name": "Living", "LVDV_Type": 1},
                {"Serial": "SER2", "Name": "Bed", "LVDV_Type": 1}]}])})

    app = web.Application()
    app.router.add_get("/api/v1/GetPlants", plants)
    app.router.add_post("/apiTS/v2/Login", login)
    app.router.add_get("/api/v1/GetPICOState", get_state)
    app.router.add_post("/api/v1/SendPicoCmd", send_cmd)
    return app


class CloudClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.sent = []
        self.server = TestServer(make_backend(self.sent))
        await self.server.start_server()

    async def asyncTearDown(self):
        await self.server.close()

    def client(self, password="secret", pin="1234"):
        return PicoCloudClient("a@b.c", password, "ser1", pin, device_id=ANDROID_ID,
                               base_url=str(self.server.make_url("")), retry_delay=0)

    async def test_status_and_command(self):
        async with self.client() as c:
            status = await c.get_status()          # token counter 2
            self.assertEqual(status.operating.mode, DeviceModeEnum.COMFORT_SUMMER)
            self.assertEqual((status.sensors.temperature_celsius, status.sensors.humidity_percent), (21.5, 45.0))
            self.assertEqual((status.idp, status.system.memory_free), (13398, 96828))
            # db re-encodes LED off as 0; the device's 2 must win.
            self.assertEqual((status.device_info.name, status.operating.is_led_state_on), ("Camera grande", False))
            self.assertEqual(status.operating.speed_requested, 100)  # db-only key still used
            await c.change_operating_mode(DeviceModeEnum.HEAT_RECOVERY)   # counter 3
        cmd = json.loads(self.sent[0]["Cmd"])
        self.assertEqual((cmd["cmd"], cmd["frm"], cmd["mod"], cmd["pin"]), ("upd_pico", "mqtt", 1, "1234"))
        self.assertEqual(self.sent[0]["Serial"], "SER1")

    async def test_login_only_list_devices_and_switch(self):
        c = PicoCloudClient("a@b.c", "secret", device_id=ANDROID_ID,
                            base_url=str(self.server.make_url("")), retry_delay=0)
        async with c:
            devices = await c.get_devices()
            self.assertEqual([d["Serial"] for d in devices], ["SER1", "SER2"])
            self.assertEqual(devices[0]["PlantName"], "HOME")
            c.use_device("ser2", "1234")
            await c.turn_on()
        self.assertEqual(self.sent[0]["Serial"], "SER2")

    async def test_bad_password(self):
        with self.assertRaises(PicoAuthError):
            await self.client(password="nope").connect()

    async def test_wrong_pin(self):
        async with self.client(pin="0000") as c:
            with self.assertRaises(PicoDeviceError):
                await c.get_status(retry=False)


class CryptoTest(unittest.TestCase):
    def test_roundtrip_and_token(self):
        c = PicoCipher(ANDROID_ID)
        self.assertEqual(c.decrypt(c.encrypt("hello")), "hello")
        self.assertTrue(c.encrypt("hello").endswith("\n"))
        self.assertEqual(c.decrypt(c.next_token(c.encrypt("x_y_5"))), "x_y_6")


if __name__ == "__main__":
    unittest.main()
