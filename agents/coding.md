---
name: coding
description: Implements features and fixes in open-pico-local-api, the async Python client for Tecnosystemi Pico devices (local UDP and cloud fallback). Use for any code change in open_pico_local_api/, tests/ or examples/.
---

# Coding Agent - open-pico-local-api

## Project Overview
Async Python library (asyncio, Python 3.11+) for controlling Tecnosystemi Pico HVAC/ventilation IoT devices. Primary path is local UDP; `PicoCloudClient` is a fallback over the vendor's HTTPS backend, used only when a local connection is not possible. Commonly integrated with Home Assistant.

## Architecture
- **`PicoClient`** (`pico_client.py`) - main public API. One instance per device.
- **`SharedTransportManager`** (`shared_transport_manager.py`) - singleton managing a single shared UDP socket, routing packets to the correct `PicoClient` via IDP ranges.
- **`enums/`** - `DeviceModeEnum`, `TargetHumidityEnum`, `OnOffStateEnum`
- **`models/`** - dataclass-style models: `PicoDeviceModel`, `CommandResponseModel`, `DeviceInfoModel`, `OperatingParametersModel`, `SensorReadingsModel`, etc.
- **`exceptions/`** - `PicoDeviceError` (base), `PicoConnectionError`, `PicoTimeoutError`, `NotSupportedError`
- **`utils/auto_reconnect.py`** - `@auto_reconnect` decorator for retrying on `PicoConnectionError`
- **`utils/pico_protocol.py`** - base `PicoProtocol` asyncio `DatagramProtocol`
- **`utils/constants.py`** - preset mode lists (e.g., `MODULAR_FAN_SPEED_PRESET_MODES`, `HUMIDITY_SELECTOR_PRESET_MODES`)
- **`cloud/`** - cloud fallback, imported from `open_pico_local_api.cloud` (not re-exported at top level):
  - `PicoCloudClient` (`pico_cloud_client.py`) - subclass of `PicoClient`; overrides `connect`, `disconnect`, `get_status`, `reset_idp`, `bruteforce_idp` and `_execute_command_with_retry`. Adds `get_plants`, `get_devices`, `use_device`
  - `PicoCipher` (`crypto.py`) - app AES scheme: key = SHA-256(`android_id[:8]` + `ns91wr48`), CBC, zero IV; rolling token via `next_token`
  - `PicoAuthError` (`exceptions.py`) - subclass of `PicoDeviceError`; login rejected or token refused (HTTP 401)

## Cloud Protocol
Reverse-engineered from the official app; spec in `docs/app/http-flows/` (read it before touching `cloud/`).
- One backend `https://proair.azurewebsites.net` (`aiohttp`); `/apiTS/*` = account, `/api/*` = devices
- Auth: Basic `<email>:PwdProAir` (`UsrProAir` before login) + `Token` header. Login uses `FIX_TOKEN`; every later call bumps the rolling token counter (decrypt `<text>_<n>`, n+1, re-encrypt)
- Session is 1 h hard from login, no refresh: client re-logs in after `SESSION_TTL` (55 min) or on HTTP 401
- Replies are `{ResCode, ResDescr}`; HTTP 400 carries the same body. `ResCode 0` OK, `2` wrong PIN. Login codes in `_LOGIN_ERRORS`
- `GetPICOState`: `ResDescr` is the backend `frm:"db"` record (control fields only) plus `lastpk`, a JSON string of the device's last `stato_sync`. `get_status` merges them with `lastpk` winning, then `PicoDeviceModel.from_dict`. Never let the flat fields win: they re-encode some values (`led_on_off_breve` off = `0` instead of `2`). Details: `docs/app/http-flows/04-pico-cloud-runtime.md`
- `SendPicoCmd`: device command dict serialized as a string in `Cmd`, with `frm: "mqtt"` and the client's own `idp` (1..501 counter). The cloud only acks; the device applies the command asynchronously, no `res: 99` ACK

## UDP Protocol
- JSON payloads over UDP (port 40070 device, 40069 local)
- Every message carries `idp` (incrementing packet ID) for request/response correlation
- ACK packet: `{"idp": N, "frm": "app", "res": 99}`
- Commands include: `stato_sync` (get status), `upd_pico` (set state)
- IDP ranges allocated per device to avoid conflicts across multiple clients

## Coding Conventions
- All I/O methods are `async`; use `asyncio.Lock` for shared state
- Raise typed exceptions from `exceptions/` - never raw `Exception`
- `verbose` flag gates all debug logging via `_LOGGER.debug`
- New commands follow the `_execute_command_with_retry` pattern
- Models use `from_dict(response)` factory methods
- Guard every public method with `if not self._connected: raise PicoConnectionError(...)`
- Use `inspect.iscoroutinefunction()` - **not** `asyncio.iscoroutinefunction()` (deprecated Python 3.14)
- IPv6 subnets are **not supported** in discovery - `_subnet_scan` raises `ValueError` on non-IPv4 CIDRs

## Auto-Discovery
`PicoAutoDiscovery.discover(pin, subnet, ...)` in `pico_auto_discovery.py` returns `List[str]` of discovered IPs.  
Strategy: concurrent per-IP scan of the CIDR subnet provided (IPv4 only).  
**All traffic uses `SharedTransportManager` (port 40069)** - Pico devices are hardcoded by the manufacturer to reply only to port 40069. Discovery uses IDP=0 (never allocated to any `PicoClient` range) so the manager routes those replies into a temporary `unmatched_queue`.  
Valid Pico response identified by: `idp == 0`, `fw_ver` present, `mod` present.

## Adding a New Command
1. Add enum value if needed in `enums/`
2. Build `cmd` dict with required keys + `"cmd": "upd_pico"`, `"frm": "app"`, `"pin": self.pin`
3. Call `await self._execute_command_with_retry(cmd, retry)` - never `_send_udp_packet` directly, or `PicoCloudClient` will not inherit the command (it overrides `frm`/`idp` and posts to `SendPicoCmd`)
4. Return `CommandResponseModel.from_dict(result)` - do not read device state from `result`: in cloud mode it is only `{idp, frm, cmd}`
5. Add mode guard via `get_status()` if command is mode-restricted (works in both clients)
6. If the command has a request/response reply (like `get_fasce`), the cloud returns the device reply in `ResDescr`; `PicoCloudClient` needs its own override

## Key Constraints
- Never create a new UDP socket per device - always use `SharedTransportManager`
- Legacy mode (`use_shared_transport=False`) is intentionally unimplemented; do not implement it
- IDP must wrap within the allocated range `[_idp_range_start, _idp_range_start + _idp_range_size)` (UDP only; cloud uses its own `_cloud_idp` counter and never registers with `SharedTransportManager`)
- `PicoClient` changes ripple into `PicoCloudClient`: keep `_execute_command_with_retry(cmd_dict, retry)` and the overridden method signatures in sync, and check `tests/cloud/`
- Local is the primary path: do not make the cloud a default or automatic route
- Never log credentials: `verbose` logs HTTP bodies, so keep secrets out of them beyond what the app protocol requires (password is sent AES-encrypted)
- Python 3.11+ required

## Testing
- Test suite lives in `tests/` - 101 tests (`tests/local/` UDP, `tests/cloud/` cloud client); runtime deps: `aiohttp`, `cryptography` (install with `pip install -e .`, otherwise `tests/cloud` fails to import and only 97 tests run)
- Cloud tests run against a local fake backend (`aiohttp.test_utils.TestServer` + `base_url`) that enforces the rolling-token counter; never hit the real backend in tests
- Run locally: `./scripts/run_tests.sh` or `python3 -W all -m unittest discover -s tests -t . -v`
- CI runs on push/PR via `.github/workflows/tests.yml` (Python 3.11, 3.12, 3.13)
- Always run tests after changes; all 101 must pass with `-W all` (zero warnings)
- `SharedTransportManager` singleton tests must reset `_instance = None; _lock = None` in `setUp`
