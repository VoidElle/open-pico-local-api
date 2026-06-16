# 🌊 Open Pico Local API

> *Asynchronous Python library for Tecnosystemi Pico IoT devices*

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/github/v/release/VoidElle/open-pico-local-api)](https://github.com/VoidElle/open-pico-local-api/releases)
[![PyPI](https://img.shields.io/pypi/v/open-pico-local-api)](https://pypi.org/project/open-pico-local-api/)
[![Tests](https://github.com/VoidElle/open-pico-local-api/actions/workflows/tests.yml/badge.svg)](https://github.com/VoidElle/open-pico-local-api/actions/workflows/tests.yml)

**[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Auto-Discovery](#-auto-discovery) • [Documentation](#-documentation) • [Internals](#-internals) • [Examples](#-examples) • [Scripts](#️-scripts) • [Testing](#-testing)**

---

## ✨ Features

### 🚀 **Performance**
- Built with **asyncio** for non-blocking operations
- Efficient UDP communication protocol
- **Shared transport manager** for multiple devices
- Automatic IDP synchronization and range allocation

### 🔄 **Reliability**
- **Auto-reconnect** on connection failures
- Configurable retry logic
- Robust error handling
- **IDP sync recovery** for resilient communication

### 🎯 **Developer Friendly**
- Type-safe with Python enums
- Async context manager support
- Comprehensive logging
- **Multi-device orchestration** support

### 🎛️ **Full Control**
- Complete device mode management
- Fan speed control
- Humidity & LED settings
- **Concurrent device operations**

---

## 📦 Installation

### pip (recommended)

```bash
pip install open-pico-local-api
```

### Home Assistant integration

Add to your integration's `manifest.json` and Home Assistant will install the library automatically when the integration loads:

```json
"requirements": [
  "open-pico-local-api==2.5.2"
]
```

### Manual

1. Clone this repository in your project
2. Import `PicoClient` and other relevant classes in your files

---

## 🚀 Quick Start

### Single Device
```python
import asyncio
from open_pico_local_api import PicoClient, DeviceModeEnum

async def main():
    # Initialize device with shared transport (default)
    device = PicoClient(
        ip="192.168.1.100",
        pin="1234",
        device_id="living_room",
        verbose=True
    )

    # Use context manager for automatic cleanup
    async with device:
        await device.turn_on()
        status = await device.get_status()
        print(f"✓ Device online: {status.operating.mode}")
        
        await device.change_operating_mode(DeviceModeEnum.CO2_RECOVERY)
        await device.change_fan_speed(75)
        print("✓ Configuration complete!")

if __name__ == "__main__":
    asyncio.run(main())
```

### Multiple Devices
```python
import asyncio
from open_pico_local_api import PicoClient

async def main():
    # Create multiple device clients
    living_room = PicoClient(
        ip="192.168.1.100",
        pin="1234",
        device_id="living_room",
        verbose=True
    )
    
    bedroom = PicoClient(
        ip="192.168.1.101",
        pin="1234",
        device_id="bedroom",
        verbose=True
    )

    # Control both devices simultaneously
    async with living_room, bedroom:
        # Concurrent operations
        await asyncio.gather(
            living_room.turn_on(),
            bedroom.turn_on()
        )
        
        # Get status from both devices
        status1, status2 = await asyncio.gather(
            living_room.get_status(),
            bedroom.get_status()
        )
        
        print(f"Living Room: {status1.sensors.temperature_celsius}°C")
        print(f"Bedroom: {status2.sensors.temperature_celsius}°C")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 📚 Table of Contents

- [Configuration](#️-configuration)
- [Multi-Device Support](#-multi-device-support)
- [Auto-Discovery](#-auto-discovery)
- [Connection Management](#-connection-management)
- [Device Control](#️-device-control)
  - [Power Control](#power-control)
  - [Operating Modes](#operating-modes)
  - [Fan Speed](#fan-speed)
  - [Night Mode](#night-mode)
  - [LED Control](#led-control)
  - [Humidity Control](#humidity-control)
- [IDP Management](#-idp-management)
- [Data Models](#️-data-models)
- [Exception Handling](#-exception-handling)
- [Internals](#-internals)
- [Examples](#-examples)
- [Scripts](#️-scripts)
- [Testing](#-testing)
- [Best Practices](#-best-practices)

---

## ⚙️ Configuration

### **Constructor Parameters**

| Parameter | Type | Default | Description |
|-----------|:----:|:-------:|-------------|
| **`ip`** ⭐ | `str` | *required* | 🌐 IP address of the Pico device |
| **`pin`** ⭐ | `str` | *required* | 🔐 PIN code for authentication |
| `device_id` | `str` | `None` | 🏷️ Unique identifier (auto-generated if not provided) |
| `device_port` | `int` | `40070` | 📡 UDP port of the device |
| `local_port` | `int` | `40069` | 📡 Local UDP port |
| `timeout` | `float` | `5` | ⏱️ Command timeout (seconds) |
| `retry_attempts` | `int` | `3` | 🔄 Number of retry attempts |
| `retry_delay` | `float` | `2.0` | ⏳ Delay between retries (seconds) |
| `verbose` | `bool` | `False` | 📢 Enable verbose logging |
| `poll_jitter` | `float` | `0.0` | 🕐 Max random delay after connect (seconds) to spread concurrent polls across devices |

---

## 🔀 Multi-Device Support

### How It Works

**IDP Range Allocation**
- Each device is assigned a unique IDP (Identifier Packet) range (10,000 IDs per device)
- The shared transport manager routes responses to the correct device based on IDP
- Automatic IDP synchronization ensures reliable communication

**Shared UDP Socket**
- All devices share a single UDP socket on the specified local port
- Responses are distributed to device-specific queues
- No port conflicts, even with multiple devices

**Automatic Management**
- Transport manager is automatically initialized on first device connection
- IDP ranges are allocated dynamically as devices register
- Cleanup happens automatically when devices disconnect

### Usage

Simply create multiple `PicoClient` instances - shared transport is always active:
```python
device1 = PicoClient(ip="192.168.1.100", pin="1234", device_id="device1")
device2 = PicoClient(ip="192.168.1.101", pin="1234", device_id="device2")
device3 = PicoClient(ip="192.168.1.102", pin="1234", device_id="device3")

async with device1, device2, device3:
    # All devices can be controlled concurrently
    statuses = await asyncio.gather(
        device1.get_status(),
        device2.get_status(),
        device3.get_status()
    )
```

### Device ID

The `device_id` parameter is **recommended** when using multiple devices:
- Provides meaningful identification in logs
- Used for internal routing and debugging
- Auto-generated as `{ip}:{port}` if not provided
```python
# Recommended: explicit device IDs
device1 = PicoClient(ip="192.168.1.100", pin="1234", device_id="living_room")
device2 = PicoClient(ip="192.168.1.101", pin="1234", device_id="bedroom")

# Also works: auto-generated IDs
device3 = PicoClient(ip="192.168.1.102", pin="1234")  # ID: "192.168.1.102:40070"
```

---

## 🔍 Auto-Discovery

`PicoAutoDiscovery` scans a subnet and returns the IPs of all Pico devices it finds. All traffic goes through `SharedTransportManager` (port 40069) - Pico devices are hardcoded to reply only to that port.

### Basic Usage

```python
import asyncio
from open_pico_local_api import PicoAutoDiscovery

async def main():
    ips = await PicoAutoDiscovery.discover(pin="1234", subnet="192.168.1.0/24")
    print(ips)  # ["192.168.1.42", "192.168.1.55"]

asyncio.run(main())
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|:----:|:-------:|-------------|
| **`pin`** ⭐ | `str` | *required* | PIN sent with each probe |
| **`subnet`** ⭐ | `str` | *required* | CIDR range to scan (e.g. `"192.168.1.0/24"`) |
| `device_port` | `int` | `40070` | UDP port Pico devices listen on |
| `local_port` | `int` | `40069` | Local port for `SharedTransportManager` |
| `scan_timeout` | `float` | `2.0` | Seconds to collect replies (collection starts concurrently with probing) |
| `max_concurrent` | `int` | `50` | Max simultaneous probes |
| `verbose` | `bool` | `False` | Enable debug logging |

**Returns:** sorted `List[str]` of discovered IP addresses.

> ⚠️ **Note:** A single PIN is broadcast to every host in the subnet. Only devices that share that PIN will respond. Devices with a different PIN will be silently missed.

### Discovery + Connect

```python
async def auto_connect():
    ips = await PicoAutoDiscovery.discover(pin="1234", subnet="192.168.1.0/24")
    if not ips:
        print("No devices found")
        return

    clients = [PicoClient(ip=ip, pin="1234") for ip in ips]
    async with asyncio.TaskGroup() as tg:
        for client in clients:
            tg.create_task(client.connect())

    statuses = await asyncio.gather(*[c.get_status() for c in clients])
    for ip, status in zip(ips, statuses):
        print(f"{ip}: {status.operating.mode.name}")
```

---

## 🔌 Connection Management

### **Connect to Device**

Establishes UDP connection to the Pico device. With shared transport, this registers the device with the transport manager and allocates an IDP range.
```python
await device.connect()
```

**Raises:** `ConnectionError` if connection fails

### **Disconnect from Device**

Gracefully closes the connection and cleans up resources. Unregisters from shared transport and releases IDP range.
```python
await device.disconnect()
```

### **Check Connection Status**

Returns `True` if device is currently connected.
```python
if device.connected:
    print("✓ Device is online")
```

---

## 🎛️ Device Control

### Get Device Status

Retrieve complete device state with sensor readings, operating parameters, and system information.
```python
status = await device.get_status()

# Device Information
print(f"Name: {status.device_info.name}")
print(f"Firmware: {status.device_info.firmware_full}")
print(f"IP: {status.device_info.ip}")

# Operating Status
print(f"Mode: {status.operating.mode}")
print(f"Power: {'ON' if status.is_on else 'OFF'}")
print(f"Fan Speed: {status.operating.speed}%")
print(f"Night Mode: {status.operating.is_night_mode_active}")

# Sensor Readings
print(f"Temperature: {status.sensors.temperature_celsius}°C")
print(f"Humidity: {status.sensors.humidity_percent}%")
print(f"CO2: {status.sensors.eco2} ppm")
print(f"TVOC: {status.sensors.tvoc} ppb")
print(f"Air Quality: {status.sensors.air_quality}")

# System Info
print(f"Uptime: {status.system.uptime_days:.1f} days")
print(f"Memory Free: {status.system.memory_free_kb:.1f} KB")
print(f"Health: {'Healthy' if status.is_healthy else 'Issues Detected'}")

# Feature Support
print(f"Supports Fan Control: {status.support_fan_speed_control}")
```

**Returns:** `PicoDeviceModel` with complete device state

**Parameters:**
- `retry` (bool): Enable retry logic (default: `True`)

### Power Control

Turn the device on or off.
```python
# Turn on
await device.turn_on()

# Turn off
await device.turn_off()
```

**Returns:** `CommandResponseModel` with operation result

### Operating Modes

Change the device operating mode.
```python
from open_pico_local_api import DeviceModeEnum

await device.change_operating_mode(DeviceModeEnum.CO2_RECOVERY)
```

**Available Modes:**
- `HEAT_RECOVERY` - Heat recovery mode
- `EXTRACTION` - Extraction only
- `IMMISSION` - Immission only
- `HUMIDITY_RECOVERY` - Humidity-based recovery
- `HUMIDITY_EXTRACTION` - Humidity-based extraction
- `COMFORT_SUMMER` - Summer comfort mode
- `COMFORT_WINTER` - Winter comfort mode
- `CO2_RECOVERY` - CO2-based recovery
- `CO2_EXTRACTION` - CO2-based extraction
- `HUMIDITY_CO2_RECOVERY` - Combined humidity/CO2 recovery
- `HUMIDITY_CO2_EXTRACTION` - Combined humidity/CO2 extraction
- `NATURAL_VENTILATION` - Natural ventilation mode

### Fan Speed

Adjust fan speed as a percentage (0-100).
```python
# Set fan speed to 50%
await device.change_fan_speed(50)

# Force change regardless of mode
await device.change_fan_speed(75, force=True)
```

**Parameters:**
- `percentage` (int): Speed from 0-100
- `retry` (bool): Enable retry logic
- `force` (bool): Skip mode validation (only supported in `HEAT_RECOVERY`, `EXTRACTION`, `IMMISSION`, `COMFORT_SUMMER`, `COMFORT_WINTER`)

### Night Mode

Activates quiet operation for nighttime use.
```python
# Enable night mode
await device.set_night_mode(True)

# Disable night mode
await device.set_night_mode(False)

# Force enable even if mode doesn't support it
await device.set_night_mode(True, force=True)
```

**Parameters:**
- `enable` (bool): True to enable, False to disable
- `retry` (bool): Enable retry logic
- `force` (bool): Skip mode validation

> ⚠️ **Note:** Only supported in modes that allow fan speed control

> 🔥 **WARNING:** Using `force=True` bypasses mode compatibility checks and may cause the device to behave unexpectedly or reset its state. Use with caution and only when you understand the implications.

### LED Control

Controls device indicator lights.
```python
# Turn off all LEDs
await device.set_led_status(False)

# Turn on LEDs
await device.set_led_status(True)
```

### Humidity Control

Set target humidity level.
```python
from open_pico_local_api import TargetHumidityEnum

await device.set_target_humidity(TargetHumidityEnum.FIFTY_PERCENT)

# Force set even if mode doesn't support it
await device.set_target_humidity(TargetHumidityEnum.FIFTY_PERCENT, force=True)
```

**Parameters:**
- `target_humidity` (TargetHumidityEnum): Target humidity level
- `retry` (bool): Enable retry logic
- `force` (bool): Skip mode validation

**Available Levels:**
- `FORTY_PERCENT` - Target 40% humidity
- `FIFTY_PERCENT` - Target 50% humidity
- `SIXTY_PERCENT` - Target 60% humidity

> ⚠️ **Note:** Only supported in humidity-based modes: `HUMIDITY_RECOVERY`, `HUMIDITY_EXTRACTION`, `CO2_RECOVERY`, `CO2_EXTRACTION`

> 🔥 **WARNING:** Using `force=True` bypasses mode compatibility checks and may cause the device to behave unexpectedly or reset its state. Use with caution and only when you understand the implications.

---

## 🔢 IDP Management

The library uses **IDP (Identifier Packet)** for reliable communication between client and device.

### What is IDP?

IDP is a sequential identifier used to match commands with responses. Each device maintains its own IDP counter that must stay synchronized with the client.

### IDP Range Allocation

When using shared transport (multi-device mode):
- Each device is assigned a unique IDP range (10,000 IDs)
- Device 1: IDP 1-10,000
- Device 2: IDP 10,001-20,000
- Device 3: IDP 20,001-30,000
- And so on...

### Automatic IDP Synchronization

The library automatically handles IDP synchronization:
1. Sends command with current IDP
2. If no response, increments IDP and retries (up to 5 times)
3. If still no response, resets IDP to range start
4. Continues with full retry logic

### Manual IDP Reset

If communication becomes stuck (e.g., device was restarted), manually reset the IDP counter:
```python
# Reset IDP counter to start of allocated range
await device.reset_idp()
```

This is useful when:
- Device was power cycled
- Device firmware was updated
- Communication became persistently unresponsive

### IDP Logging

Enable verbose mode to see IDP synchronization in action:
```python
device = PicoClient(ip="192.168.1.100", pin="1234", verbose=True)

# Logs will show:
# → [living_room] SENT: stato_sync (idp:1)
# ✓ [living_room] ACK received (idp:1)
# ✓ [living_room] Response received (idp:1)
# ⚠ [living_room] No response for IDP 5 - likely out of sync
# ✓ [living_room] IDP synchronized after 2 increments
```

---

## 🏗️ Data Models

The library provides strongly-typed data models for all device information.

### **PicoDeviceModel**

Main model containing complete device state with the following components:
```python
status = await device.get_status()

# Access sub-models
status.device_info      # Device identification
status.sensors          # Sensor readings
status.operating        # Operating parameters
status.parameters       # Parameter arrays
status.system          # System information
```

### **DeviceInfoModel**

Device identification and hardware information.
```python
print(f"Name: {status.device_info.name}")
print(f"Firmware: {status.device_info.firmware_full}")
print(f"Model: {status.device_info.model}")
print(f"IP: {status.device_info.ip}")
print(f"Has Datamatrix: {status.device_info.has_datamatrix}")
```

### **SensorReadingsModel**

Real-time environmental sensor data.
```python
sensors = status.sensors

print(f"Temperature: {sensors.temperature_celsius}°C")
print(f"Humidity: {sensors.humidity_percent}%")
print(f"CO2: {sensors.eco2} ppm")
print(f"TVOC: {sensors.tvoc} ppb")
print(f"Air Quality: {sensors.air_quality}")
print(f"Has Air Quality Sensors: {sensors.has_air_quality}")
```

### **OperatingParametersModel**

Current operating state and settings.
```python
op = status.operating

print(f"Mode: {op.mode}")
print(f"Is On: {op.is_on}")
print(f"Fan Speed: {op.speed}%")
print(f"Fan Running: {op.fan_running}")
print(f"Night Mode: {op.is_night_mode_active}")
print(f"LED On: {op.is_led_state_on()}")
```

### **SystemInfoModel**

System diagnostics and health.
```python
sys = status.system

print(f"Uptime: {sys.uptime_days:.1f} days")
print(f"Memory Free: {sys.memory_free_kb:.1f} KB")
print(f"Has RTC: {sys.has_rtc}")
print(f"Date/Time: {sys.date} {sys.time}")
```

### **ParameterArraysModel**

Device parameter arrays and error tracking.
```python
params = status.parameters

print(f"Has Errors: {params.has_errors}")
print(f"Active Errors: {params.active_errors}")
print(f"Realtime Params: {params.realtime}")
```

### **CommandResponseModel**

Response from device control commands.
```python
response = await device.turn_on()

print(f"IDP: {response.idp}")
print(f"Frame from: {response.frame_from}")
print(f"Command: {response.command}")
```

---

## 🚨 Exception Handling

The library provides custom exceptions for different scenarios:

| Exception | Description |
|-----------|-------------|
| `PicoConnectionError` | Connection establishment or communication failures |
| `PicoTimeoutError` | Operation exceeded timeout duration |
| `NotSupportedError` | Feature not supported in current operating mode |
| `PicoDeviceError` | General device-related errors (base class) |

**Example:**
```python
from open_pico_local_api import PicoConnectionError, NotSupportedError

async def safe_operation():
    device = PicoClient(ip="192.168.1.100", pin="1234")
    
    try:
        await device.connect()
        await device.change_fan_speed(75)
        
    except NotSupportedError as e:
        print(f"⚠️  Feature not available: {e}")
        
    except PicoConnectionError as e:
        print(f"❌ Connection failed: {e}")
        
    finally:
        await device.disconnect()
```

---

## 🔬 Internals

Detailed documentation of the internal flows and architecture lives in [`docs/`](docs/):

| Document | Description |
|----------|-------------|
| [Architecture: Shared Transport](docs/architecture.md) | How the single UDP socket is shared across devices; IDP range allocation; O(log n) packet routing |
| [Command Flow](docs/command-flow.md) | The 4-step send/ACK/status/ACK UDP exchange; `_wait_for_response` state machine; timeout behaviour |
| [Retry Logic & IDP Sync](docs/retry-logic.md) | Two-level retry strategy; how IDP drift is detected and recovered; manual reset |
| [Connection Lifecycle](docs/connection-lifecycle.md) | `connect()` / `disconnect()` flow; `auto_reconnect` decorator; `SharedTransportManager.shutdown()` |
| [Auto-Discovery Flow](docs/auto-discovery.md) | Subnet probe; concurrent probe+collect; response validation; relation to registered devices |

---

## 💡 Examples
See [`examples/README.md`](examples/README.md) for full documentation and usage instructions.

---

## 🎯 Best Practices

### ✅ DO

- ✔️ Use **async context managers** for automatic cleanup
- ✔️ Enable **verbose mode** during development
- ✔️ Use **explicit device_id** when controlling multiple devices
- ✔️ Handle exceptions appropriately
- ✔️ Check mode compatibility before operations
- ✔️ Verify device status after using `force` parameter
- ✔️ Use `asyncio.gather()` for concurrent operations on multiple devices

### ❌ DON'T

- ✖️ Block the event loop with synchronous operations
- ✖️ Ignore connection errors
- ✖️ Use the same client instance across multiple event loops
- ✖️ Forget to disconnect when not using context managers
- ✖️ Use `force=True` without understanding the consequences
- ✖️ Apply incompatible settings without checking device state afterwards
- ✖️ Create multiple PicoClient instances for the same device

---

## 📦 Library Structure
```
open-pico-local-api/
├── scripts/
│   ├── bump_version.sh                # Bump version across all files
│   └── run_tests.sh                   # Run the full test suite
├── examples/
│   ├── basic_control.py               # Connect, read status, control a single device
│   ├── multi_device.py                # Concurrent control of multiple devices
│   ├── auto_discovery.py              # Discover devices then read their status
│   ├── adaptive_climate.py            # Auto-select mode from sensor readings
│   ├── monitoring.py                  # Continuous polling with alerts
│   └── maintenance.py                 # Check and reset filter maintenance flag
├── open_pico_local_api/
│   ├── __init__.py                    # Public API re-exports
│   ├── pico_client.py                 # Main client class
│   ├── pico_auto_discovery.py         # Subnet-based device discovery
│   ├── shared_transport_manager.py    # Shared UDP transport for multi-device
│   ├── enums/
│   │   ├── device_mode_enum.py        # Operating modes
│   │   ├── on_off_state_enum.py       # Power states
│   │   └── target_humidity_enum.py    # Humidity levels
│   ├── models/
│   │   ├── pico_device_model.py       # Complete device state
│   │   ├── command_response_model.py  # Command responses
│   │   ├── device_info_model.py       # Device identification
│   │   ├── sensor_readings_model.py   # Sensor data
│   │   ├── operating_parameters_model.py
│   │   ├── parameter_arrays_model.py
│   │   └── system_info_model.py       # System diagnostics
│   ├── utils/
│   │   ├── auto_reconnect.py          # Auto-reconnect decorator
│   │   ├── constants.py               # Mode constants
│   │   └── pico_protocol.py           # Base UDP protocol
│   └── exceptions/
│       ├── pico_device_error.py
│       ├── pico_connection_error.py
│       ├── pico_timeout_error.py
│       └── not_supported_error.py
└── tests/
    ├── test_exceptions.py
    ├── test_enums.py
    ├── test_models.py
    ├── test_shared_transport_manager.py
    ├── test_pico_auto_discovery.py
    ├── test_auto_reconnect.py
    └── test_pico_protocol.py
```

---

## 🛠️ Scripts

Utility scripts live in the [`scripts/`](scripts/) directory and must be run from the repo root.

### `scripts/bump_version.sh`

Keeps all version references in sync across `pyproject.toml`, `README.md`, and `pico_client.py` in one command.

```bash
./scripts/bump_version.sh patch     # 2.3.0 → 2.3.1
./scripts/bump_version.sh minor     # 2.3.0 → 2.4.0
./scripts/bump_version.sh major     # 2.3.0 → 3.0.0
./scripts/bump_version.sh 2.5.0     # set an explicit version
./scripts/bump_version.sh           # interactive menu
```

### `scripts/run_tests.sh`

Runs the full unit test suite with verbose output.

```bash
./scripts/run_tests.sh
```

---

## 📋 Requirements

- **Python 3.11+**
- **asyncio** support
- **Local network access** to Pico device(s)
- No third-party dependencies - stdlib only

---

## 🧪 Testing

The library ships with a full unit test suite (96 tests) covering all modules. No third-party packages needed.

### Run locally

```bash
./scripts/run_tests.sh
```

Or directly:

```bash
python3 -W all -m unittest discover -s tests -v
```

### CI

Tests run automatically on every push and pull request via GitHub Actions, across Python 3.11, 3.12, and 3.13.

### Coverage

| Module | Tests |
|--------|------:|
| `exceptions/` | 10 |
| `enums/` | 8 |
| `models/` | 34 |
| `shared_transport_manager.py` | 20 |
| `pico_auto_discovery.py` | 12 |
| `utils/auto_reconnect.py` | 6 |
| `utils/pico_protocol.py` | 6 |
| **Total** | **96** |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🆘 Support

- 🐛 **Issues**: [Report a bug](https://github.com/VoidElle/open-pico-local-api/issues)