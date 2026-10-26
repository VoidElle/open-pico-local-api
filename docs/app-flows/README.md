# PICO local flows (decompiled Tecnosystemi app)

Map of the PICO local flows derived from `Export-Pico/sources/it/tecnosystemi/TS` (JADX).
`file:line` references are relative to that folder. "(inferred)" = deduced, not read.
Out of scope: VMC, SeiX, legacy ControlUnit, master/slave configurations (cascade).

| File | Content |
|------|---------|
| [01-transport.md](01-transport.md) | UDP: send to 40070, reply always on 40069. Envelope `{cmd,frm,idp,pin}`, ACK `res:99`, retry/timeout, Android network binding, quirks |
| [02-pico-runtime.md](02-pico-runtime.md) | `stato_sync` polling every 5 s, state parsing, `upd_pico` (on/off, `mod` 1..12, speed, humidity, night, led, reset), `upd_datetime`, `get/set_fasce` |
| [03-provisioning.md](03-provisioning.md) | Join AP `Pico_config`/`Pico_<SER>`, `pico_info`, `check_led`, `scan_wifi`, `config` online/offline, `check_pin`, `pico_ap` |
| [04-firmware-ota.md](04-firmware-ota.md) | Cloud firmware catalog, `ota_start` + TCP 40060 |

Key points:
- Local vs cloud is decided by the per-device `Pico.offline` flag, not by runtime detection.
- The app always talks to `192.168.4.1` (device AP). No discovery.
- PIN in clear text; every retry uses a new `idp`; `resetIDP()` resets it to 1 on every reconnection.
