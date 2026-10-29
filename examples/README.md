# 💡 Examples

Ready-to-run scripts that demonstrate the main features of the `open-pico-local-api` library.
Every script accepts CLI arguments - no code editing required.

---

## Scripts

### [`basic_control.py`](local/basic_control.py)

Connects to a single device, prints its current status, turns it on, and sets the operating mode.

```bash
python3 examples/local/basic_control.py --ip 192.168.1.100 --pin 1234
```

---

### [`multi_device.py`](local/multi_device.py)

Controls multiple devices concurrently over a shared UDP transport.
Connects all devices at once, reads their statuses in parallel, then sets a uniform mode across all of them.

```bash
python3 examples/local/multi_device.py --pin 1234 --ips 192.168.1.100 192.168.1.101 192.168.1.102
```

---

### [`auto_discovery.py`](local/auto_discovery.py)

Scans a subnet for Pico devices, then connects to each discovered device and reads its status.

> ⚠️ All devices on the network must share the same PIN to be discovered in a single scan.

```bash
python3 examples/local/auto_discovery.py --subnet 192.168.1.0/24 --pin 1234

# Longer timeout for larger or slower networks
python3 examples/local/auto_discovery.py --subnet 192.168.1.0/24 --pin 1234 --timeout 5.0
```

---

### [`adaptive_climate.py`](local/adaptive_climate.py)

Reads the current sensor values (humidity, CO₂) and automatically picks the best operating mode and fan speed:

| Condition | Mode | Fan |
|-----------|------|-----|
| Humidity > 70% | `HUMIDITY_EXTRACTION` | 80% |
| CO₂ > 1000 ppm | `CO2_RECOVERY` | 70% |
| Normal | `HEAT_RECOVERY` | 50% |

```bash
# Run once
python3 examples/local/adaptive_climate.py --ip 192.168.1.100 --pin 1234

# Keep running and re-evaluate every 60 s
python3 examples/local/adaptive_climate.py --ip 192.168.1.100 --pin 1234 --loop --interval 60
```

---

### [`monitoring.py`](local/monitoring.py)

Continuously polls a device and prints a status report. Alerts on errors or when filter maintenance is required.

```bash
python3 examples/local/monitoring.py --ip 192.168.1.100 --pin 1234

# Custom polling interval
python3 examples/local/monitoring.py --ip 192.168.1.100 --pin 1234 --interval 10
```

Sample output:
```
[14:32:01]  ✅ Healthy  🟢 ON
  Mode    : HEAT_RECOVERY
  Fan     : 50%
  Temp    : 22.5°C
  Humidity: 48%
  CO₂     : 620 ppm
  Night   : Inactive
  Uptime  : 12.3 days
```

---

### [`maintenance.py`](local/maintenance.py)

Checks whether the filter maintenance flag is set and, if so, resets it.

```bash
python3 examples/local/maintenance.py --ip 192.168.1.100 --pin 1234

# Reset even if the flag is not set
python3 examples/local/maintenance.py --ip 192.168.1.100 --pin 1234 --force
```

---

### [`idp_diagnostic.py`](local/idp_diagnostic.py)

Diagnoses a device that stopped responding by brute-forcing its IDP. The normal retry logic only
probes 5 consecutive IDP values; this sweeps a wider range to find the one the device answers to,
then realigns the client counter so communication resumes.

```bash
# Sweep the full IDP range (slow - narrow it for speed)
python3 examples/local/idp_diagnostic.py --ip 192.168.1.100 --pin 1234

# Narrow the range and probe every hit
python3 examples/local/idp_diagnostic.py --ip 192.168.1.100 --pin 1234 --start 1 --end 500 --all
```

---

## Common arguments (local examples, in `examples/local/`)

| Argument | Used by | Description |
|----------|---------|-------------|
| `--ip` | all except `auto_discovery` | Device IP address |
| `--pin` | all | Device PIN |
| `--subnet` | `auto_discovery` | CIDR range to scan (e.g. `192.168.1.0/24`) |
| `--ips` | `multi_device` | Space-separated list of IP addresses |
| `--timeout` | `auto_discovery`, `idp_diagnostic` | Scan timeout / per-IDP wait in seconds |
| `--interval` | `monitoring`, `adaptive_climate` | Polling/re-evaluation interval in seconds |
| `--loop` | `adaptive_climate` | Keep running instead of running once |
| `--force` | `maintenance` | Reset maintenance flag regardless of its state |
| `--start` / `--end` | `idp_diagnostic` | IDP range to sweep |
| `--all` | `idp_diagnostic` | Probe the whole range instead of stopping at first hit |

---

## Cloud examples (in `examples/cloud/`)

These use `PicoCloudClient` and need `aiohttp` and `cryptography` (installed with the package). Credentials come from flags (`--email`, `--password`, `--serial`, `--pin`) or the env vars `PICO_EMAIL`, `PICO_PASSWORD`, `PICO_SERIAL`, `PICO_PIN`.

| Example | What |
|---------|------|
| [`login.py`](cloud/login.py) | Login only, prints plant/device counts |
| [`list_devices.py`](cloud/list_devices.py) | Plants and devices of the account (`--json` for raw). Cloud gives no PINs |
| [`basic_cloud.py`](cloud/basic_cloud.py) | Status, on, mode change |
| [`simple_actions.py`](cloud/simple_actions.py) | One-shot CLI: `status`, `on`, `off`, `mode N`, `fan P`, `led`, `night`, `humidity` |
| [`adaptive_cloud.py`](cloud/adaptive_cloud.py) | Humidity/CO2 driven mode+fan, sends only on change, `--loop` |
| [`monitor_cloud.py`](cloud/monitor_cloud.py) | Poll every 5 s, print diffs, backoff on errors |
| [`multi_device_cloud.py`](cloud/multi_device_cloud.py) | Every PICO of the account on one login (`use_device`), bulk `--turn` / `--set-mode` |

Warning: these examples hit the real cloud. Use your own account.
