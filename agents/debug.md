# Debug Agent - open-pico-local-api

## Purpose
Diagnose issues in the async UDP communication stack of this Pico device library.

## Common Failure Modes

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

## Debugging Checklist
1. Enable `verbose=True` on `PicoClient` - all IDP, ACK, and retry events log to `DEBUG`
2. Check `asyncio` event loop is running (not closed) when calling async methods
3. Verify `await client.connect()` completed without raising before issuing commands
4. For multi-device setups, confirm each device gets a distinct IDP range via `SharedTransportManager.register_device`
5. Inspect raw UDP traffic with `tcpdump -i any udp port 40069 or port 40070 -A`
6. Run the test suite to confirm no regressions: `./run_tests.sh`

## Key Code Paths
- Packet routing: `SharedPicoProtocol.datagram_received` → `_find_device_by_idp` → `registration.response_queue.put_nowait`
- Command flow: `public method` → `_execute_command_with_retry` → `_send_udp_packet` → `_wait_for_response`
- IDP allocation: `SharedTransportManager.register_device` assigns `(range_start, range_size)` per device
- Public accessors: use `get_device_registration(device_id)` and `unmatched_queue` property instead of accessing `_devices`/`_unmatched_queue` directly

## Exception Classes
- `PicoDeviceError` - base class
- `PicoConnectionError` - connection/communication failures
- `PicoTimeoutError` - operation timeout
- `NotSupportedError` - command not valid in current mode
