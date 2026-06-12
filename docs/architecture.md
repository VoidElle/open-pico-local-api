# Architecture: Shared Transport

## The Port Constraint

Pico devices are hardcoded by the manufacturer to **only respond to packets originating from port 40069**.
This means you cannot open a dedicated UDP socket per device - the OS allows only one process to bind a
given port at a time. A naive one-socket-per-device approach would fail on the second device.

## Solution: One Socket, Many Devices

`SharedTransportManager` binds a single UDP socket on port 40069 and multiplexes all traffic through it.
Each `PicoClient` gets an exclusive numeric range of **IDP (Identifier Packet)** values. Incoming packets
are routed to the correct client by inspecting the `idp` field in the JSON payload.

```
  PicoClient A          PicoClient B          PicoClient C
  device_id="room_a"    device_id="room_b"    device_id="room_c"
  IDP range 1-10000     IDP range 10001-20000 IDP range 20001-30000
       |                      |                      |
       +----------+-----------+----------+-----------+
                  |                      |
                  v                      v
        SharedTransportManager    SharedPicoProtocol
        (singleton)               (asyncio.DatagramProtocol)
                  |                      |
                  +----------+-----------+
                             |
                    UDP socket :40069
                             |
            +----------------+-----------------+
            |                |                 |
       192.168.1.100    192.168.1.101    192.168.1.102
       :40070           :40070           :40070
```

## IDP Range Allocation

When a `PicoClient` calls `connect()`, `SharedTransportManager.register_device()` assigns a
non-overlapping IDP range:

```
Device 1 registered  ->  IDPs    1 - 10 000
Device 2 registered  ->  IDPs 10001 - 20 000
Device 3 registered  ->  IDPs 20001 - 30 000
...
```

The allocation counter (`_next_idp_range`) is protected by `_init_lock` to prevent races when
multiple devices connect simultaneously.

## Packet Routing (O(log n))

`SharedPicoProtocol.datagram_received()` is called for every incoming UDP packet. Routing to the
correct device queue is done in O(log n) via `bisect`:

```
Incoming packet  idp=15432
        |
        v
bisect_right([1, 10001, 20001], 15432) - 1  ==>  index 1
        |
        v
_idp_sorted_starts[1] = 10001
_idp_start_to_device[10001] = "room_b"
        |
        v
_devices["room_b"].response_queue.put_nowait((response, addr))
```

IDP 0 is reserved for discovery and is never allocated to any client. Packets with IDP 0 are
routed to the `unmatched_queue` used by `PicoAutoDiscovery`.

## Singleton Lifecycle

`SharedTransportManager` is a process-level singleton. It is created on the first `get_instance()`
call and destroyed via `shutdown()`. After `shutdown()`, `_instance` is reset to `None` so a fresh
instance can be created on the next `get_instance()` call.

```
get_instance()         initialize()           register_device()
     |                      |                       |
     v                      v                       v
create instance       bind UDP socket         allocate IDP range
_instance = self      _initialized = True     update bisect index
```

## Unregistered Device Cleanup

When `PicoClient.disconnect()` is called, `unregister_device()` removes the device from
`_devices`, `_idp_start_to_device`, and `_idp_sorted_starts`. The IDP range is released but
not reclaimed - new registrations always get a fresh range appended at the top.
