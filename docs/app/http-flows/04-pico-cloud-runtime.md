# 04 - PICO cloud runtime

Same screen (`PicoActivity`) as the local flow. Branch point is `pico.getOffline()`; online = REST, offline = UDP ([../local-flows/02-pico-runtime.md](../local-flows/02-pico-runtime.md)). State parsing and command bodies are shared.

## State polling
`PicoActivity.startStatoTimer()` (`Activity/PICO/PicoActivity.java:803`): `Timer`, period **5000 ms**, does nothing in demo mode.
Per tick, online branch (`:872`):
```
GET /api/v1/GetPICOState?picoSerial=<SER>&PIN=<PIN>      (type 26)
```
- 4th ctor arg = `first`: progress spinner only on the first request.
- Reply HTTP 200 + `ResCode 0`: `ResDescr` = backend state record (not the raw device packet, see below) -> `receiveStato()` -> `pico.receivedSync(str)` -> UI.
- Staleness: if no state for >15 s, one toast per 15 s (`zone_errors[5]`) and error code `10004` is injected into the Pico (`:826-856`).
- `picoCMD` flag: after a successful command the next state reply is **dropped once** (`receiveStato:788`) so the UI keeps the optimistic value instead of an older server snapshot.
- Timer is cancelled/paused when the PIN dialog is open (`pausastato`).

### `ResDescr` shape (observed on a live device, fw 1.0.12)
`ResDescr` is a JSON string with two copies of the state:
- **Flat fields, `frm:"db"`**: the backend's own record. Only control fields: `on_off`, `mod`, `speed`, `spd_row`, `spd_rich`, `night_mod`, `s_umd`, `name`, `led_on_off`, `led_on_off_breve`, `led_color`, `id_slave`, `has_slave`, `err`, `man`, `par_ext`, `par_amb`, `m_crono`, `tw_active`, `ip`, `fw_ver`, `vr`, `w_rssi`, `res`, plus `reset`/`timezone` (seen `null`).
- **`lastpk`**: JSON string (third level of encoding) of the last `stato_sync` the device sent (`frm:"mst"`, own `idp`). Same keys and encoding as the local UDP reply. Sensors (`v_tmpr`, `v_umd`, `v_ECo2`, ...), `par_rt`/`par_mm`, `fw_note`, `modello`, `memfree`, `up_time`, ... exist **only** here.

```
{"ResCode":0,"ResDescr":"{\"cmd\":\"stato_sync\",\"frm\":\"db\",\"on_off\":2,\"mod\":1,...,
  \"lastpk\":\"{\\\"idp\\\":13398,\\\"frm\\\":\\\"mst\\\",\\\"v_tmpr\\\":23.56,...}\", ...}"}
```

The two copies do **not** always agree, because the db copy re-encodes some fields. Measured by toggling the LED via `SendPicoCmd` (`[led_on_off, led_on_off_breve, led_color]`, both copies updated within one 6 s poll):

| moment | flat (`db`) | `lastpk` (device) |
|---|---|---|
| initial | `[1, 1, 0]` | `[1, 0, 1]` |
| LED off | `[0, 0, 0]` | `[0, 2, 1]` |
| LED on | `[1, 1, 0]` | `[1, 1, 1]` |

- `led_on_off_breve`: device uses the local encoding (`2` = off, `1`/`0` = on); db stores a boolean (`0` = off). Reading the db value with the local parser reports an off LED as on.
- `led_color`: constant `0` in db vs `1` on the device: different encoding, not staleness.
- `name`: db holds the name given in the app/account (`"VMC - CG"`), `lastpk` the name stored on the device (`"Camera grande"`).
- Fan speed (`speed`, `spd_rich`, `spd_row`) matched in both copies before and after `change_fan_speed`.

**Library rule** (`PicoCloudClient.get_status`): decode `lastpk` and let it win; flat fields only fill keys `lastpk` lacks (and `null` flat values are dropped). The cloud status is then parsed exactly like a local reply. The app's account name stays in `raw_data["name"]`; the raw `lastpk` string in `raw_data["lastpk"]`. The app itself feeds the flat fields to `receivedSync` and reads `lastpk` only in its unreachable debug panel, so it shows the db encoding.

## Commands
Entry `updatePico(n)` builds a `CmdPICO` (same bodies as local: `upd_pico`, `upd_led`, `upd_pman_reset`, `upd_pico_mcrono`, ...). Online path `sendCmdUpdPico` (`:1555`):
1. `cmd.frm = "mqtt"` (local uses `"app"`), `cmd.idp = getIDP()` (static counter, `:1516`: if >500 reset to 1, then +1; set to 0 in `onCreate`, `:157`).
2. Wrap in `PICOServer`:
```json
{"Serial":"<SER>","Pin":"<PIN>","Name":"<name>","Cmd":"{\"cmd\":\"upd_pico\",\"frm\":\"mqtt\",\"idp\":7,\"pin\":\"1234\",\"on_off\":1,\"mod\":6,...}"}
```
   `Cmd` is the device JSON serialized to a **string** inside the JSON.
3. `POST /api/v1/SendPicoCmd?picoSerial=<SER>&PIN=<PIN>` (type 27 -> `setStatoPico`).
4. Reply 200 + `ResCode 0` -> `pico = tmpPico.getCopy()`, `picoCMD=true`, redraw. Else toast `msg_commandKo` (ResCode 2 -> PIN dialog).
No device ACK (`res:99`) is awaited; delivery to the PICO is asynchronous on the backend (inferred, MQTT).
`idp` is only a client counter here; the local `resetIDP()` on reconnect has no online equivalent.

## Date, time, timezone
`impostaDataOraTimeZone` (`:1884`): `CmdPICO.UPD_DateTime{date:"yyyy-MM-dd", time:"HH:mm:00", week}` wrapped in `PICOServerTimezone{Serial,Pin,Timezone,Cmd}` and sent with `POST /api/v1/UpdPicoTimeAndTimezone` (same handler type 27).
`Timezone` = `idTimeZone` chosen from `Constants.TIMEZONES` (login response `ListTimezone`). Online devices need a timezone before the schedule (fasce) screen opens (`:1971`); offline ones do not.

## Schedules (fasce)
| Step | Call |
|------|------|
| get | `POST /api/v1/SendPicoCmd` (no query) body `PICOServerTimezone{Serial,Pin,Cmd=get_fasce JSON,frm:"mqtt"}` (type 33) |
| set | same URL, body with `Cmd` = `PICO_Fasce` (days d0..d6), type 34 |
Reply `ResCode 0` and **`ResDescr` = the device's reply string** (so for fasce the cloud call is synchronous request/response, unlike plain commands). Parsed by `parseRespGetFasce` / `parseRespSetFasce` exactly as the UDP reply.
After a get, offline devices also push `UPD_DateTime`; online ones do not.

## PIN handling
`ResCode 2` on any device call -> `checkonlineError`: stop the poll, show the PIN dialog once (`asckedPin`). New PIN saved to prefs, `first=true`, timer restarts. PIN is sent in clear in query string and body.

## What does not exist online
- No `ota_start`/firmware push from `PicoActivity` (type 28 has no caller); firmware update opens the bootloader screen over AP ([05-firmware-push.md](05-firmware-push.md)).
- No server push of state: push notifications only carry alerts.
- No retry/backoff: a failed poll is just skipped, next tick after 5 s.

## Sequence (command)
```
User tap -> updatePico -> tmpPico changed
 -> POST SendPicoCmd {Serial,Pin,Cmd:"{..frm:mqtt..}"}  [Authorization Basic, Token]
 <- 200 {"ResCode":0}   -> pico=tmpPico, picoCMD=true
 -> (5 s) GET GetPICOState ... <- {"ResCode":0,"ResDescr":"<db record + lastpk>"}  (first one ignored)
```
