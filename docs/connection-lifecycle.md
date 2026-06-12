# Connection Lifecycle

## connect()

```
PicoClient.connect()
        |
        +-- already connected? return early
        |
        v
SharedTransportManager.get_instance()
        |
        +-- not initialized?  initialize(local_port, verbose)
        |                     bind UDP socket on 0.0.0.0:40069
        |
        v
register_device(device_id, ip, port, response_queue)
        |
        +-- already registered? return existing IDP range
        |
        +-- allocate next IDP range (protected by _init_lock)
        +-- add to _devices, _idp_sorted_starts, _idp_start_to_device
        |
        v
_idp_counter = _idp_range_start
_connected = True
        |
        +-- poll_jitter > 0?  sleep random(0, poll_jitter)   # thundering herd prevention
```

## disconnect()

```
PicoClient.disconnect()
        |
        +-- not connected? return early
        |
        v
SharedTransportManager.unregister_device(device_id)
        |
        +-- remove from _devices
        +-- remove from _idp_start_to_device
        +-- remove from _idp_sorted_starts  (bisect pop)
        |
        v
_connected = False
```

## Reconnect on Update Failure (Home Assistant pattern)

The coordinator pattern used with Home Assistant does not use the `auto_reconnect` decorator.
Instead it checks `client.connected` before each poll and reconnects manually:

```python
if not client.connected:
    await client.connect()
status = await client.get_status()
```

## auto_reconnect Decorator

`auto_reconnect` is an async decorator for wrapping async methods that should retry on
`PicoConnectionError` or `OSError`:

```python
@auto_reconnect
async def my_method(self):
    ...
```

The decorator checks `self._auto_reconnect`, `self._max_reconnect_attempts`, and
`self._reconnect_delay` on the decorated object. These attributes must be set manually -
`PicoClient` itself does not use this decorator.

Retry flow:

```
call wrapped method
        |
        +-- not connected? await self.connect()
        |
        +-- await func(...)
        |
        +-- PicoConnectionError or OSError?
                |
                +-- attempt < max-1?
                |       await self.disconnect()
                |       await asyncio.sleep(_reconnect_delay)
                |       await self.connect()
                |       continue loop
                |
                +-- last attempt?
                        raise PicoConnectionError
```

## Shared Transport Shutdown

```
SharedTransportManager.shutdown()
        |
        v
transport.close()           # close UDP socket
_transport = None
_initialized = False
_devices.clear()            # drop all registrations
_idp_sorted_starts.clear()
_idp_start_to_device.clear()
_next_idp_range = 1         # reset allocation counter
_unmatched_queue = None
_instance = None            # allow fresh singleton creation
```

After `shutdown()`, calling `get_instance()` creates a brand new `SharedTransportManager`.
Any `PicoClient` instances that were connected before shutdown will have `_connected = True`
but their `_transport_manager` reference points to the old (closed) instance. Always
`disconnect()` all clients before calling `shutdown()`.
