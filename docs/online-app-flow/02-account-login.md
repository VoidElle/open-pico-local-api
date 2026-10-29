# 02 - Account and login

## Entry
`SplashActivity` (fixed delay) -> `LoginActivity` (`Activity/SplashActivity.java:24`). There is no auto-login: stored credentials only prefill the form.

## Login
`LoginActivity.login()` (`Activity/LoginActivity.java:285`)
1. Validate email format + non-empty password (`Validation`).
2. `android_id = Settings.Secure.ANDROID_ID`.
3. Build `LoginModel` JSON:
```json
{"Username":"<email>","Password":"<AES(pwd)>","DeviceId":"<android_id>",
 "Timezone":"Europe@Rome","TokenPush":"<FCM token>","Platform":"fcm2"}
```
   - `Password` = AES-CBC(zero IV) base64 with key SHA-256(`android_id[0:8]` + `ns91wr48`). Not a hash; reversible by anyone with the id.
   - `Timezone` = Java zone id with `/` replaced by `@`.
4. `POST /apiTS/v2/Login` with `Token: FIX_TOKEN`, Basic `UsrProAir:PwdProAir` (`ThreadWebService.logIn`, `:684`).
5. If "remember me": store `PREF_PWD = AES(android_id, pwd)` (second AES scheme, `AESAlgorithm`), `PREF_USERNAME`. Otherwise clear them.

### Login response (`ResCode` in body, HTTP 200)
| ResCode | Action |
|---------|--------|
| 0 | success (below) |
| 1 | toast wrong user/password |
| 2 | toast user must confirm email |
| 3 | toast user blocked |
| 4 | toast user not found |
| 5 | nothing |
| 6 | open `ChangePwdActivity` (temporary password) with old user/pwd |
| 7 | toast: request new temporary password |
| 10 | privacy/ToS not accepted -> `GDPRActivity` (`needprivacy`), then `AcceptTermsOfUse` |
| other / no body | generic error toast |

### On success (`ResCode 0`)
- `savepref`: `Constants.token = Token`; `PREF_TOKEN_DATE = now`; `PREF_USER_ID = ID`; if the username differs from the last user, wipe cached device prefs (`SavePreferences.initialize`).
- `Constants.user = email` (used as Basic user from now on).
- Read optional fields: `ResetPin`, `LastFWVr`, `LastVrAndroid`, `LastVrAndroidText`, `MarketingAccepted`, `ListTimezone` (-> `Constants.TIMEZONES`, used for PICO timezone), `ListRecipe` (modbus, out of scope), `ListPlants` (-> `SyncInpianti`).
- Navigation: exactly one plant -> `TSDeviceListActivity`, else `TSHomeActivity`.

## Session expiry
`BaseActivity.onResume` (`Activity/BaseActivity.java:2074`): if `PREF_TOKEN_DATE` is older than 1 h, or `Constants.token` is empty, toast `sessioneScaduta`, clear token, restart `LoginActivity`. Skipped for SignUp, ChangePwd, GDPR, bootloader screens and demo. The 1 h clock is **not** refreshed by API calls; only a new login resets it.
Nothing refreshes the session in the background: the PICO 5 s poll keeps running only while the user stays on the screen and the activity is resumed.

## Sign-up
`SignUpActivity` (`Activity/SignUpActivity.java`)
1. On email focus-out: `GET /apiTS/v1/CheckEmail?email=` -> `ResCode 9` means exists.
2. Password rule via `Validation.isValidPassword`; ToS + Privacy checkboxes mandatory (marketing optional).
3. `POST /apiTS/v2/RegisterUser` body = `User` `{Id:0, Name, Username, Password(AES), DeviceId, Lang, Ok_Marketing, Ok_TOS, Ok_Privacy}`. `Lang` is the device language (`nl-BE` special case).
4. `ResCode 0` -> toast "check email" and finish (account must be confirmed by email link).

## Forgot password
Popup asks email -> `POST /apiTS/v1/ForgotPwd` with `LoginModel{Username, Password:"", DeviceId, Timezone}`. Result toasts reuse the login `ResCode` table (0 = mail sent, 6 = temporary password sent).

## Change password
`ChangePwdActivity` reached from login `ResCode 6`. Builds `ChangePwdModel` (`LoginModel` + `OldPassword`), both AES-encrypted, `POST /apiTS/v2/ChangePwd`. The handler is `logIn`, so a successful change logs in directly (`type 2`) and updates the remembered password (`changePref`).

## GDPR
`GDPRActivity` -> `POST /apiTS/v2/AcceptTermsOfUse` `{"Username","Ok_TOS","Ok_Privacy","Ok_Marketing"}` (type 32). On `ResCode 0` the screen just finishes; the user lands on the login form and logs in again (no automatic re-login).

## Delete account
Menu in `HomeActivity`/`TSHomeActivity`/`TSDeviceListActivity` -> `DELETE /api/v1/DeleteUser` (type 20). On `ResCode 0`: `SavePreferences.deletePref()` and back to login. Server deletes accounts, plants, devices.

## Demo mode
"Demo" menu item: `Constants.ISDEMO=true`, `DataClass.populateDemo`, opens `TSHomeActivity`. No network; `PicoActivity` skips its poll timer when `ISDEMO`.

## Logout
No dedicated logout call found; leaving requires session expiry or account delete (inferred from absence in sources).
