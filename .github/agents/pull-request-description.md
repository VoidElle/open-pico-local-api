# Pull Request Description Agent — open-pico-local-api

## Purpose
Generate clear, structured PR descriptions for this async Python UDP IoT library.

## PR Description Template

### Title format
`[scope]: short imperative description`

Scopes: `client`, `transport`, `models`, `enums`, `exceptions`, `utils`, `docs`, `chore`

### Body structure
```
## What
[1–2 sentences: what changed and why]

## How
[Brief explanation of the approach, especially for protocol or async changes]

## Testing
[How the change was validated — manual test against device, unit test, etc.]

## Breaking Changes
[List any breaking changes, or "None"]
```

## Domain Context
- UDP IDP protocol: changes to IDP range logic or ACK handling are high-risk — call out explicitly
- `SharedTransportManager` is a singleton — changes affect all concurrent device clients
- Mode guards (`get_status()` checks before commands) are safety-critical; flag if removed or weakened
- `from_dict()` model changes may break downstream Home Assistant integrations — note field renames
- Async context manager (`__aenter__`/`__aexit__`) changes must ensure `disconnect()` always runs
