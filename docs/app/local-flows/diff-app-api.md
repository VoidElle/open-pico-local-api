# Report: Tecnosystemi app (PICO) vs `open_pico_local_api` mismatches

Date: 2026-10-26. Compares the flows extracted from the decompiled app (the other files in this folder) with the implementation (`../../../open_pico_local_api`, `examples/`, `README.md`, `docs/*.md`).

Scope: single-device setup only (no master/slave).

Method: 4 comparison agents (transport, runtime, provisioning, firmware) + 4 adversarial verifiers. Only `confirmed` or `partial` findings are reported (with the verifier's correction); 1 refuted finding was dropped. Duplicate findings across areas were merged.

> **App-side verification:** the first analysis used the snippets in this folder, because the sources were temporarily unavailable. A second, targeted pass on the restored source confirmed:
> - #1, #5, #6, #7, #8, #9: `Commands/UDPSocket.java:56-176, 228-325`
> - #10-#13: `Model/Pico.java:409-437`
> - #14: `CmdPICO.java:160-173`, `PicoActivity.java:1488`
> - #3: `PicoActivity.java:568-575`
> - #2 with a correction (see below)
> - OTA, 1300 B / 20 ms / `ota_end` / `ap_m:5`: `PicoBootloaderActivity.java:315-341`
> - 1.0.3 threshold: `PicoBootloaderActivity.java:351`, `CheckLedPICOActivity.java:112`
>
> A third pass (2 Sonnet agents) checked every remaining point, #4 to #27, against the real source. The corrections are merged into each point: #4, #17 (`timezone`), #20/#23, #24 (`upd_datetime`), #27. The library side is verified against the code.

Confirmed in the field: the PICO always replies to UDP 40069, whatever the source port.

## Summary

| # | Sev. | Type | Title |
|---|------|------|-------|
| 1 | medium | wire | Retry: up to 15 sends, even after an ACK (app: max 3, never after an ACK) |
| 2 | medium | parsing | `res` never checked: error / wrong PIN reported as success |
| 3 | medium | parsing | `err` with all-zero arrays → `has_errors=True` forever |
| 4 | medium | lib-doc | `local_port` presented as configurable with no warning (port rule in `architecture.md` fixed) |
| 5 | low | wire | Device ACK recognised only with `frm=="mst"`; fixed 2 s wait after the ACK |
| 6 | low | wire | Client ACK sent only for the expected idp (app: ACK for every message with `res != 99`) |
| 7 | low | wire | Message without `res` and with the expected idp treated as the reply and ACKed |
| 8 | low | wire | Per-device idp ranges (1, 10001, 20001…); the "synchronised idp" model is not backed by the app |
| 9 | low | wire | Envelope field order / JSON spaces / `pin: null` differ from Gson |
| 10 | low | parsing | Missing/unknown `mod` → `HEAT_RECOVERY` |
| 11 | low | parsing | `on_off`: lib OFF if `!= 1`, app OFF only if `== 2` |
| 12 | low | parsing | Missing `s_umd` → made-up 50%; `umd` alias ignored |
| 13 | low | parsing | LED: only `led_on_off_breve` read; no fallback to `led`/`led_on_off` |
| 14 | - | - | removed: out of scope |
| 15 | low | semantics | Docs now use `speed_requested`; `fan_running` still based on legacy `speed` |
| 16 | low | validation | Setters without range checks (`mod`, `spd_row`, `s_umd`, `vr`) |
| 17 | low | semantics | `par_amb`/`par_ext`, `m_crono`, `vr`, `timezone` left raw |
| 18 | low | robustness | Listener never recreated after a socket error |
| 19 | low | robustness | `register_device` with an existing `device_id` ignores the new ip/port |
| 20 | low | discovery | LAN discovery with `idp=0`, no ACK, needs the PIN |
| 21 | low | lib-doc | idp docs: "device keeps a counter" stated as fact; "releases IDP range" is false |
| 22 | low | lib-doc | `../../command-flow.md`: reply after a command = full state (not verified) |
| 23 | low | lib-doc | LAN use / fixed ports presented as standard; the app only uses `192.168.4.1` |
| 24 | low | gap | Missing commands: `check_pin`, `upd_datetime`, `get/set_fasce`, `m_crono`, `pico_info` |
| 25 | low | gap | No provisioning, OTA, or handling of `null`/`"-1"` PIN |
| 26 | low | dead code | `utils/pico_protocol.py` duplicate, unused |
| 27 | low | doc-app | `02-pico-runtime.md` inconsistent about `spd_row` |

---

## 1. Retry: up to 15 sends, even after an ACK — medium

- **App** (`01-transport.md` §4-5, `UDPSocket.java:284-311`): 3 attempts, a new idp each; retries only if no ACK arrives within 5 s. Once ACKed, it waits for the reply (5 s from the send) and does not retry.
- **Lib** (`pico_client.py:494-536`, `:545`, `:553-558`): `retry_attempts=3` × `max_idp_sync=5` = up to 15 sends, a new idp each. After an ACK it waits only a fixed 2.0 s, then sends the same command again. With `retry=False` it still sends up to 5 packets.
- **Impact:** a non-idempotent command (`upd_pico`, `man_reset`) that was already applied can be sent up to 14 more times. Worst case ~79 s against ~16 s for the app.
- **Fix:** after an ACK, wait for the reply up to `timeout` without resending. At most 3 sends. `retry=False` = 1 send. Idp sweep opt-in only.

## 2. `res` never checked — medium (partial)

- **App** (`PicoActivity.checkRespSetMode`, `:1593-1603`; used in `sendCmdUpdPico` `:1555-1564` and `sendCmdDataOraTImezone` `:1525-1539`): a command is OK only with `res==1`, and only then is the optimistic state applied (`pico = tmpPico.getCopy()`). With `res != 1` or `null` the app silently drops the change, with no toast. `check_pin` also requires `res==1`; otherwise it shows the PIN dialog.
- **Lib** (`pico_client.py:574-580`): any reply with `res != 99` and the right idp is returned. `CommandResponseModel` has no `res`. `get_status` builds `PicoDeviceModel` without checking it (`pico_device_model.py:144` default `res=0`).
- **Impact:** a wrong PIN or a device error looks like success; an error reply parsed as state produces made-up defaults.
- **Fix:** expose `res`; raise `PicoDeviceError` if `res != 1`; `get_status` requires `res==1`.

## 3. `err` with all-zero arrays → permanent error — medium

- **App** (`02-pico-runtime.md` §3.1-3.2): `err` is `int[][]`, one array per unit. The error icon shows only if an element is `!= 0`. Code = `category*1000 + 8-bit mask`. `10004` is a synthetic watchdog.
- **Lib** (`models/parameter_arrays_model.py:17-26`): `has_errors = any(len(l) > 0)`; `active_errors` includes the zeros. `is_healthy` depends on it (`pico_device_model.py:158-164`).
- **Fix:** filter `e != 0`; optionally decode category and mask.
- **To check on the device:** whether it really sends all-zero arrays.

## 4. Reply port rule described backwards — medium

- **Fact:** the device always replies to 40069. The app sends from an ephemeral port and listens on 40069.
- **App** (`UDPSocket.java:41,91`: listener on 40069; `:262,340`: sends from an ephemeral `new DatagramSocket()`).
- **Lib docs:** `docs/architecture.md` used to say the opposite ("only respond to packets originating from port 40069"); fixed. `README.md:247` ("reply only to that port") and `pico_auto_discovery.py:6-7,47-48` are correct, at most ambiguous. `local_port` is a configurable parameter with default 40069 (`README.md:183,269`, `docs/auto-discovery.md:89`), with no warning that it must stay 40069.
- **Impact:** with `local_port != 40069` every command times out. The stated reason for the shared socket was wrong, although the design is still valid: a single listener must own 40069.
- **Fix:** document that `local_port` "must stay 40069", or remove it.

## 5. Device ACK only with `frm=="mst"`; 2 s wait after the ACK — low

- **App:** ACK = `res==99` with the expected idp, no check on `frm`. The wait for the reply follows the command timeout (10-15 s for `pico_info`/`config`).
- **Lib** (`pico_client.py:568`, `:545`): requires `frm=="mst"`; otherwise the ACK is silently dropped. `ack_timeout=2.0` is fixed. `docs/command-flow.md:23-70` states `frm=mst` as a protocol rule.
- **Fix:** accept the ACK whatever `frm` is; wait after the ACK = command timeout.

## 6. Client ACK only for the expected idp — low

- **App** (`UDPSocket.parsemsg`, `01-transport.md` §4): sends `{idp, frm:"app", res:99}` for every message with `res != 99`, including late replies, unknown idps and pushes. It also requires `cmd`; without it, the exception is only logged.
- **Lib:** `pico_client.py:565-566` drops other idps without an ACK. `shared_transport_manager.py:70-75` routes/drops them without an ACK. Discovery: no ACK.
- **Possible impact:** if the firmware retransmits until it gets an ACK → spurious traffic. Possibly linked to the "stuck idp" symptoms (not verified).
- **Fix:** central ACK in `SharedPicoProtocol.datagram_received` for every message with `idp`, `res != 99` and `cmd`.

## 7. Message without `res` treated as the reply — low

- **Lib** (`pico_client.py:574`): `response.get("res") != 99` is true even when `res` is missing → returned and ACKed.
- **App:** `getLong("res")` throws → ignored, no ACK.
- **Fix:** require `"res" in response`.

## 8. Per-device idp ranges — low (partial)

- **App:** global counter, starts at 1, `resetIDP()` on every reconnection, a new idp per retry, no synchronisation.
- **Lib** (`shared_transport_manager.py:136-137,221-222`, `pico_client.py:121,451`): 10000-wide range per device. The first device starts at 1, the others at 10001, 20001… Wraps to `range_start`.
- **Note:** this is a problem only if the firmware really tracks the idp (see #21). To be checked on hardware; if it does, use per-device idps from 1 and demultiplex by source IP.

## 9. Envelope format — low

- **App (Gson):** `{"cmd":…,"frm":"app","idp":N,"pin":"…"}`, compact, a null `pin` is omitted.
- **Lib** (`pico_client.py:160-164,516,467`): order `cmd, frm, pin, idp`, separators with spaces, `"pin": null` sent.
- **Impact:** none with a real JSON parser. Align (`separators=(',',':')`, idp before pin, omit None) only if firmware with strict parsers shows up.

## 10-13. State parsing — low

| Field | App (`02-pico-runtime.md` §3.1) | Lib | Fix |
|---|---|---|---|
| `mod` | updated only if present; outside 1..12 = no mode | `pico_device_model.py:75-78` default 1 → `HEAT_RECOVERY`, enables the speed/night guards | raw value + `UNKNOWN`/`None` |
| `on_off` | OFF only if `==2`; missing key = previous value | `:81-84` default 0 → OFF | `is_off = on_off == 2` |
| `s_umd` | from `umd` then `s_umd` (`s_umd` wins), only if present | `:87-90` missing → warning + 50% | `Optional`, fall back to `umd` |
| LED | `led_on_off` → `led` → `led_on_off_breve`, last one wins | `operating_parameters_model.py:45-47` only `led_on_off_breve` (`!= 2`): matches the app when `led_on_off_breve` is present | fall back to `led`/`led_on_off` when it is missing |

## 14. Maintenance `man[]` — removed: out of scope

- Removed: out of scope. The app treats `man[0]` as the PICO; the other indexes belong to the cascade. The lib uses only index 0 (`pico_client.py:310-312`): aligned.

## 15. `speed` presented as % — low (partial)

- **App:** percentage = `spd_rich` (requested) / `spd_row` (0..100). `speed` is a legacy value (1..3, inferred). The command sends `speed:0` + `spd_row`.
- **Lib:** the model exposes `speed_requested` (`spd_rich`) and `speed_row` (`spd_row`); `README.md` and `examples/*` now print `speed_requested` as the percentage. Still open: `fan_running = speed > 0` (`operating_parameters_model.py:36-38`) still uses the legacy value.
- **Fix:** revisit `fan_running` (e.g. `speed_row > 0`).

## 16. No validation in setters — low (partial)

`change_operating_mode` (`pico_client.py:188-196`), `change_fan_speed` (`:203-220`) and `set_target_humidity` (`:278-283`) send any int. The app limits `mod` to 1..12 (6..11 hidden with `vr==1`), `spd_row` to 0..100, `s_umd` to 1..3. Also, `change_fan_speed` does not block night mode (the app disables the slider) and skips the mode guard when `percentage==100`.

## 17. Raw fields without semantics — low

- **Sensors:** `par_amb`/`par_ext` passed through as lists. App: `[1]` humidity /100, `[2]` quality index (thresholds 200/400), `[3]` CO2 /100, valid only in the raw range 30000..300000, `-999` = not available.
- **Temperatures:** `AMB_tmpr`/`EXT_tmpr` not parsed.
- **Other fields:** `m_crono` (1 = on, **2 = off**: a consumer treating it as a boolean gets it wrong), `vr` (1 hides modes 6..11, 3 enables time slots and date), `timezone` (string; `"null"` treated as null, missing key = `""`, `Pico.java:67-71`), `week` (0 = Monday) are not documented.

## 18. Listener never recreated — low

`shared_transport_manager.py:98-104` only logs `error_received`/`connection_lost`; `_initialized` stays True (`:163-166`). 40069 is never rebound until `shutdown()` is called. The app instead recreates the listener on every retry and reconnection.

## 19. `register_device` with an existing id — low (partial)

`shared_transport_manager.py:210-218` only updates the queue and callbacks, ignoring a new ip/port. It affects only callers that reuse an explicit `device_id` without `disconnect()`, or two live clients with the same id. The default case (`ip:port`) is unaffected.

## 20. Discovery — low

`pico_auto_discovery.py`: subnet scan with `stato_sync`, `idp=0` (the app starts at 1), PIN required, no ACK to replies. The app has no discovery and always uses `192.168.4.1` (`UDPSocket.java:61-62`). Devices with a different PIN or not yet configured are not found. PIN-less alternative: `pico_info` (returns `ser`, `fw_ver`, `config_mod`).

## 21-23. Library documentation — low

- **#21** `docs/retry-logic.md:3-30` and `README.md:502` state as fact that "the device keeps an idp counter that must match". The app shows the opposite: reset to 1, a new idp per retry, no synchronisation. It should be marked as an observed, unverified workaround. `reset_idp` goes back to `range_start`, not to 1 (`retry-logic.md:97-98`). `README.md:312` "releases IDP range" is false: `_next_idp_range` only grows (stated correctly in `architecture.md:91-92`).
- **#22** `docs/command-flow.md:10-28`: reply after a command = full updated state. In the app this is an open question; the app only looks at `res==1`.
- **#23** `README.md:77-145,192-242` and `docs/architecture.md:33` present the LAN IP as the normal case. The app uses `192.168.4.1` (device AP) and the cloud in STA mode. LAN use should be documented as an empirical extension. Missing from the README: default AP `192.168.4.1`, SSID `Pico_config`/`12345678`, `Pico_<SER>`/`TS_<SER>`.

## 24-25. Missing features — low (gap, no wrong value sent)

- **Runtime commands:**
  - `check_pin` (`res==1` = valid PIN)
  - `upd_datetime` (`date yyyy-MM-dd`, `time HH:mm:00`, `week` 0 = Mon; `PicoActivity.java:1879-1882`). App bug: `PICOCronoSummaryActivity.java:113-117` sends `hh:mm:ss` (12-hour format); neither path sets the pin.
  - `get_fasce`/`set_fasce` (D0..D6, 4 slots `[start_min,end_min,mod,speed,hum]`, empty slot `[-1,-1,0,0,0]`)
  - `upd_pico` with `m_crono` 1/2
- **Info:** `pico_info` without pin; `ser` never parsed (`device_info_model.py`).
- **Provisioning:** `check_led`, `scan_wifi`, `config`, `pico_ap` (`pin:"-1"`, `ap_m`).
- **OTA:** `ota_start{sha256,size}` → TCP `192.168.4.1:40060` in 1300 B chunks with a 20 ms pause → `ota_end` → `pico_ap{ap_m:5}`.
- **PIN:** always serialised; no support for `None` (omitted) and no validation (the app requires 4 characters that parse as an int).
- **Versions:** no numeric comparison helper (the app uses a 1.0.3 threshold).

## 26. Dead code — low

`../../../open_pico_local_api/utils/pico_protocol.py`: `PicoProtocol` (single queue, no idp routing) is used only by `tests/local/test_pico_protocol.py`. Remove or deprecate.

## 27. Inconsistencies in the app docs — low

- `02-pico-runtime.md`: `:267-268,291` map `spd_row` to `Pico.speed_raw`, but `:306` calls it "debug only, not stored in Pico". The code reads it into `Pico` (`Pico.java:418-419`) and also uses it outside the debug panel (`PicoActivity.java:1225,1467`). Remove `spd_row` from the list at `:306`.

---

## Discarded

- "IDP bruteforce in `../../../scripts`": refuted. The tool is `examples/local/idp_diagnostic.py`, already linked in `docs/retry-logic.md:122`; its docstring already warns about the duration.

## Suggested priorities

1. **#1, #2, #5, #7:** the send/wait loop in `pico_client.py`; one place, high value.
2. **#3, #10-#14:** robust state parsing (direct impact on Home Assistant).
3. **#4, #21, #23:** documentation fixes (port, idp, LAN).
4. **#6:** central ACK, then check on hardware whether the "stuck idp" symptom goes away (if so, simplify #8 and the idp sweep).
5. **#24:** `check_pin` and `upd_datetime` (cheap), then time slots.

## Questions for hardware tests

- Does the firmware track the idp? (decides #8, #21 and the sweep logic)
- Does the firmware retransmit without a client ACK? (#6)
- Does `err` arrive as all-zero arrays when there are no errors? (#3)
- Is the reply to `upd_pico` `{res:1}` or the full state? (#22)
