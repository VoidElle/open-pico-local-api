# Report: disallineamenti app Tecnosystemi (PICO) vs `open_pico_local_api`

Data: 2026-10-26. Confronto tra `` (flussi ricavati dall'app decompilata) e implementazione (`../../../open_pico_local_api`, `examples/`, `README.md`, `docs/*.md`).

Scope: solo configurazione singola (no master/slave).

Metodo: 4 agenti di confronto (trasporto, runtime, provisioning, firmware) + 4 verificatori avversariali. Riportati solo finding `confirmed` o `partial` (con correzione del verificatore); 1 refutato, scartato. Finding duplicati tra aree accorpati.

> **Verifica lato app:** la prima analisi è stata fatta sugli snippet in ``, perché i sorgenti erano temporaneamente assenti. Una seconda passata, mirata e sul sorgente ripristinato, ha confermato:
> - #1, #5, #6, #7, #8, #9: `Commands/UDPSocket.java:56-176, 228-325`
> - #10-#13: `Model/Pico.java:409-437`
> - #14: `CmdPICO.java:160-173`, `PicoActivity.java:1488`
> - #3: `PicoActivity.java:568-575`
> - #2 con una correzione (vedi sotto)
> - OTA, 1300 B / 20 ms / `ota_end` / `ap_m:5`: `PicoBootloaderActivity.java:315-341`
> - soglia 1.0.3: `PicoBootloaderActivity.java:351`, `CheckLedPICOActivity.java:112`
>
> Una terza passata (2 agenti Sonnet) ha verificato sul sorgente reale tutti i punti restanti, da #4 a #27. Le correzioni sono integrate nei rispettivi punti: #4, #17 (`timezone`), #20/#23, #24 (`upd_datetime`), #27. Il lato lib è verificato sul codice.

Fatto confermato sul campo: il PICO risponde sempre a UDP 40069, qualunque sia la porta sorgente.

## Sintesi

| # | Sev. | Tipo | Titolo |
|---|------|------|--------|
| 1 | medium | wire | Retry: fino a 15 invii, anche dopo ACK (app: max 3, mai dopo ACK) |
| 2 | medium | parsing | `res` mai controllato: errore/PIN errato riportato come successo |
| 3 | medium | parsing | `err` con array a zero → `has_errors=True` permanente |
| 4 | medium | lib-doc | Regola porta di risposta descritta al contrario; `local_port` presentato come configurabile |
| 5 | low | wire | ACK device riconosciuto solo con `frm=="mst"`; attesa post-ACK fissa 2 s |
| 6 | low | wire | ACK client inviato solo per idp atteso (app: ACK a ogni messaggio con `res != 99`) |
| 7 | low | wire | Messaggio senza `res` con idp atteso trattato come risposta e ACK-ato |
| 8 | low | wire | idp a range per device (1, 10001, 20001…); modello "idp sincronizzato" non supportato dall'app |
| 9 | low | wire | Ordine campi envelope / spazi JSON / `pin: null` diversi da Gson |
| 10 | low | parsing | `mod` assente/sconosciuto → `HEAT_RECOVERY` |
| 11 | low | parsing | `on_off`: lib OFF se `!= 1`, app OFF solo se `== 2` |
| 12 | low | parsing | `s_umd` assente → 50% inventato; alias `umd` ignorato |
| 13 | low | parsing | LED: letto solo `led_on_off`; app usa anche `led`, `led_on_off_breve` |
| 14 | - | - | rimosso: fuori scope |
| 15 | low | semantica | `speed` documentato come %; la percentuale è `spd_rich`/`spd_row` |
| 16 | low | validazione | Setter senza range check (`mod`, `spd_row`, `s_umd`, `vr`) |
| 17 | low | semantica | `par_amb`/`par_ext`, `m_crono`, `vr`, `timezone` grezzi |
| 18 | low | robustezza | Listener mai ricreato dopo errore socket |
| 19 | low | robustezza | `register_device` con `device_id` esistente ignora nuovo ip/port |
| 20 | low | discovery | Discovery LAN con `idp=0`, senza ACK, richiede PIN |
| 21 | low | lib-doc | Docs idp: "device mantiene contatore" presentato come fatto; "releases IDP range" falso |
| 22 | low | lib-doc | `../../command-flow.md`: risposta post-comando = stato completo (non verificato) |
| 23 | low | lib-doc | Uso LAN / porte fisse presentati come standard; app usa solo `192.168.4.1` |
| 24 | low | gap | Comandi mancanti: `check_pin`, `upd_datetime`, `get/set_fasce`, `m_crono`, `pico_info` |
| 25 | low | gap | Nessun provisioning, OTA, gestione PIN `null`/`"-1"` |
| 26 | low | dead code | `utils/pico_protocol.py` duplicato inutilizzato |
| 27 | low | doc-app | `02-pico-runtime.md` incoerente su `spd_row` |

---

## 1. Retry: fino a 15 invii, anche dopo ACK — medium

- **App** (`01-transport.md` §4-5, `UDPSocket.java:284-311`): 3 tentativi, idp nuovo ciascuno; ritenta solo se nessun ACK entro 5 s. Ricevuto ACK, attende la risposta (5 s dall'invio) e non ritenta.
- **Lib** (`pico_client.py:494-536`, `:545`, `:553-558`): `retry_attempts=3` × `max_idp_sync=5` = fino a 15 invii, idp nuovo ciascuno. Dopo ACK attende solo 2.0 s fissi, poi reinvia lo stesso comando. Con `retry=False` invia comunque fino a 5 pacchetti.
- **Impatto:** comando non idempotente (`upd_pico`, `man_reset`) già eseguito può essere reinviato fino a 14 volte. Caso peggiore ~79 s contro ~16 s dell'app.
- **Fix:** se c'è ACK, attendi la risposta fino a `timeout` senza reinviare. Massimo 3 invii. `retry=False` = 1 invio. Sweep idp solo opt-in.

## 2. `res` mai controllato — medium (partial)

- **App** (`PicoActivity.checkRespSetMode`, `:1593-1603`; uso in `sendCmdUpdPico` `:1555-1564` e `sendCmdDataOraTImezone` `:1525-1539`): un comando è OK solo con `res==1`, e solo allora viene applicato lo stato ottimistico (`pico = tmpPico.getCopy()`). Con `res != 1` o `null` l'app scarta in silenzio la modifica, senza toast. `check_pin` richiede anch'esso `res==1`; altrimenti dialog PIN.
- **Lib** (`pico_client.py:574-580`): qualunque risposta con `res != 99` e idp corretto viene restituita. `CommandResponseModel` non ha `res`. `get_status` costruisce `PicoDeviceModel` senza verifica (`pico_device_model.py:144` default `res=0`).
- **Impatto:** PIN errato o errore device risultano successo; una risposta d'errore parsata come stato produce default inventati.
- **Fix:** esporre `res`; `PicoDeviceError` se `res != 1`; `get_status` richiede `res==1`.

## 3. `err` con array a zero → errore permanente — medium

- **App** (`02-pico-runtime.md` §3.1-3.2): `err` è `int[][]` per unità. Icona d'errore solo se un elemento è `!= 0`. Codice = `categoria*1000 + maschera 8 bit`. `10004` è un watchdog sintetico.
- **Lib** (`models/parameter_arrays_model.py:17-26`): `has_errors = any(len(l) > 0)`; `active_errors` include gli zeri. Da qui dipende `is_healthy` (`pico_device_model.py:158-164`).
- **Fix:** filtrare `e != 0`; opzionalmente decodificare categoria e maschera.
- **Da verificare sul device:** se invii davvero array a zero.

## 4. Regola porta di risposta descritta al contrario — medium

- **Fatto:** il device risponde sempre a 40069. L'app invia da una porta effimera e ascolta su 40069.
- **App** (`UDPSocket.java:41,91`: listener su 40069; `:262,340`: invio da `new DatagramSocket()` effimero).
- **Lib docs:** solo `docs/architecture.md:5` inverte la regola ("only respond to packets originating from port 40069"). `README.md:240` ("reply only to that port") e `pico_auto_discovery.py:6-7,47-48` sono corretti, al più ambigui. `local_port` è un parametro configurabile con default 40069 (`README.md:176,262`, `docs/auto-discovery.md:89`), senza avvertenza che deve restare 40069.
- **Impatto:** con `local_port != 40069` tutti i comandi vanno in timeout. La motivazione del socket condiviso è sbagliata, anche se il design resta valido: un solo listener deve possedere 40069.
- **Fix:** riformulare; `local_port` "deve restare 40069" oppure rimuoverlo.

## 5. ACK device solo con `frm=="mst"`; attesa post-ACK 2 s — low

- **App:** ACK = `res==99` con idp atteso, nessun controllo su `frm`. L'attesa della risposta segue il timeout del comando (10-15 s per `pico_info`/`config`).
- **Lib** (`pico_client.py:568`, `:545`): richiede `frm=="mst"`; altrimenti l'ACK viene scartato in silenzio. `ack_timeout=2.0` fisso. `docs/command-flow.md:23-70` fissa `frm=mst` come regola di protocollo.
- **Fix:** accettare ACK a prescindere da `frm`; attesa post-ACK = timeout del comando.

## 6. ACK client solo per idp atteso — low

- **App** (`UDPSocket.parsemsg`, `01-transport.md` §4): invia `{idp, frm:"app", res:99}` per ogni messaggio con `res != 99`, incluse risposte tardive, idp sconosciuti e push. Richiede anche `cmd`; senza, l'eccezione viene solo loggata.
- **Lib:** `pico_client.py:565-566` scarta gli altri idp senza ACK. `shared_transport_manager.py:70-75` li instrada/scarta senza ACK. Discovery: nessun ACK.
- **Impatto ipotetico:** se il firmware ritrasmette fino all'ACK → traffico spurio. Possibile legame con i sintomi "idp bloccato" (non verificato).
- **Fix:** ACK centralizzato in `SharedPicoProtocol.datagram_received` per ogni messaggio con `idp`, `res != 99` e `cmd`.

## 7. Messaggio senza `res` trattato come risposta — low

- **Lib** (`pico_client.py:574`): `response.get("res") != 99` è vero anche se `res` manca → restituito e ACK-ato.
- **App:** `getLong("res")` lancia → ignorato, nessun ACK.
- **Fix:** richiedere `"res" in response`.

## 8. idp a range per device — low (partial)

- **App:** contatore globale, parte da 1, `resetIDP()` a ogni riconnessione, idp nuovo per retry, nessuna sincronizzazione.
- **Lib** (`shared_transport_manager.py:136-137,221-222`, `pico_client.py:121,451`): range da 10000 per device. Il primo device parte da 1, gli altri da 10001, 20001… Wrap a `range_start`.
- **Nota:** è un problema solo se il firmware traccia davvero l'idp (vedi #21). Da verificare su hardware; in caso affermativo usare idp per device da 1 e demultiplexare per IP sorgente.

## 9. Formato envelope — low

- **App (Gson):** `{"cmd":…,"frm":"app","idp":N,"pin":"…"}`, compatto, `pin` null omesso.
- **Lib** (`pico_client.py:160-164,516,467`): ordine `cmd, frm, pin, idp`, separatori con spazi, `"pin": null` inviato.
- **Impatto:** nessuno con un parser JSON reale. Allineare (`separators=(',',':')`, idp prima di pin, omettere None) solo se emergono firmware con parser rigidi.

## 10-13. Parsing stato — low

| Campo | App (`02-pico-runtime.md` §3.1) | Lib | Fix |
|---|---|---|---|
| `mod` | aggiornato solo se presente; fuori 1..12 = nessun modo | `pico_device_model.py:75-78` default 1 → `HEAT_RECOVERY`, abilita guard speed/night | valore grezzo + `UNKNOWN`/`None` |
| `on_off` | OFF solo se `==2`; chiave assente = valore precedente | `:81-84` default 0 → OFF | `is_off = on_off == 2` |
| `s_umd` | da `umd` poi `s_umd` (vince `s_umd`), solo se presente | `:87-90` assente → warning + 50% | `Optional`, fallback `umd` |
| LED | `led_on_off` → `led` → `led_on_off_breve`, vince l'ultimo | `operating_parameters_model.py:45-47` solo `led_on_off` | property con stessa precedenza |

## 14. Manutenzione `man[]` — rimosso: fuori scope

- Rimosso: fuori scope. L'app tratta `man[0]` come il PICO; gli altri indici appartengono alla cascata. La lib usa solo l'indice 0 (`pico_client.py:310-312`): allineata.

## 15. `speed` presentato come % — low (partial)

- **App:** percentuale = `spd_rich` (richiesta) / `spd_row` (0..100). `speed` è un valore legacy (1..3, inferred). Il comando invia `speed:0` + `spd_row`.
- **Lib:** `README.md:336,579` e `examples/*` stampano `Fan Speed: {speed}%`. `fan_running = speed > 0` (`operating_parameters_model.py:36-38`). Dopo `change_fan_speed` (`speed:0`) il valore mostrato non riflette quanto impostato.
- **Fix:** documentare `speed_requested`/`speed_row` come percentuale; rivedere `fan_running`.

## 16. Nessuna validazione nei setter — low (partial)

`change_operating_mode` (`pico_client.py:188-196`), `change_fan_speed` (`:203-220`) e `set_target_humidity` (`:278-283`) inviano qualunque int. L'app limita `mod` 1..12 (6..11 nascosti con `vr==1`), `spd_row` 0..100, `s_umd` 1..3. Inoltre `change_fan_speed` non blocca la modalità notte (l'app disabilita lo slider) e salta il guard di modo con `percentage==100`.

## 17. Campi grezzi senza semantica — low

- **Sensori:** `par_amb`/`par_ext` passati come liste. App: `[1]` umidità /100, `[2]` indice qualità (soglie 200/400), `[3]` CO2 /100 valido solo nel range 30000..300000 grezzo, `-999` = non disponibile.
- **Temperature:** `AMB_tmpr`/`EXT_tmpr` non parsati.
- **Altri campi:** `m_crono` (1 = on, **2 = off**: un consumer che lo tratta come booleano sbaglia), `vr` (1 nasconde i modi 6..11, 3 abilita fasce e data), `timezone` (stringa; `"null"` trattato come null, chiave assente = `""`, `Pico.java:67-71`), `week` (0 = lunedì) non documentati.

## 18. Listener mai ricreato — low

`shared_transport_manager.py:98-104` si limita a loggare `error_received`/`connection_lost`; `_initialized` resta True (`:163-166`). Nessun rebind di 40069 finché non viene chiamato `shutdown()`. L'app invece ricrea il listener a ogni retry e riconnessione.

## 19. `register_device` con id esistente — low (partial)

`shared_transport_manager.py:210-218` aggiorna solo coda e callback, ignorando un nuovo ip/port. Riguarda solo chi riusa un `device_id` esplicito senza `disconnect()`, o due client vivi con lo stesso id. Il caso default (`ip:port`) non è toccato.

## 20. Discovery — low

`pico_auto_discovery.py`: scan della subnet con `stato_sync`, `idp=0` (l'app parte da 1), PIN obbligatorio, nessun ACK alle risposte. L'app non ha discovery. L'app usa sempre `192.168.4.1` (`UDPSocket.java:61-62`). Device con PIN diverso o non configurati non vengono trovati. Alternativa senza PIN: `pico_info` (restituisce `ser`, `fw_ver`, `config_mod`).

## 21-23. Documentazione lib — low

- **#21** `docs/retry-logic.md:3-30` e `README.md:480` presentano come fatto "il device mantiene un contatore idp che deve combaciare". L'app evidenzia il contrario: reset a 1, idp nuovo per retry, nessuna sincronizzazione. Va marcato come workaround osservato e non verificato. `reset_idp` torna a `range_start`, non a 1 (`retry-logic.md:70-74`). `README.md:305` "releases IDP range" è falso: `_next_idp_range` cresce soltanto (corretto in `architecture.md:96`).
- **#22** `docs/command-flow.md:10-28`: risposta post-comando = stato aggiornato completo. Nell'app è una domanda aperta; l'app considera solo `res==1`.
- **#23** `README.md:78,106-113,208-233` e `docs/architecture.md:32` presentano l'IP LAN come caso normale. L'app usa `192.168.4.1` (AP device) e il cloud in STA. L'uso LAN va documentato come estensione empirica. Assenti in README: AP default `192.168.4.1`, SSID `Pico_config`/`12345678`, `Pico_<SER>`/`TS_<SER>`.

## 24-25. Funzionalità mancanti — low (gap, nessun valore errato inviato)

- **Comandi runtime:**
  - `check_pin` (`res==1` = PIN valido)
  - `upd_datetime` (`date yyyy-MM-dd`, `time HH:mm:00`, `week` 0 = lun; `PicoActivity.java:1879-1882`). Bug app: `PICOCronoSummaryActivity.java:113-117` invia `hh:mm:ss` (formato 12h); nessuno dei due percorsi imposta il pin.
  - `get_fasce`/`set_fasce` (D0..D6, 4 slot `[start_min,end_min,mod,speed,hum]`, slot vuoto `[-1,-1,0,0,0]`)
  - `upd_pico` con `m_crono` 1/2
- **Info:** `pico_info` senza pin; `ser` mai parsato (`device_info_model.py`).
- **Provisioning:** `check_led`, `scan_wifi`, `config`, `pico_ap` (`pin:"-1"`, `ap_m`).
- **OTA:** `ota_start{sha256,size}` → TCP `192.168.4.1:40060` a chunk da 1300 B con pausa di 20 ms → `ota_end` → `pico_ap{ap_m:5}`.
- **PIN:** sempre serializzato; nessun supporto a `None` (omesso) né validazione (l'app richiede 4 caratteri convertibili in int).
- **Versioni:** nessun helper di confronto numerico (soglia 1.0.3 usata dall'app).

## 26. Dead code — low

`../../../open_pico_local_api/utils/pico_protocol.py`: `PicoProtocol` (coda singola, senza routing per idp) usato solo da `tests/local/test_pico_protocol.py`. Rimuovere o deprecare.

## 27. Incoerenze in `` — low

- `02-pico-runtime.md`: `:267-268,291` mappano `spd_row` su `Pico.speed_raw`, ma `:306` lo dice "solo debug, non entra in Pico". Il codice lo legge in `Pico` (`Pico.java:418-419`) e lo usa anche fuori dal pannello debug (`PicoActivity.java:1225,1467`). Togliere `spd_row` dalla lista a `:306`.

---

## Scartati

- "IDP bruteforce in `../../../scripts`": refutato. Il tool è `examples/local/idp_diagnostic.py`, già linkato in `docs/retry-logic.md:122`; il docstring avvisa già della durata.

## Priorità suggerite

1. **#1, #2, #5, #7:** loop di invio/attesa in `pico_client.py`; unico punto, alto valore.
2. **#3, #10-#14:** parsing robusto degli stati (impatto diretto su Home Assistant).
3. **#4, #21, #23:** correzioni alla documentazione (porta, idp, LAN).
4. **#6:** ACK centralizzato, poi verificare su hardware se il sintomo "idp bloccato" sparisce (in tal caso semplificare #8 e lo sweep idp).
5. **#24:** `check_pin` e `upd_datetime` (basso costo), poi fasce.

## Domande per test su hardware

- Il firmware traccia l'idp? (decide #8, #21 e la logica di sweep)
- Il firmware ritrasmette senza ACK del client? (#6)
- `err` arriva come array a zero quando non ci sono errori? (#3)
- La risposta a `upd_pico` è `{res:1}` o lo stato completo? (#22)
