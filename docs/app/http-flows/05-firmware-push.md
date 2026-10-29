# 05 - Firmware catalog and push

## Firmware catalog
`ThreadDowloadFirmWare` (`Threads/ThreadDowloadFirmWare.java`), started by the PICO menu "check firmware" (`PicoActivity.java:1918`, offline devices hide it) and by `VerFWActivity`.
1. `GET /api/v4/FWs` (`uri_infoFrameWork`), type 4, Basic + rolling `Token`, up to 5 attempts while HTTP 401.
2. Reply = JSON array of firmware entries (fields seen: `Path`, size). Written to prefs `PREF_INFOFWS`; its non-empty state makes the "Update firmware" menu item appear.
3. Local folder `FW_DIRECTORY_NAME` is synced: files not in the catalog are deleted, missing ones downloaded.
4. Download: `GET /api/v1/FW?filename=<Path>` (type 5, binary), up to 5 attempts on 401. File saved only if the byte length equals the catalog size; otherwise `ok=false`, toast `ha_syncFWError`.

## Flashing
Not online. "Update firmware" (`setApConfig`, `PicoActivity.java:1743`) joins the PICO Wi-Fi (`Pico_<SER>`, password `TS_<SER>`) and opens `PicoBootloaderActivity`, which pushes the downloaded file to the device over TCP 40060 (see [../app-flows/04-firmware-ota.md](../local-flows/04-firmware-ota.md)). The cloud is only the file source.
Version hints from login: `LastFWVr`, `LastVrAndroid`, `LastVrAndroidText` (compared in the UI; no forced update found).

## Push notifications (FCM)
- Token: `BaseActivity.FirebaseToken` (`:219`).
- Registered server side by sending `TokenPush` + `Platform:"fcm2"` at login and `token`/`platform` in `AddUserToDevice`, `DeleteDevice`, `DeletePlant`. Backend uses it to deliver alerts (inferred).
- Receiver: `MyFirebaseService.onMessageReceived` reads `data.message`; the first 6 chars are a numeric code: `1` -> "communication error: <rest>" (control unit), `2` -> PICO communication error. Other payloads are shown as-is. Notification channel `tecnosystemi_channel_ID`.
- Opt-in dialog stored in `PREF_REGID_NAME` / `PREF_REGID_SETTING_NAME` (0 = user declined in-app prompt, 1 = accepted).
- Pushes do not update screen state; the 5 s poll does.
