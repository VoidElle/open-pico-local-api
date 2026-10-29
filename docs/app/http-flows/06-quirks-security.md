# 06 - Quirks and security notes

Observed in the decompiled app. Relevant if a client reimplements this API.

## Auth and crypto
- Basic auth password is hard-coded `PwdProAir`; user is the email after login, `UsrProAir` before. Real authentication is only the `Token` header.
- `FIX_TOKEN` (`Utils/Constants.java:57`) hard-coded for unauthenticated calls.
- User password is **encrypted, not hashed**, with a key derived from the public `android_id[0:8]` + fixed salt `ns91wr48`, zero IV. Anyone who knows the device id and salt can decrypt captured logins. Same scheme protects the rolling token.
- `android_id` is sent in the login body (`DeviceId`), so the key is effectively known to the server and any observer of the body. TLS is the only real protection.
- "Remember me" stores the password AES(`android_id`, pwd) in SharedPreferences (second scheme, `AESAlgorithm`, via `scottyab` AESCrypt).
- PICO PIN: plain text in URL query (`PIN=`), JSON body, and prefs.

## Token handling bugs
- `ThreadWebService.savepref` (`:823`) saves `this.token` (which is `FIX_TOKEN`) under `PREF_TOKEN`, not the server `Token`. The real token is kept only in memory (`Constants.token`) and later in `TOKENVALUE`. After process death the app forces re-login anyway.
- `Constants.token != ""` compares string references, not values. It works only because `token` is initialised to the same literal; any `new String("")` token would be treated as set.
- `calcNewToken` may return `null`; the call still goes out with `Token: null`.
- Counter increments per call, including the 5 s poll, so a stale counter (two devices, same account) can produce 401s (inferred: server compares counters).

## Flow quirks
- `ThreadWebService.run()` switch: case 32 and 33 have no `break` (`:178-182`). `updGDPR` falls through to `getPicoFasce` then `getPicoSetFasce`, which cast the activity to `PICOCronoSummaryActivity`/`PicoCronoSetActivity`; the `ClassCastException` is swallowed by `catch (Exception unused)`. Cosmetic but would double-send a request if the activity matched.
- All handlers swallow exceptions; many return silently (e.g. `signUp` with null response shows nothing).
- Session is 1 h hard from login (`BaseActivity.java:2074`), not sliding, with no refresh endpoint.
- `GetPlants` `ResDescr` is JSON inside JSON; `SendPicoCmd.Cmd` is JSON inside JSON.
- Device deleted locally before the server confirms (`PicoActivity.cancellaDevice`).
- `SendPicoCmd` type 28 handler has no caller (dead code).
- Success toast for CU commands says "applied within 10 minutes" (`okSendCMDToServer`); PICO commands use the same plumbing but the UI optimistically updates immediately.
- No certificate pinning; cleartext not enabled in the manifest (no `usesCleartextTraffic` hit).

## Reimplementation hints (for this repo)
1. Login: `POST /apiTS/v2/Login` with Basic `UsrProAir:PwdProAir`, `Token: FIX_TOKEN`, body as in [02-account-login.md](02-account-login.md). Keep the returned `Token`.
2. Before each later call: decrypt token, `counter+1`, re-encrypt, send; Basic user = email.
3. Poll `GetPICOState` every 5 s; parse `ResDescr` with the local `stato_sync` parser.
4. Send commands as `SendPicoCmd` with `frm:"mqtt"` and double-encoded `Cmd`.
5. Re-login before 1 h.
