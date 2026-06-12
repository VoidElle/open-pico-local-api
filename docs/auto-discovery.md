# Auto-Discovery Flow

`PicoAutoDiscovery.discover()` scans a subnet and returns the IP addresses of all Pico
devices that respond to a probe.

## How It Works

```
discover(pin, subnet)
        |
        v
SharedTransportManager.get_instance()   # reuse or create shared socket
        |
        v
set_unmatched_queue(queue)              # IDP 0 packets go here during scan
        |
        v
_subnet_scan(...)
        |
        +-- create collect_task         # starts draining unmatched_queue immediately
        |
        +-- asyncio.gather(probe_host   # send probe to every host concurrently
             for each IP in subnet)     # semaphore limits to max_concurrent at a time
        |
        +-- await collect_task          # wait for collection window to finish
        |
        v
clear_unmatched_queue()                 # stop routing unmatched packets
        |
        v
return sorted(discovered)
```

## Probe Packet

Each probe is a `stato_sync` command with **IDP 0** (reserved - never allocated to any
`PicoClient`) and the provided PIN:

```json
{"cmd": "stato_sync", "frm": "app", "pin": "1234", "idp": 0}
```

## Response Validation

A response is accepted as a valid Pico device if it:

- Is a JSON object (dict)
- Has `"idp": 0`
- Contains both `"fw_ver"` and `"mod"` fields

Anything else is silently ignored.

## Concurrent Probe + Collect

Collection starts **immediately** when probing begins (not after all probes are sent). This
means:

- Responses from fast-responding devices are captured during the probe phase itself.
- Total scan time = `max(probe_time, scan_timeout)` instead of `probe_time + scan_timeout`.
- On a /24 subnet this typically saves 1-2 seconds.

```
Time -->

[probe phase: ~0.5s for /24 at max_concurrent=50]
|=====================|
[collect phase: scan_timeout=2.0s, starts at t=0]
|==============================================|

Result collected at t=2.0s  (not t=2.5s)
```

## Relation to Registered Devices

During discovery, `unmatched_queue` receives all packets whose IDP does not belong to any
registered `PicoClient`. Since the probe uses IDP 0 (which is never registered), all device
replies flow into `unmatched_queue` automatically - no conflicts with active clients.

After `discover()` returns, `clear_unmatched_queue()` is called in a `finally` block so
normal routing resumes regardless of errors.

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `pin` | *required* | PIN broadcast to every host |
| `subnet` | *required* | CIDR range, e.g. `"192.168.1.0/24"` (IPv4 only) |
| `device_port` | `40070` | UDP port devices listen on |
| `local_port` | `40069` | Local port for `SharedTransportManager` |
| `scan_timeout` | `2.0` | Collection window in seconds |
| `max_concurrent` | `50` | Max simultaneous in-flight probes |
| `verbose` | `False` | Enable debug logging |

## Limitations

- IPv6 subnets are not supported (raises `ValueError`).
- Only devices sharing the given PIN will respond. Devices with a different PIN are silently
  missed.
- Discovery uses a fire-and-forget UDP probe. There is no guarantee every device receives
  every probe on a congested network.
