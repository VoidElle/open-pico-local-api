# 01 - HTTP transport and auth

## Layers
`Activity` -> `new ThreadWebService(activity, method, type, url, jsonBody, params[, showProgress]).start()` (`Threads/ThreadWebService.java:65`) -> `WebClientDevWrapper.getNewHttpClient(url, body, token, user, method, type)` (`Threads/WebClientDevWrapper.java:21`) -> `HttpURLConnection`.
`ThreadWebService.run()` (`:92`) switches on `type`, calls one handler, which parses the response and calls back into the activity on the UI thread.
No retry layer, no OkHttp/Retrofit. Errors: `getNewHttpClient` returns `null` on any exception -> toast `resCodeError`.

## Wire format
| Item | Value |
|------|-------|
| Base URL | `https://proair.azurewebsites.net` (`res/values/strings.xml:810-812`) |
| `method` arg | 0 GET, 1 POST, 2 DELETE (with body), 3 PUT (`WebClientDevWrapper.java:23-37`) |
| Timeouts | connect 15 s, read 15 s |
| `Authorization` | `Basic base64("<Constants.user>:PwdProAir")`; before login user is `UsrProAir` |
| `Token` | login/sign-up/forgot/GDPR/check-email: fixed `Constants.FIX_TOKEN`; afterwards rolling token (below) |
| `UserObj-Agent` | `benincapp`, GET only |
| Body | `application/json` (POST/PUT/DELETE), UTF-8 |
| Response | body read from input stream, falls back to error stream. Binary GET (`type 5`) returns raw bytes |

## Rolling token (`Functions.calcNewToken`, `Utils/Functions.java:544`)
1. Login response field `Token` -> `Constants.token` (kept in memory).
2. Key = SHA-256(`androidId[0:8]` + `SALT`), `SALT="ns91wr48"`; cipher `AES/CBC/PKCS7`, IV = 16 zero bytes (`Utils/AESCrypt.java`).
3. Server token decrypts to `"<text>_<counter>"`. Before each call the app decrypts, counter+1, re-encrypts, strips `\r\n`, and sends it in `Token`. Also stores it in prefs `cont_token`, `TOKENVALUE`.
4. If decrypt fails, `calcNewToken` returns `null` and the request goes out with `Token: null` (inferred: server answers 401).
`ThreadDowloadFirmWare` retries up to 5 times while HTTP 401 (each retry bumps the counter). No other call retries.

## Dispatch table (`ThreadWebService.run`)
| type | Handler | Endpoint (method) | Used by |
|------|---------|-------------------|---------|
| 0 | `signUp` | `/apiTS/v2/RegisterUser` (POST) | SignUp |
| 1 | `checkEmail` | `/apiTS/v1/CheckEmail?email=` (GET) | SignUp |
| 2 | `logIn` | `/apiTS/v2/Login`, `/apiTS/v2/ChangePwd` (POST) | Login, ChangePwd |
| 3 | `recPwd` | `/apiTS/v1/ForgotPwd` (POST) | Login |
| 8 | `connUsrUC` | `/api/v1/AddUserToDevice` (POST) | legacy CU |
| 9 | `getHome` | `/api/v1/GetHome` (GET) | legacy `HomeActivity` |
| 10, 25 | `deleteUsrfromUC` | `/api/v1/DeleteDevice`, `DeleteUserFromCU`, `DeletePlant` (DELETE) | PICO delete = 10 |
| 20 | `delUser` | `/api/v1/DeleteUser` (DELETE) | delete account |
| 22 | `plantInsUPD` | `/api/v1/InsertPlant`, `UpdatePlant` (POST) | AddUpdPlant |
| 23 | `getHomeTS` | `/api/v1/GetPlants` (GET) | TSHome / TSDeviceList |
| 24 | `connUsrPico` | `/api/v1/AddUserToDevice` (POST) | add PICO by serial+PIN |
| 26 | `getStatoPico` | `/api/v1/GetPICOState?picoSerial=&PIN=` (GET) | PICO poll |
| 27 | `setStatoPico` | `/api/v1/SendPicoCmd?picoSerial=&PIN=`, `/api/v1/UpdPicoTimeAndTimezone` (POST) | PICO commands |
| 28 | `picoCMD` | `/api/v1/SendPicoCmd` | no caller found (dead path, goes to bootloader instructions on ok) |
| 29 | `checkPicoConfig` | `/api/v1/AddUserToDevice` (POST) | PICO online pairing poll |
| 33 / 34 | `getPicoFasce` / `getPicoSetFasce` | `/api/v1/SendPicoCmd` (POST) | PICO schedules |
| 32 | `updGDPR` | `/apiTS/v2/AcceptTermsOfUse` (POST) | GDPR screen |
| 11-19, 21 | CU/VMC handlers | `GetCUState`, `UpdateCUData`, `GetTW`, `UpdateTW`, ... | out of scope |
| 4, 5 | firmware | `/api/v4/FWs`, `/api/v1/FW?filename=` | `ThreadDowloadFirmWare` |

## Response convention
`{"ResCode": n, "ResDescr": "..."}`; HTTP 200 for OK, 400 for logical errors with same body.
| ResCode | Meaning |
|---------|---------|
| 0 | OK |
| 2 | wrong PIN (device endpoints) -> `pinerror()` toast + PIN dialog. On `AcceptTermsOfUse`/login: user to confirm |
| 9 | email already exists (`CheckEmail`), restore failed (`SendRestoreCmd`) |
Login-specific values: see [02-account-login.md](02-account-login.md).
Handlers check `ResCode` only when `has("ResCode")`; missing -> generic `msg_commandKo` toast.
