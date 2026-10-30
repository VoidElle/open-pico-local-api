---
name: debug
description: Diagnoses failures in open-pico-local-api - local UDP issues (timeouts, IDP drift, routing) and cloud fallback issues (login, token, PIN, stale state). Use when a PicoClient or PicoCloudClient call fails or misbehaves.
---

# Debug Agent - open-pico-local-api

## Purpose
Diagnose issues in this Pico device library: the async UDP stack (`PicoClient`) and the cloud fallback (`PicoCloudClient`, HTTPS). First establish which client is in use; most UDP failure modes below do not apply to the cloud.

## Common Failure Modes (local UDP)

### IDP out-of-sync
**Symptom:** Commands time out; `_wait_for_response` drains queue but no match.  
**Cause:** Device IDP counter diverged from client (e.g., device restarted, packet loss burst).  
**Fix:** Call `await client.reset_idp()` to realign; check `_idp_range_start` allocation in `SharedTransportManager`.

### Port conflict / no response at all
**Symptom:** Zero packets received; `SharedPicoProtocol.datagram_received` never fires.  
**Cause:** Another process holds UDP port 40069, or firewall blocks UDP.  
**Fix:** Verify only one `SharedTransportManager` instance is initialized; check `is_initialized` flag.

### Wrong device gets response
**Symptom:** IDP matches but parsed data is from a different device.  
**Cause:** IDP ranges overlap between two `PicoClient` instances.  
**Fix:** Inspect `_find_device_by_idp` in `SharedTransportManager`; ensure ranges don't overlap after `register_device`.

### ACK received but no status response
**Symptom:** `got_ack = True` but `_wait_for_response` returns `None` after `ack_timeout`.  
**Cause:** Device acknowledged command but status update packet was lost or delayed.  
**Fix:** Increase `ack_timeout` or `retry_delay`; check device-side logs.

### `NotSupportedError` on valid command
**Symptom:** Fan speed or humidity command raises `NotSupportedError`.  
**Cause:** Current device mode not in `MODULAR_FAN_SPEED_PRESET_MODES` or `HUMIDITY_SELECTOR_PRESET_MODES`.  
**Fix:** Change operating mode first via `change_operating_mode()`; or pass `force=True` to bypass guard.

## Common Failure Modes (cloud)
Protocol reference: `docs/app/http-flows/` (`01` auth/token, `02` login codes, `04` runtime, `06` quirks).

### Login rejected
**Symptom:** `PicoAuthError` from `connect()`.  
**Cause:** login `ResCode` != 0; message comes from `_LOGIN_ERRORS` (1 wrong credentials, 2 email not confirmed, 6 temporary password, 10 terms not accepted, ...).  
**Fix:** codes 2, 6, 7, 10 need action in the official app; the library cannot resolve them.

### Repeated 401 / session loss
**Symptom:** `PicoAuthError("Unauthorized (token rejected)")` after retries.  
**Cause:** rolling token counter out of sync (token bumped without the call reaching the server, or two clients sharing one token), or session past 1 h. `_device_call` forces re-login on 401 and after `SESSION_TTL` (55 min).  
**Fix:** check `_login_time`/`_token` handling in `_device_call`; ensure every call goes through it under `_command_lock`.

### Wrong PIN
**Symptom:** `PicoDeviceError("Wrong PIN")`.  
**Cause:** `ResCode 2` on a device endpoint; serial/PIN mismatch (serial is upper-cased).  
**Fix:** verify with `get_devices()` that the serial belongs to the account and the PIN is correct.

### Command "succeeds" but state does not change
**Symptom:** command returns, `get_status()` still shows old values.  
**Cause:** expected: `SendPicoCmd` is only a cloud ack, delivery to the device is asynchronous (backend -> MQTT, inferred). No `res: 99` ACK exists in cloud mode.  
**Fix:** poll `get_status()` for a few seconds (the app polls every 5 s). If it never applies, the device may be offline from the cloud.

### Cloud status: sensors at 0 or LED state inverted
**Symptom:** cloud `get_status()` shows temperature/humidity `0`, empty `par_rt`, `memfree` 0, or `is_led_state_on` True with the LED off.  
**Cause:** `ResDescr` parsed from the flat `frm:"db"` fields instead of `lastpk`. Sensors exist only in `lastpk`; the db copy re-encodes `led_on_off_breve` (off = `0`, device sends `2`).  
**Fix:** keep the merge in `PicoCloudClient.get_status` with `lastpk` winning. Compare both copies with `verbose=True` or `examples/cloud/raw_log_cloud.py`.

### Other cloud errors
- `PicoDeviceError("Cloud rejected request (ResCode N)")` - server-side logical error (HTTP 400 carries the same body)
- `PicoDeviceError("Non-JSON reply ...")` - backend/proxy error page
- `PicoTimeoutError` / `PicoConnectionError` - network; `timeout` is per request (`aiohttp.ClientTimeout`)
- `NotSupportedError` from `bruteforce_idp` - by design; IDP is not negotiated in cloud mode, `reset_idp` only resets the client counter

## Debugging Checklist
1. Enable `verbose=True` on `PicoClient` - all IDP, ACK, and retry events log to `DEBUG`
2. Check `asyncio` event loop is running (not closed) when calling async methods
3. Verify `await client.connect()` completed without raising before issuing commands
4. For multi-device setups, confirm each device gets a distinct IDP range via `SharedTransportManager.register_device`
5. Inspect raw UDP traffic with `tcpdump -i any udp port 40069 or port 40070 -A`
6. Run the test suite to confirm no regressions: `./scripts/run_tests.sh` (needs `aiohttp` and `cryptography`: `pip install -e .`)
7. Cloud: `verbose=True` logs every HTTP request/response (`→`/`←`) on `open_pico_local_api.cloud.pico_cloud_client`; scripts in `examples/cloud/` reproduce single calls. Logs contain the account email and PIN - redact before sharing

## Key Code Paths
- Packet routing: `SharedPicoProtocol.datagram_received` → `_find_device_by_idp` → `registration.response_queue.put_nowait`
- Command flow: `public method` → `_execute_command_with_retry` → `_send_udp_packet` → `_wait_for_response`
- IDP allocation: `SharedTransportManager.register_device` assigns `(range_start, range_size)` per device
- Public accessors: use `get_device_registration(device_id)` and `unmatched_queue` property instead of accessing `_devices`/`_unmatched_queue` directly
- Cloud command flow: inherited public method -> `PicoCloudClient._execute_command_with_retry` -> `_device_call` (lock, retry, re-login, token bump) -> `_request` (aiohttp, maps errors/401)
- Cloud status: `get_status` -> `GET GetPICOState` -> `ResDescr` (flat db fields + `lastpk` device packet, `lastpk` wins) -> `PicoDeviceModel.from_dict`

## Exception Classes
- `PicoDeviceError` - base class
- `PicoConnectionError` - connection/communication failures
- `PicoTimeoutError` - operation timeout
- `NotSupportedError` - command not valid in current mode (or not available in cloud mode)
- `PicoAuthError` - cloud login rejected or token refused; subclass of `PicoDeviceError`, import from `open_pico_local_api.cloud`
