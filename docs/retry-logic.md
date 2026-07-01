# Retry Logic and IDP Synchronization

## Why IDP Can Go Out of Sync

The IDP counter in the client and the device must match for the device to respond. They can
drift apart when:

- The device is power-cycled or firmware-updated while the client is running.
- A UDP packet is lost (UDP has no delivery guarantee).
- The client process was restarted without the device being restarted.

When the IDP is out of sync the device silently ignores commands - it receives the packet but
its internal counter is at a different value, so it discards it.

## Two-Level Retry Strategy

`_execute_command_with_retry` uses a two-level loop:

```
Outer loop: retry_attempts (default 3)  -- full retry with delay between attempts
  |
  +-- Inner loop: max_idp_sync (5)      -- fast IDP re-sync by incrementing IDP
```

### Inner loop: IDP sync

If the device is slightly ahead (e.g., it processed a previous command but the client never
received the response), incrementing the IDP by 1-4 will re-align:

```
attempt 1: send idp=100  -->  no response  (device expects 101)
attempt 2: send idp=101  -->  no response  (device expects 102)
attempt 3: send idp=102  -->  ACK + status (device was at 102)
           "IDP synchronized after 2 increments"
```

### Outer loop: full retry with IDP reset

If all 5 IDP sync attempts fail, the outer loop resets the IDP counter to `_idp_range_start`
and waits `retry_delay` seconds before the next full attempt:

```
Attempt 1/3:
  IDP sync x5 -> all fail
  reset IDP to range start
  sleep retry_delay (2.0s)

Attempt 2/3:
  IDP sync x5 -> fail at 3, succeed at 4
  return response

[or]

Attempt 3/3:
  IDP sync x5 -> all fail
  return None  ->  caller raises PicoTimeoutError
```

## Full Flow Diagram

```
_execute_command_with_retry(cmd)
        |
        v
  attempt = 1..retry_attempts
        |
        +-- attempt > 1? sleep retry_delay, reset IDP
        |
        v
  idp_sync = 0..4
        |
        +-- get next IDP
        +-- send packet
        +-- wait for response (self.timeout seconds)
        |       |
        |       +-- response received  -->  return response (success)
        |       |
        |       +-- timeout            -->  next idp_sync iteration
        |
        +-- all 5 idp_sync failed?
                |
                +-- attempt < max?  reset IDP counter, continue outer loop
                +-- last attempt?   fall through, return None
        |
        v
  return None  -->  PicoTimeoutError raised by caller
```

## Manual IDP Reset

If the device was power-cycled and all automatic retry logic fails, you can manually reset:

```python
await device.reset_idp()
```

This resets `_idp_counter` to `_idp_range_start`. The next command will start from IDP 1
(or whatever the range start is for this device), which is what a freshly booted device also
starts at.

## Bruteforce IDP Recovery (Diagnostic)

`reset_idp()` and the automatic retry logic only help when the device's IDP is close to the
client's expected value - the inner loop probes just 5 consecutive IDPs. If the device counter
has drifted far away (many lost packets, an out-of-band restart, or an unknown starting point),
none of that recovers it and every command silently times out.

`bruteforce_idp()` sweeps a range of IDP values, sending a lightweight `stato_sync` with each
one and waiting a short time for a matching response. On the first hit it realigns the client
counter to the next value so normal commands resume:

```python
result = await device.bruteforce_idp(start=1, end=500, per_idp_timeout=0.3)
if result["found"] is not None:
    print(f"Device responded to IDP {result['found']}")
    status = await device.get_status()  # works again
```

It returns `{"found": <idp or None>, "responsive_idps": [...], "probed": <count>}`.

Keep the range narrow when possible: a full 10000-wide sweep at 0.3s per IDP takes ~50 minutes.
See [`examples/idp_diagnostic.py`](../examples/idp_diagnostic.py) for a ready-to-run tool.
