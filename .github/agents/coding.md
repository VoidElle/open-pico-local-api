# Coding Agent — open-pico-local-api

## Project Overview
Async Python library (asyncio, Python 3.11+) for controlling Tecnosystemi Pico HVAC/ventilation IoT devices over UDP. Used as a local API client, commonly integrated with Home Assistant.

## Architecture
- **`PicoClient`** (`pico_client.py`) — main public API. One instance per device.
- **`SharedTransportManager`** (`shared_transport_manager.py`) — singleton managing a single shared UDP socket, routing packets to the correct `PicoClient` via IDP ranges.
- **`enums/`** — `DeviceModeEnum`, `TargetHumidityEnum`, `OnOffStateEnum`
- **`models/`** — dataclass-style models: `PicoDeviceModel`, `CommandResponseModel`, `DeviceInfoModel`, `OperatingParametersModel`, `SensorReadingsModel`, etc.
- **`exceptions/`** — `PicoDeviceError` (base), `PicoConnectionError`, `PicoTimeoutError`, `NotSupportedError`
- **`utils/auto_reconnect.py`** — `@auto_reconnect` decorator for retrying on `PicoConnectionError`
- **`utils/pico_protocol.py`** — base `PicoProtocol` asyncio `DatagramProtocol`
- **`utils/constants.py`** — preset mode lists (e.g., `MODULAR_FAN_SPEED_PRESET_MODES`, `HUMIDITY_SELECTOR_PRESET_MODES`)

## UDP Protocol
- JSON payloads over UDP (port 40070 device, 40069 local)
- Every message carries `idp` (incrementing packet ID) for request/response correlation
- ACK packet: `{"idp": N, "frm": "app", "res": 99}`
- Commands include: `stato_sync` (get status), `upd_pico` (set state)
- IDP ranges allocated per device to avoid conflicts across multiple clients

## Coding Conventions
- All I/O methods are `async`; use `asyncio.Lock` for shared state
- Raise typed exceptions from `exceptions/` — never raw `Exception`
- `verbose` flag gates all debug logging via `_LOGGER.debug`
- New commands follow the `_execute_command_with_retry` pattern
- Models use `from_dict(response)` factory methods
- Guard every public method with `if not self._connected: raise PicoConnectionError(...)`
- Use `inspect.iscoroutinefunction()` — **not** `asyncio.iscoroutinefunction()` (deprecated Python 3.14)
- IPv6 subnets are **not supported** in discovery — `_subnet_scan` raises `ValueError` on non-IPv4 CIDRs

## Auto-Discovery
`PicoAutoDiscovery.discover(pin, subnet, ...)` in `pico_auto_discovery.py` returns `List[str]` of discovered IPs.  
Strategy: concurrent per-IP scan of the CIDR subnet provided (IPv4 only).  
**All traffic uses `SharedTransportManager` (port 40069)** — Pico devices are hardcoded by the manufacturer to reply only to port 40069. Discovery uses IDP=0 (never allocated to any `PicoClient` range) so the manager routes those replies into a temporary `unmatched_queue`.  
Valid Pico response identified by: `idp == 0`, `fw_ver` present, `mod` present.

## Adding a New Command
1. Add enum value if needed in `enums/`
2. Build `cmd` dict with required keys + `"cmd": "upd_pico"`, `"frm": "app"`, `"pin": self.pin`
3. Call `await self._execute_command_with_retry(cmd, retry)`
4. Return `CommandResponseModel.from_dict(result)`
5. Add mode guard via `get_status()` if command is mode-restricted

## Key Constraints
- Never create a new UDP socket per device — always use `SharedTransportManager`
- Legacy mode (`use_shared_transport=False`) is intentionally unimplemented; do not implement it
- IDP must wrap within the allocated range `[_idp_range_start, _idp_range_start + _idp_range_size)`
- Python 3.11+ required

## Testing
- Test suite lives in `tests/` — 96 tests, stdlib only, zero dependencies
- Run locally: `./run_tests.sh` or `python3 -W all -m unittest discover -s tests -v`
- CI runs on push/PR via `.github/workflows/tests.yml` (Python 3.11, 3.12, 3.13)
- Always run tests after changes; all 96 must pass with `-W all` (zero warnings)
- `SharedTransportManager` singleton tests must reset `_instance = None; _lock = None` in `setUp`
