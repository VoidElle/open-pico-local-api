"""
PicoClient drop-in that talks to the Tecnosystemi cloud instead of UDP.

Commands (turn_on, change_operating_mode, ...) are inherited from PicoClient: they only build
the device command dict and call `_execute_command_with_retry`, which is replaced here by a
`SendPicoCmd` REST call. See docs/app/http-flows/ for the protocol.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import aiohttp

from ..pico_client import PicoClient
from ..exceptions.not_supported_error import NotSupportedError
from ..exceptions.pico_connection_error import PicoConnectionError
from ..exceptions.pico_device_error import PicoDeviceError
from ..exceptions.pico_timeout_error import PicoTimeoutError
from ..models.pico_device_model import PicoDeviceModel

from .crypto import PicoCipher
from .exceptions import PicoAuthError

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://proair.azurewebsites.net"
FIX_TOKEN = "Ga5mM61KCm5Bk18lhD5J999jC2Mu0Vaf"  # token for unauthenticated calls
BASIC_PWD = "PwdProAir"
SESSION_TTL = 55 * 60  # server session lasts 1 h from login, no refresh endpoint

_LOGIN_ERRORS = {
    1: "wrong user or password",
    2: "user must confirm the email first",
    3: "user blocked",
    4: "user not found",
    6: "temporary password: change it in the official app",
    7: "request a new temporary password",
    10: "terms of use / privacy not accepted: accept them in the official app",
}


class PicoCloudClient(PicoClient):
    def __init__(
            self,
            email: str,
            password: str,
            serial: str = "",
            pin: str = "",
            name: str = "",
            device_id: Optional[str] = None,
            base_url: str = BASE_URL,
            timezone: str = "Europe@Rome",
            timeout: float = 15,
            retry_attempts: int = 3,
            retry_delay: float = 2.0,
            verbose: bool = False,
    ):
        super().__init__(ip="cloud", pin=pin, device_id=serial.upper() or "account", timeout=timeout,
                         retry_attempts=retry_attempts, retry_delay=retry_delay, verbose=verbose)
        self.email = email
        self.password = password
        self.serial = serial.upper()
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.timezone = timezone  # Java zone id with "/" -> "@"
        # Stands in for ANDROID_ID: it is the AES key seed and is sent as `DeviceId` at login.
        self.android_id = device_id or uuid.uuid4().hex[:16]
        self._cipher = PicoCipher(self.android_id)
        self._session: Optional[aiohttp.ClientSession] = None
        self._token = ""
        self._login_time = 0.0
        self._cloud_idp = 0
        self.plants: List[Dict[str, Any]] = []

    # ----------------------------
    # CONNECTION
    # ----------------------------

    async def connect(self) -> None:
        if self._connected:
            return
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        try:
            await self._login()
        except BaseException:
            await self._session.close()
            self._session = None
            raise
        self._connected = True

    async def disconnect(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        self._token = ""
        self._connected = False

    async def _login(self) -> None:
        body = {
            "Username": self.email,
            "Password": self._cipher.encrypt(self.password),
            "DeviceId": self.android_id,
            "Timezone": self.timezone,
            "TokenPush": "",  # FCM token: none, so no push notifications
            "Platform": "fcm2",
        }
        res = await self._request("POST", "/apiTS/v2/Login", body, token=FIX_TOKEN, user=None)
        code = res.get("ResCode", -1)
        if code != 0:
            raise PicoAuthError(_LOGIN_ERRORS.get(code, f"login failed (ResCode {code})"))
        self._token = res["Token"]
        self._login_time = time.monotonic()
        plants = res.get("ListPlants") or "[]"
        self.plants = json.loads(plants) if isinstance(plants, str) else plants

    # ----------------------------
    # PUBLIC API (only what differs from PicoClient)
    # ----------------------------

    async def get_status(self, retry: bool = True) -> PicoDeviceModel:
        """
        GET GetPICOState. `ResDescr` is the backend's `frm:"db"` record: control fields (on_off, mod,
        speed, led_*, name, ...) flat, plus `lastpk` = JSON string of the last device `stato_sync`,
        the only place with sensors, parameter arrays and system info. Parsed like a local reply.
        """
        self._require_connected()
        res = await self._device_call(
            "GET", f"/api/v1/GetPICOState?picoSerial={self.serial}&PIN={self.pin}", None, retry)
        try:
            descr = res["ResDescr"]
            state = json.loads(descr) if isinstance(descr, str) else descr
            last = state.get("lastpk") or {}
            if isinstance(last, str):
                last = json.loads(last)
            # lastpk wins: the db copy re-encodes some fields (led_on_off_breve off = 0, device sends 2),
            # so only lastpk matches the local protocol the model parses. db only fills missing keys.
            return PicoDeviceModel.from_dict({**{k: v for k, v in state.items() if v is not None}, **last})
        except Exception as e:
            raise PicoDeviceError(f"Failed to parse device status: {e}")

    async def get_plants(self) -> List[Dict[str, Any]]:
        """GET GetPlants: plants and the devices bound to this account."""
        self._require_connected()
        res = await self._device_call("GET", "/api/v1/GetPlants", None, True)
        descr = res.get("ResDescr") or "[]"
        self.plants = json.loads(descr) if isinstance(descr, str) else descr
        return self.plants

    async def get_devices(self) -> List[Dict[str, Any]]:
        """Flat list of the account's devices (Serial, Name, LVDV_Type 1 = PICO, ...) + `PlantName`."""
        return [{**d, "PlantName": p.get("LVPL_Name", "")}
                for p in await self.get_plants() for d in p.get("ListDevices") or []]

    def use_device(self, serial: str, pin: str, name: str = "") -> None:
        """Point this logged-in session at another device (one login, many devices)."""
        self.serial, self.device_id, self.pin, self.name = serial.upper(), serial.upper(), pin, name

    async def reset_idp(self) -> None:
        self._cloud_idp = 0

    async def bruteforce_idp(self, *args, **kwargs):
        raise NotSupportedError("IDP is not negotiated with the device in cloud mode")

    # ----------------------------
    # INTERNAL
    # ----------------------------

    def _require_connected(self) -> None:
        if not self._connected:
            raise PicoConnectionError("Not connected to cloud")

    def _next_idp(self) -> int:
        # Same counter as PicoActivity.getIDP: >500 -> 1, then +1.
        if self._cloud_idp > 500:
            self._cloud_idp = 1
        self._cloud_idp += 1
        return self._cloud_idp

    async def _execute_command_with_retry(self, cmd_dict: Dict[str, Any], retry: bool = True) -> Optional[Dict[str, Any]]:
        """POST SendPicoCmd. The cloud only acks (ResCode 0); real state shows in get_status()."""
        cmd = {**cmd_dict, "frm": "mqtt", "idp": self._next_idp()}
        body = {"Serial": self.serial, "Pin": self.pin, "Name": self.name, "Cmd": json.dumps(cmd)}
        await self._device_call(
            "POST", f"/api/v1/SendPicoCmd?picoSerial={self.serial}&PIN={self.pin}", body, retry)
        return {"idp": cmd["idp"], "frm": "mqtt", "cmd": cmd.get("cmd", "")}

    async def _device_call(self, method: str, path: str, body: Optional[dict], retry: bool) -> Dict[str, Any]:
        """Authenticated call with retry; re-logs in when the session is old or the server says 401."""
        async with self._command_lock:
            attempts = self.retry_attempts if retry else 1
            last: Exception = PicoTimeoutError("Request failed")
            for attempt in range(1, attempts + 1):
                if attempt > 1:
                    await asyncio.sleep(self.retry_delay)
                try:
                    if time.monotonic() - self._login_time > SESSION_TTL:
                        await self._login()
                    self._token = self._cipher.next_token(self._token)  # app keeps the bumped token too
                    res = await self._request(method, path, body, token=self._token, user=self.email)
                except PicoAuthError as e:
                    last = e
                    self._login_time = 0  # force relogin next attempt
                    continue
                except (PicoConnectionError, PicoTimeoutError) as e:
                    last = e
                    continue
                code = res.get("ResCode", -1)
                if code == 0:
                    return res
                if code == 2:
                    raise PicoDeviceError("Wrong PIN")
                raise PicoDeviceError(f"Cloud rejected request (ResCode {code})")
            raise last

    async def _request(self, method: str, path: str, body: Optional[dict], token: str,
                       user: Optional[str]) -> Dict[str, Any]:
        if not self._session:
            raise PicoConnectionError("Not connected to cloud")
        basic = base64.b64encode(f"{user or 'UsrProAir'}:{BASIC_PWD}".encode()).decode()
        headers = {"Authorization": f"Basic {basic}", "Token": token}
        if method == "GET":
            headers["UserObj-Agent"] = "benincapp"
        if self.verbose:
            _LOGGER.debug("→ %s %s %s", method, path, body)
        try:
            async with self._session.request(method, self.base_url + path, headers=headers, json=body) as r:
                text = await r.text()
                status = r.status
        except asyncio.TimeoutError as e:
            raise PicoTimeoutError(f"{method} {path} timed out") from e
        except aiohttp.ClientError as e:
            raise PicoConnectionError(f"{method} {path} failed: {e}") from e
        if self.verbose:
            _LOGGER.debug("← %s %s", status, text)
        if status == 401:
            raise PicoAuthError("Unauthorized (token rejected)")
        try:
            return json.loads(text)
        except ValueError:
            raise PicoDeviceError(f"Non-JSON reply (HTTP {status}): {text[:100]}")
