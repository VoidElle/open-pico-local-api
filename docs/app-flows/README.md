# Flussi locali PICO (app Tecnosystemi decompilata)

Mappa dei flussi locali PICO ricavata da `Export-Pico/sources/it/tecnosystemi/TS` (JADX).
Riferimenti `file:riga` relativi a quella cartella. "(inferred)" = dedotto, non letto.
Fuori scope: VMC, SeiX, ControlUnit legacy.

| File | Contenuto |
|------|-----------|
| [01-transport.md](01-transport.md) | UDP: invio 40070, risposta sempre su 40069. Envelope `{cmd,frm,idp,pin}`, ACK `res:99`, retry/timeout, binding rete Android, quirk |
| [02-pico-runtime.md](02-pico-runtime.md) | Polling `stato_sync` 5 s, parsing stato, `upd_pico` (on/off, `mod` 1..12, speed, umidità, night, led, reset), `upd_datetime`, `get/set_fasce`, `get/set_slave` |
| [03-provisioning.md](03-provisioning.md) | Join AP `Pico_config`/`Pico_<SER>`, `pico_info`, `check_led`, `scan_wifi`, `config` online/offline/slave, `check_pin`, `pico_ap` |
| [04-firmware-ota.md](04-firmware-ota.md) | Catalogo firmware cloud, `ota_start` + TCP 40060 |

Punti chiave:
- Locale vs cloud deciso dal flag per-device `Pico.offline`, non da rilevamento runtime.
- App parla sempre con `192.168.4.1` (AP device). IP LAN usato solo per slave da `get_slave`. Nessuna discovery.
- PIN in chiaro; ogni retry usa nuovo `idp`; `resetIDP()` riporta a 1 a ogni riconnessione.
