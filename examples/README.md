# 💡 Examples

Ready-to-run scripts that demonstrate the main features of the `open-pico-local-api` library.
Every script accepts CLI arguments - no code editing required.

---

## Scripts

### [`basic_control.py`](basic_control.py)

Connects to a single device, prints its current status, turns it on, and sets the operating mode.

```bash
python3 examples/basic_control.py --ip 192.168.1.100 --pin 1234
```

---

### [`multi_device.py`](multi_device.py)

Controls multiple devices concurrently over a shared UDP transport.
Connects all devices at once, reads their statuses in parallel, then sets a uniform mode across all of them.

```bash
python3 examples/multi_device.py --pin 1234 --ips 192.168.1.100 192.168.1.101 192.168.1.102
```

---

### [`auto_discovery.py`](auto_discovery.py)

Scans a subnet for Pico devices, then connects to each discovered device and reads its status.

> ⚠️ All devices on the network must share the same PIN to be discovered in a single scan.

```bash
python3 examples/auto_discovery.py --subnet 192.168.1.0/24 --pin 1234

# Longer timeout for larger or slower networks
python3 examples/auto_discovery.py --subnet 192.168.1.0/24 --pin 1234 --timeout 5.0
```

---

### [`adaptive_climate.py`](adaptive_climate.py)

Reads the current sensor values (humidity, CO₂) and automatically picks the best operating mode and fan speed:

| Condition | Mode | Fan |
|-----------|------|-----|
| Humidity > 70% | `HUMIDITY_EXTRACTION` | 80% |
| CO₂ > 1000 ppm | `CO2_RECOVERY` | 70% |
| Normal | `HEAT_RECOVERY` | 50% |

```bash
# Run once
python3 examples/adaptive_climate.py --ip 192.168.1.100 --pin 1234

# Keep running and re-evaluate every 60 s
python3 examples/adaptive_climate.py --ip 192.168.1.100 --pin 1234 --loop --interval 60
```

---

### [`monitoring.py`](monitoring.py)

Continuously polls a device and prints a status report. Alerts on errors or when filter maintenance is required.

```bash
python3 examples/monitoring.py --ip 192.168.1.100 --pin 1234

# Custom polling interval
python3 examples/monitoring.py --ip 192.168.1.100 --pin 1234 --interval 10
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

### [`maintenance.py`](maintenance.py)

Checks whether the filter maintenance flag is set and, if so, resets it.

```bash
python3 examples/maintenance.py --ip 192.168.1.100 --pin 1234

# Reset even if the flag is not set
python3 examples/maintenance.py --ip 192.168.1.100 --pin 1234 --force
```

---

## Common arguments

| Argument | Used by | Description |
|----------|---------|-------------|
| `--ip` | all except `auto_discovery` | Device IP address |
| `--pin` | all | Device PIN |
| `--subnet` | `auto_discovery` | CIDR range to scan (e.g. `192.168.1.0/24`) |
| `--ips` | `multi_device` | Space-separated list of IP addresses |
| `--timeout` | `auto_discovery` | Scan timeout in seconds (default: `2.0`) |
| `--interval` | `monitoring`, `adaptive_climate` | Polling/re-evaluation interval in seconds |
| `--loop` | `adaptive_climate` | Keep running instead of running once |
| `--force` | `maintenance` | Reset maintenance flag regardless of its state |
