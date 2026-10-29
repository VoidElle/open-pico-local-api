# 03 - Plants and devices

## Model
- `Plant` ("impianto", `Model/Plant.java`): `{LVPL_Id, LVPL_Name (upper-cased), LVPL_Icon, LVPL_USAN_Id, ListDevices[]}`. A user owns plants; devices live inside a plant.
- `Device`: `LVDV_Id`, `LVDV_Type` (`DEVICE_TYPE_PICO = 1`), `Serial`, `Name`, `NUM_ERROR`.
- Local cache: SharedPreferences `PREFS_TS`. `PREF_DEVS_TS` = map plantId -> devices. Each PICO also stored as `Pico` (serial, PIN, name, `offline` flag) via `Pico.savePicoInPref`.
- The PIN is part of the device record on the phone and is sent in every device call (query string or body).

## List plants
`GET /api/v1/GetPlants` (type 23, `TSHomeActivity.java:177`, `TSDeviceListActivity.java:394`).
- `ResCode 0` -> `ResDescr` is a JSON **string** containing `ArrayList<Plant>` (double-encoded, Gson parses it separately).
- `Functions.SyncInpianti` merges server plants into the cache: adds missing devices and replaces cached ones with the server entry; for an offline-flagged Pico it compares `LastAddTimezone` before replacing; stale local devices are dropped (inferred from the collected-serial lists, `Utils/Functions.java:190`). `Constants.listaImpianti` then drives the UI.
- Same list arrives at login (`ListPlants`), so `GetPlants` is a refresh.

## Plant CRUD
| Action | Call |
|--------|------|
| Create | `POST /api/v1/InsertPlant` body `Plant` (type 22) |
| Update | `POST /api/v1/UpdatePlant` body `Plant` (type 22) |
| Delete | `DELETE /api/v1/DeletePlant` body `{"plantID": <id>, "token": <FCM>, "platform": "fcm2"}` (type 10 from TSHome, 25 from TSDeviceList = also closes screen) |
`ResCode 0` finishes the screen; `2` -> PIN error; other -> `msg_commandKo`.

## Add an existing PICO (already online)
`SetNameAndPinPICOActivity` with `mode == 2` (`Activity/PICO/Config/SetNameAndPinPICOActivity.java:234`):
`POST /api/v1/AddUserToDevice` (type 24)
```json
{"Serial":"<UPPER serial>","PIN":"1234","isPico":true,"PlantId":<id>,
 "token":"<FCM>","platform":"fcm2"}
```
Reply `ResCode 0` -> `savserverPico()` saves the Pico with `offline=false`, adds it to the plant cache, opens `TSDeviceListActivity`. Non-zero -> toast `au_errorAddUser` (400 body is ignored apart from the toast).
Binding user<->device happens server side; PIN is verified by the backend (inferred from `ResCode 2`).

## Pair a new PICO online
Local part (join `Pico_config` AP, `config` online, ...) is in [../app-flows/03-provisioning.md](../local-flows/03-provisioning.md). The cloud part (`ConfigPICOActivity`):
1. After the device accepts `config` online, app `unbidNetwork()` (drops AP binding) and sets `times = CONFIG_TIMES = 40` (`:61`, `:298`).
2. `checkPicoOnline()` waits 5 s, then `POST /api/v1/AddUserToDevice` (type 29) with `Device_OP` + `PhoneDate` (`yyyy-MM-dd'T'HH:mm:ss.SSS'Z'`, local time, literal `Z`).
3. `ResCode 0` -> `addpico(serial, offline=false)`: cache Pico, add to plant, "device added". Anything else (network error, `ResCode != 0`) -> `times--` and repeat.
4. `times == 0` -> `error()`. Worst case about 40 x (5 s + RTT), roughly 3.5 min.
The poll succeeds only once the PICO has reached the cloud and registered itself (inferred).

## Delete a PICO
`PicoActivity.cancellaDevice()` (`:1836`): remove from local prefs first, then, if not offline, `DELETE /api/v1/DeleteDevice` body
```json
{"deviceID": <LVDV_Id>, "token": "<FCM>", "platform": "fcm2"}
```
(type 10). The local copy is deleted before the server answers, so a failed call leaves the device deleted on the phone and still bound on the server until the next `GetPlants` sync re-adds it (inferred).
Offline devices skip the call (local delete only).

## Delete user's access (other device types)
`DeleteUserFromCU` / `DeleteUser` are legacy CU and account paths, see [02-account-login.md](02-account-login.md).
