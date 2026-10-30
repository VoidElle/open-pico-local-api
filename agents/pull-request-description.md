---
name: pull-request-description
description: Writes structured PR titles and descriptions for open-pico-local-api, flagging protocol, transport, cloud and breaking-change risks. Use when preparing a pull request.
---

# Pull Request Description Agent - open-pico-local-api

## Purpose
Generate clear, structured PR descriptions for this async Python IoT library (local UDP client plus cloud fallback over HTTPS).

## PR Description Template

### Title format
`[scope]: short imperative description`

Scopes: `client`, `transport`, `models`, `enums`, `exceptions`, `utils`, `cloud`, `tests`, `docs`, `chore`

### Body structure
```
## What
[1–2 sentences: what changed and why]

## How
[Brief explanation of the approach, especially for protocol or async changes]

## Testing
[How the change was validated - manual test against device, unit test, etc.]

## Breaking Changes
[List any breaking changes, or "None"]
```

## Domain Context
- UDP IDP protocol: changes to IDP range logic or ACK handling are high-risk - call out explicitly
- `SharedTransportManager` is a singleton - changes affect all concurrent device clients
- Mode guards (`get_status()` checks before commands) are safety-critical; flag if removed or weakened
- `from_dict()` model changes may break downstream Home Assistant integrations - note field renames
- Async context manager (`__aenter__`/`__aexit__`) changes must ensure `disconnect()` always runs
- Exception class names: `PicoConnectionError`, `PicoTimeoutError`, `PicoDeviceError`, `NotSupportedError`, `PicoAuthError` (cloud) - never use bare `ConnectionError`/`TimeoutError`
- `PicoCloudClient` subclasses `PicoClient`: changes to `PicoClient` commands or `_execute_command_with_retry` also change cloud behaviour - say whether cloud was checked
- Cloud auth/crypto (`cloud/crypto.py`, login body, rolling token, `SESSION_TTL`) mirrors the official app (`docs/app/http-flows/`); call out any deviation and update those docs
- Cloud commands are ack-only and applied asynchronously; flag changes that assume immediate state
- Never paste credentials, tokens, PINs or serials from verbose logs into the PR
- The cloud is a fallback: flag anything that makes it a default or automatic route
- After any code change, all 101 tests must pass: `./scripts/run_tests.sh` or CI will catch it
- IPv6 subnets are not supported in `PicoAutoDiscovery` - raises `ValueError` by design
