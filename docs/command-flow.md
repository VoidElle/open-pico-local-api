# Command Flow

Every control method (`turn_on`, `change_fan_speed`, `get_status`, etc.) follows the same
four-step UDP exchange with the device.

## Full Exchange

```
Client                                          Pico Device
  |                                                  |
  |  1. COMMAND  {"cmd":"upd_pico","idp":42,...}    |
  | ------------------------------------------------> |
  |                                                  |
  |  2. ACK      {"res":99,"frm":"mst","idp":42}    |
  | <------------------------------------------------ |
  |                                                  |
  |  3. STATUS   {"cmd":"stato_sync","idp":42,...}   |
  | <------------------------------------------------ |
  |                                                  |
  |  4. ACK      {"res":99,"frm":"app","idp":42}    |
  | ------------------------------------------------> |
  |                                                  |
```

1. **Client sends command** with the next IDP from its allocated range.
2. **Device sends ACK** (`res=99, frm="mst"`) - acknowledges receipt of the command.
3. **Device sends full status** - the updated device state after applying the command.
4. **Client sends ACK** (`res=99, frm="app"`) - acknowledges receipt of the status.

For `get_status` (`stato_sync`) the exchange is identical except step 1 is a read-only probe,
so no state changes occur before step 3.

## Code Path

```
PicoClient.turn_on()
    |
    v
_execute_command_with_retry(cmd_dict)
    |
    +-- _get_next_idp()           # thread-safe counter increment
    |
    +-- _send_udp_packet(cmd)     # JSON encode + sendto via SharedTransportManager
    |
    +-- _wait_for_response(idp, timeout)
            |
            +-- loop: asyncio.wait_for(response_queue.get(), 0.5s)
            |
            +-- res==99 frm=="mst"  -->  got_ack = True
            |
            +-- res!=99             -->  send ACK back, return response
```

## `_wait_for_response` State Machine

```
Start
  |
  v
[waiting] <-------------------------------+
  |                                       |
  | got packet                            | TimeoutError (0.5s slice)
  v                                       |
[check idp]                               |
  | wrong idp  -->  discard, back to [waiting]
  |
  | idp matches
  v
[ACK from device? res==99 frm=="mst"]
  | yes  -->  got_ack=True, record time, back to [waiting]
  | no
  v
[status response]
  |
  +-- send client ACK (res=99, frm="app")
  +-- return response

Timeout conditions:
  - outer loop: loop.time() >= end_time  (self.timeout seconds)
  - after ACK:  loop.time() - ack_received_time > 2.0s  ->  IDP out of sync
```

## Timeout Behaviour

The `timeout` constructor parameter controls the total window for each command attempt.
Default is 5 seconds. The inner `asyncio.wait_for` uses 0.5 s slices so the outer timeout
check runs regularly without blocking indefinitely.

After the ACK is received, the client gives the device an additional 2 seconds to send the
status response. If it does not arrive, the IDP is considered out of sync.
