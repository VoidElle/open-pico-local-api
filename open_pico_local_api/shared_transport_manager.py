"""
Shared UDP Transport Manager for multiple Pico devices

Allows multiple PicoClient instances to share a single UDP socket by routing
responses based on IDP ranges assigned to each device.
"""

import bisect
import logging
import asyncio
import inspect
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from open_pico_local_api.exceptions.pico_connection_error import PicoConnectionError

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceRegistration:
    """Registration info for a device"""
    device_id: str
    ip: str
    port: int
    response_queue: asyncio.Queue
    event_callbacks: Dict
    idp_range_start: int
    idp_range_size: int  # Number of IDPs allocated to this device


class SharedPicoProtocol(asyncio.DatagramProtocol):
    """Shared protocol that routes responses to correct device clients"""

    def __init__(self, transport_manager, verbose: bool = False):
        self.transport_manager = transport_manager
        self.verbose = verbose
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport_manager._transport = transport

    def datagram_received(self, data, addr):
        try:
            response = json.loads(data.decode('utf-8'))
            _LOGGER.debug(response)

            if self.verbose:
                idp = response.get('idp', '?')
                cmd = response.get('cmd', 'unknown')
                _LOGGER.debug(f"← RECV from {addr}: cmd={cmd}, idp={idp}")

            # Route response to correct device based on IDP
            idp = response.get('idp')
            if idp is not None:
                device_id = self.transport_manager.find_device_by_idp(idp)
                if device_id:
                    registration = self.transport_manager.get_device_registration(device_id)
                    # Put in device's response queue
                    registration.response_queue.put_nowait((response, addr))

                    # Trigger callbacks if any
                    cmd = response.get('cmd', '')
                    if cmd in registration.event_callbacks:
                        callback = registration.event_callbacks[cmd]
                        asyncio.create_task(self._run_callback(callback, response))
                else:
                    unmatched_queue = self.transport_manager.unmatched_queue
                    if unmatched_queue is not None:
                        unmatched_queue.put_nowait((response, addr))
                    elif self.verbose:
                        _LOGGER.debug(f"⚠ No device found for IDP {idp}")
            else:
                if self.verbose:
                    _LOGGER.debug(f"⚠ Response without IDP: {response}")

        except json.JSONDecodeError as e:
            if self.verbose:
                _LOGGER.warning(f"⚠ JSON decode error: {e}")
        except Exception as e:
            if self.verbose:
                _LOGGER.warning(f"⚠ Error processing datagram: {e}")

    @staticmethod
    async def _run_callback(callback, response):
        """Run callback in async context"""
        try:
            if inspect.iscoroutinefunction(callback):
                await callback(response)
            else:
                callback(response)
        except Exception as e:
            _LOGGER.warning(f"⚠ Callback error: {e}")

    def error_received(self, exc):
        if self.verbose:
            _LOGGER.warning(f"⚠ Protocol error: {exc}")

    def connection_lost(self, exc):
        if self.verbose and exc:
            _LOGGER.warning(f"⚠ Connection lost: {exc}")


class SharedTransportManager:
    """
    Singleton manager for shared UDP transport across multiple Pico devices.

    Usage:
        manager = await SharedTransportManager.get_instance()
        await manager.initialize(local_port=40069)

        # Register devices
        device1_queue = asyncio.Queue()
        await manager.register_device("device1", "192.168.1.100", 40070, device1_queue)

        device2_queue = asyncio.Queue()
        await manager.register_device("device2", "192.168.1.101", 40070, device2_queue)
    """

    _instance = None
    _lock: asyncio.Lock = asyncio.Lock()  # Class-level lock — safe in Python 3.11+ (no event-loop binding)

    def __init__(self):
        if SharedTransportManager._instance is not None:
            raise RuntimeError("Use get_instance() instead")

        self._transport = None
        self._protocol = None
        self._devices: Dict[str, DeviceRegistration] = {}
        self._local_port = None
        self._verbose = False
        self._initialized = False
        self._next_idp_range = 1  # Start IDP allocation from 1
        self._idp_range_size = 10000  # Allocate 10k IDPs per device
        self._init_lock = asyncio.Lock()  # Lock for thread-safe initialization and registration
        self._unmatched_queue: Optional[asyncio.Queue] = None  # Receives packets with no registered IDP owner

        # O(log n) IDP routing structures
        self._idp_sorted_starts: List[int] = []          # Sorted range-start values
        self._idp_start_to_device: Dict[int, str] = {}   # range_start → device_id

    @classmethod
    async def get_instance(cls):
        """Get or create singleton instance (thread-safe)"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    async def initialize(self, local_port: int = 40069, verbose: bool = False):
        """
        Initialize the shared UDP transport

        Args:
            local_port: Local port to bind to
            verbose: Enable verbose logging
        """
        # Thread-safe initialization check
        async with self._init_lock:
            if self._initialized:
                if verbose:
                    _LOGGER.debug(f"ℹ Shared transport already initialized on port {self._local_port}")
                return

            self._local_port = local_port
            self._verbose = verbose

            try:
                loop = asyncio.get_running_loop()
                self._transport, self._protocol = await loop.create_datagram_endpoint(
                    lambda: SharedPicoProtocol(self, verbose),
                    local_addr=("0.0.0.0", local_port)
                )
                self._initialized = True

                if verbose:
                    _LOGGER.debug(f"✓ Shared transport initialized on port {local_port}")

            except Exception as e:
                raise PicoConnectionError(f"Failed to initialize shared transport: {e}")

    async def register_device(
        self,
        device_id: str,
        ip: str,
        port: int,
        response_queue: asyncio.Queue,
        event_callbacks: Optional[Dict] = None
    ) -> Tuple[int, int]:
        """
        Register a device to use the shared transport

        Args:
            device_id: Unique identifier for the device
            ip: Device IP address
            port: Device port
            response_queue: Queue to receive responses
            event_callbacks: Optional event callbacks

        Returns:
            Tuple of (idp_range_start, idp_range_size)
        """
        if not self._initialized:
            raise RuntimeError("Transport not initialized. Call initialize() first.")

        async with self._init_lock:
            if device_id in self._devices:
                # Already registered — update the response queue and callbacks so that a
                # reconnected client (new PicoClient instance, new asyncio.Queue) receives
                # its responses instead of the old abandoned queue.
                reg = self._devices[device_id]
                reg.response_queue = response_queue
                if event_callbacks:
                    reg.event_callbacks = event_callbacks
                return reg.idp_range_start, reg.idp_range_size

            # Allocate IDP range for this device (protected by lock to prevent races)
            idp_range_start = self._next_idp_range
            self._next_idp_range += self._idp_range_size

            registration = DeviceRegistration(
                device_id=device_id,
                ip=ip,
                port=port,
                response_queue=response_queue,
                event_callbacks=event_callbacks or {},
                idp_range_start=idp_range_start,
                idp_range_size=self._idp_range_size
            )

            self._devices[device_id] = registration
            bisect.insort(self._idp_sorted_starts, idp_range_start)
            self._idp_start_to_device[idp_range_start] = device_id

        if self._verbose:
            _LOGGER.debug(f"✓ Registered device '{device_id}' at {ip}:{port}")
            _LOGGER.debug(f"  IDP range: {idp_range_start} - {idp_range_start + self._idp_range_size - 1}")

        return idp_range_start, self._idp_range_size

    async def unregister_device(self, device_id: str):
        """Unregister a device"""
        if device_id in self._devices:
            reg = self._devices.pop(device_id)
            start = reg.idp_range_start
            self._idp_start_to_device.pop(start, None)
            idx = bisect.bisect_left(self._idp_sorted_starts, start)
            if idx < len(self._idp_sorted_starts) and self._idp_sorted_starts[idx] == start:
                self._idp_sorted_starts.pop(idx)
            if self._verbose:
                _LOGGER.debug(f"✓ Unregistered device '{device_id}'")

    def find_device_by_idp(self, idp: int) -> Optional[str]:
        """Find which device an IDP belongs to — O(log n) via bisect."""
        if not self._idp_sorted_starts:
            return None
        idx = bisect.bisect_right(self._idp_sorted_starts, idp) - 1
        if idx < 0:
            return None
        start = self._idp_sorted_starts[idx]
        device_id = self._idp_start_to_device.get(start)
        if device_id is None:
            return None
        reg = self._devices[device_id]
        if idp < start + reg.idp_range_size:
            return device_id
        return None

    async def send_to_device(self, device_id: str, data: bytes):
        """Send data to a specific device"""
        if device_id not in self._devices:
            raise ValueError(f"Device '{device_id}' not registered")

        registration = self._devices[device_id]
        self._transport.sendto(data, (registration.ip, registration.port))

        if self._verbose:
            _LOGGER.debug(f"→ SENT to {device_id} ({registration.ip}:{registration.port})")

    def send_raw(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Send raw bytes to an arbitrary address (used by discovery)."""
        if not self._initialized:
            raise RuntimeError("Transport not initialized.")
        self._transport.sendto(data, addr)

    def get_device_registration(self, device_id: str) -> Optional['DeviceRegistration']:
        """Return the registration for *device_id*, or None if not found."""
        return self._devices.get(device_id)

    @property
    def unmatched_queue(self) -> Optional[asyncio.Queue]:
        """Queue that receives packets with no registered IDP owner."""
        return self._unmatched_queue

    def set_unmatched_queue(self, queue: asyncio.Queue) -> None:
        """Route packets with no registered IDP owner into *queue* (used by discovery)."""
        self._unmatched_queue = queue

    def clear_unmatched_queue(self) -> None:
        """Stop routing unmatched packets."""
        self._unmatched_queue = None

    async def shutdown(self):
        """Shutdown the shared transport"""
        if self._transport:
            self._transport.close()
            self._transport = None
            self._initialized = False
            self._devices.clear()
            self._idp_sorted_starts.clear()
            self._idp_start_to_device.clear()
            self._next_idp_range = 1
            self._unmatched_queue = None

            # Reset singleton so a fresh instance can be created after re-initialization
            SharedTransportManager._instance = None

            if self._verbose:
                _LOGGER.debug("✓ Shared transport closed")

    @property
    def is_initialized(self) -> bool:
        """Check if transport is initialized"""
        return self._initialized