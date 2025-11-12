"""
Open Pico Local API

A Python library for controlling Tecnosystemi Pico IoT devices via UDP communication

Basic Usage:
    from iot_device import IoTDevice

    device = IoTDevice(ip="192.168.1.208", pin="1234")
    device.connect()

    status = device.get_status()
    print(status)

    device.disconnect()

Advanced Usage with Auto-Reconnect:
    # Enable auto-reconnect for all operations
    device = IoTDevice(ip="192.168.1.208", pin="1234", auto_reconnect=True)
    device.connect()

    # Methods will automatically reconnect if connection is lost
    status = device.get_status()

    # Context manager (auto connect/disconnect)
    with IoTDevice(ip="192.168.1.208", pin="1234", auto_reconnect=True) as device:
        status = device.get_status()
        response = device.send_command("set_temp", temp=25)
"""

import socket
import json
import time
import threading
from typing import Optional, Dict, Any
from queue import Queue, Empty

from exceptions.pico_device_error import PicoDeviceError
from exceptions.connection_error import ConnectionError
from exceptions.timeout_error import TimeoutError

__version__ = "1.1.0"
__all__ = ['PicoClient', 'PicoDeviceError', 'ConnectionError', 'TimeoutError']

from models.pico_device_model import PicoDeviceModel
from utils.auto_reconnect import auto_reconnect

# ----------------------------
# MAIN API CLASS
# ----------------------------
class PicoClient:
    """
    Pico Client

    A high-level interface for communicating with Technosystemi Pico IoT devices over UDP
    with automatic reconnection capabilities.

    Args:
        ip: Device IP address
        pin: Device PIN code
        device_port: Device UDP port (default: 40070)
        local_port: Local UDP port (default: 40069)
        timeout: Response timeout in seconds (default: 15)
        retry_attempts: Number of retry attempts (default: 3)
        retry_delay: Delay between retries in seconds (default: 2.0)
        auto_reconnect: Enable automatic reconnection (default: False)
        max_reconnect_attempts: Max reconnection attempts (default: 3)
        reconnect_delay: Delay between reconnection attempts (default: 2.0)

    Example:
        >>> device = PicoClient(ip="192.168.1.208", pin="1234", auto_reconnect=True)
        >>> device.connect()
        >>> status = device.get_status()  # Will auto-reconnect if connection lost
        >>> device.disconnect()

        >>> # With context manager
        >>> with PicoClient(ip="192.168.1.208", pin="1234", auto_reconnect=True) as device:
        ...     status = device.get_status()
    """

    def __init__(
            self,
            ip: str,
            pin: str,
            device_port: int = 40070,
            local_port: int = 40069,
            timeout: float = 15,
            retry_attempts: int = 3,
            retry_delay: float = 2.0,
            verbose: bool = False,
            auto_reconnect: bool = False,
            max_reconnect_attempts: int = 3,
            reconnect_delay: float = 2.0
    ):
        self.ip = ip
        self.pin = pin
        self.device_port = device_port
        self.local_port = local_port
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.verbose = verbose

        # Auto-reconnect settings
        self._auto_reconnect = auto_reconnect
        self._max_reconnect_attempts = max_reconnect_attempts
        self._reconnect_delay = reconnect_delay

        self._sock = None
        self._idp_counter = 1
        self._response_queue = Queue()
        self._running = False
        self._listen_thread = None
        self._lock = threading.Lock()
        self._connected = False
        self._event_callbacks = {}

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()
        return False

    @property
    def connected(self) -> bool:
        """Check if device is connected"""
        return self._connected

    def get_auto_reconnect(self) -> bool:
        """Check if auto-reconnect is enabled"""
        return self._auto_reconnect

    def set_auto_reconnect(self, value: bool):
        """Enable or disable auto-reconnect"""
        self._auto_reconnect = value
        if self.verbose:
            status = "enabled" if value else "disabled"
            print(f"Auto-reconnect {status}")

    def connect(self) -> None:
        """
        Connect to the Pico

        Raises:
            ConnectionError: If connection fails
        """
        if self._connected:
            return

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.bind(("", self.local_port))
            self._sock.settimeout(0.5)

            self._running = True
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()
            self._connected = True

            if self.verbose:
                print(f"✓ Connected to {self.ip}:{self.device_port}")
                if self._auto_reconnect:
                    print(f"  Auto-reconnect: enabled (max {self._max_reconnect_attempts} attempts)")

        except Exception as e:
            raise ConnectionError(f"Failed to connect: {e}")

    def disconnect(self) -> None:
        """Disconnect from the Pico"""
        self._running = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
        if self._sock:
            self._sock.close()
        self._connected = False

        if self.verbose:
            print("✓ Disconnected")

    @auto_reconnect
    def get_status(self, retry: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get device status (with auto-reconnect if enabled)

        Args:
            retry: Whether to retry on failure

        Returns:
            Device status dictionary or None if failed

        Raises:
            ConnectionError: If not connected and when auto-reconnect fails
            TimeoutError: If operation times out

        Example:
            >>> status = device.get_status()
            >>> print(status['name'])
        """
        if not self._connected:
            raise ConnectionError("Not connected to device")

        max_attempts = self.retry_attempts if retry else 1
        max_idp_sync = 10

        for attempt in range(1, max_attempts + 1):
            if attempt > 1:
                if self.verbose:
                    print(f"↻ Retry {attempt}/{max_attempts}")
                time.sleep(self.retry_delay)

            for idp_sync_attempt in range(max_idp_sync):
                if idp_sync_attempt > 0 and self.verbose:
                    print(f"  ↻ IDP sync attempt {idp_sync_attempt}/{max_idp_sync}")
                    time.sleep(0.5)

                idp = self._get_next_idp()
                cmd = {
                    "cmd": "stato_sync",
                    "frm": "app",
                    "idp": idp,
                    "pin": self.pin
                }

                if not self._send_command(cmd):
                    continue

                status = self._wait_for_response(idp, self.timeout)

                if status:
                    if idp_sync_attempt > 0 and self.verbose:
                        print(f"  ✓ IDP synchronized after {idp_sync_attempt} increments")
                    return status

        return None

    @auto_reconnect
    def send_command(self, command: str, **params) -> Optional[Dict[str, Any]]:
        """
        Send a custom command to the device (with auto-reconnect if enabled)

        Args:
            command: Command name
            **params: Additional command parameters

        Returns:
            Device response or None if failed

        Raises:
            ConnectionError: If not connected and when auto-reconnect fails

        Example:
            >>> device.send_command("set_temp", temp=25, mode="heat")
            >>> device.send_command("turn_on")
        """
        if not self._connected:
            raise ConnectionError("Not connected to device")

        idp = self._get_next_idp()
        cmd = {
            "cmd": command,
            "frm": "app",
            "idp": idp,
            "pin": self.pin,
            **params
        }

        if not self._send_command(cmd):
            return None

        return self._wait_for_response(idp, self.timeout)

    # ----------------------------
    # INTERNAL METHODS
    # ----------------------------

    def _get_next_idp(self) -> int:
        """Thread-safe IDP counter increment"""
        with self._lock:
            idp = self._idp_counter
            self._idp_counter += 1
            return idp

    def _listen_loop(self):
        """Background thread that continuously listens for UDP responses"""
        while self._running:
            try:
                data, addr = self._sock.recvfrom(8192)
                try:
                    response = json.loads(data.decode('utf-8'))
                    if self.verbose:
                        print(f"← RECV: {response.get('res', response.get('cmd', 'unknown'))}")
                    self._response_queue.put((response, addr))

                    # Trigger event callbacks
                    cmd = response.get('cmd', '')
                    if cmd in self._event_callbacks:
                        self._event_callbacks[cmd](response)

                except json.JSONDecodeError as e:
                    if self.verbose:
                        print(f"⚠ JSON decode error: {e}")
            except socket.timeout:
                continue
            except Exception as e:
                if self._running and self.verbose:
                    print(f"⚠ Listen error: {e}")
                if self._running:
                    # Socket error during listening might indicate connection issue
                    raise

    def _send_command(self, cmd: Dict[str, Any]) -> bool:
        """Send a command to the device"""
        try:
            data = json.dumps(cmd).encode('utf-8')
            self._sock.sendto(data, (self.ip, self.device_port))
            if self.verbose:
                cmd_name = cmd.get('cmd', 'ACK' if cmd.get('res') == 99 else 'unknown')
                print(f"→ SENT: {cmd_name} (idp:{cmd['idp']})")
            return True
        except Exception as e:
            if self.verbose:
                print(f"✗ Send error: {e}")
            raise  # Re-raise to trigger auto-reconnect

    def _wait_for_response(self, idp: int, timeout: float) -> Optional[Dict[str, Any]]:
        """Wait for responses matching the given idp"""
        got_ack = False
        end_time = time.time() + timeout
        ack_timeout = 3.0
        ack_received_time = None

        while time.time() < end_time:
            remaining = end_time - time.time()
            if remaining <= 0:
                break

            if got_ack and ack_received_time:
                if time.time() - ack_received_time > ack_timeout:
                    if self.verbose:
                        print(f"  ⚠ ACK received but no status - IDP may be out of sync")
                    return None

            try:
                response, addr = self._response_queue.get(timeout=min(remaining, 0.5))

                if response.get("idp") != idp:
                    continue

                if response.get("res") == 99 and response.get("frm") == "mst":
                    if self.verbose:
                        print(f"  ✓ ACK received (idp:{idp})")
                    got_ack = True
                    ack_received_time = time.time()

                elif response.get("res") != 99:
                    if self.verbose:
                        print(f"  ✓ Full status received (idp:{idp})")
                    full_status = response

                    ack = {"idp": idp, "frm": "app", "res": 99}
                    self._send_command(ack)
                    return full_status

            except Empty:
                continue

        return None


# ----------------------------
# EXAMPLE USAGE
# ----------------------------
if __name__ == "__main__":
    # Example 1: Basic usage with auto-reconnect in a continuous loop
    print("Example 1: Auto-reconnect enabled with continuous monitoring")
    device = PicoClient(
        ip="192.168.8.133",
        pin="1234",
        verbose=True,
        auto_reconnect=True,
        max_reconnect_attempts=3
    )

    try:
        device.connect()

        print("Starting continuous monitoring loop (Ctrl+C to stop)...")
        iteration = 0

        while True:
            iteration += 1
            print(f"\n{'='*60}")
            print(f"Iteration {iteration} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")

            try:
                # This will automatically reconnect if connection is lost
                status = device.get_status()
                if status:
                    status_parsed = PicoDeviceModel.from_dict(status)
                    print(f"\n📊 Device Status: {status_parsed.to_dict()}")
                else:
                    print("\n⚠ Failed to get status")

            except KeyboardInterrupt:
                print("\n\n🛑 Stopping monitoring loop...")
                raise
            except Exception as e:
                print(f"\n❌ Error in iteration {iteration}: {e}")

            # Wait 10 seconds before next iteration
            print(f"\n⏳ Waiting 10 seconds before next check...")
            time.sleep(10)

    except KeyboardInterrupt:
        print("\n✓ Gracefully shutting down...")
    finally:
        device.disconnect()

    print("\n" + "="*50 + "\n")