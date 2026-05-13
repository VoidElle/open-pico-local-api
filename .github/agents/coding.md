# Coding Agent — open-pico-local-api

## Project Overview
Async Python library (asyncio) for controlling Tecnosystemi Pico HVAC/ventilation IoT devices over UDP. Used as a local API client, commonly integrated with Home Assistant.

## Architecture
- **`PicoClient`** (`pico_client.py`) — main public API. One instance per device.
- **`SharedTransportManager`** (`shared_transport_manager.py`) — singleton managing a single shared UDP socket, routing packets to the correct `PicoClient` via IDP ranges.
- **`enums/`** — `DeviceModeEnum`, `TargetHumidityEnum`, `OnOffStateEnum`
- **`models/`** — dataclass-style models: `PicoDeviceModel`, `CommandResponseModel`, `DeviceInfoModel`, `OperatingParametersModel`, `SensorReadingsModel`, etc.
- **`exceptions/`** — `PicoDeviceError`, `NotSupportedError`, `ConnectionError`, `TimeoutError`
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
- Guard every public method with `if not self._connected: raise ConnectionError(...)`

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
- Python 3.7+ compatibility required
