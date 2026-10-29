# PICO online (cloud) flows (decompiled Tecnosystemi app)

Map of the cloud flows derived from `Export-Pico/sources/it/tecnosystemi/TS` (JADX).
`file:line` references are relative to that folder. "(inferred)" = deduced, not read.
Counterpart of [../app-flows](../app-flows/README.md) (local UDP flow).
Out of scope: VMC, SeiX, legacy ControlUnit, master/slave cascade (`PicoCascataActivity`).

| File | Content |
|------|---------|
| [01-http-transport-auth.md](01-http-transport-auth.md) | Base URL, REST endpoints, headers (Basic + rolling `Token`), `ThreadWebService` type codes, `ResCode` values |
| [02-account-login.md](02-account-login.md) | Splash, login, sign-up, forgot/change password, GDPR, session expiry, remember-me, delete account, demo mode |
| [03-plants-devices.md](03-plants-devices.md) | Plants/devices model, `GetPlants`, `AddUserToDevice`, online pairing poll, `DeleteDevice`/`DeletePlant` |
| [04-pico-cloud-runtime.md](04-pico-cloud-runtime.md) | `GetPICOState` polling (5 s), `SendPicoCmd` envelope (`frm:"mqtt"`), datetime/timezone, fasce, PIN errors |
| [05-firmware-push.md](05-firmware-push.md) | Firmware catalog `FWs` + `FW` download, FCM push notifications |
| [06-quirks-security.md](06-quirks-security.md) | Bugs, dead code, and security weaknesses seen in the app |

Key points:
- One backend: `https://proair.azurewebsites.net` (same host for `uriWebService`, `_PICO`, `_POLARIS`). Paths `/apiTS/*` = account, `/api/*` = devices.
- Device cloud traffic is app -> REST -> backend -> (MQTT, inferred) -> PICO. The app never talks to the PICO directly online; commands carry `frm:"mqtt"`.
- Local vs cloud is chosen per device by `Pico.offline` (see `PicoActivity.java:846,1527,1557`), same flag as the local flow.
- Auth = fixed HTTP Basic (`<email>:PwdProAir`) + custom `Token` header holding a rolling AES counter token. Session lasts 1 h from login.
- All responses are JSON `{ResCode, ResDescr}`. `ResCode 0` = OK, `2` = wrong PIN (device calls). HTTP 400 carries the same body.
- Command POSTs return only an ack. Real state comes from the next 5 s poll.
- Graph note: the codebase-memory index holds only folders for this decompiled Java (no symbols), so references were traced by reading/grepping files.
