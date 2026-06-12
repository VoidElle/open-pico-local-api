"""
Pico Device Auto-Discovery

Discovers Tecnosystemi Pico devices on the local network via subnet scan.

All traffic goes through SharedTransportManager (port 40069) because Pico
devices are hardcoded by the manufacturer to respond only to that port.
"""

import asyncio
import json
import logging
from ipaddress import ip_network, IPv4Network
from typing import Any, Dict, List, Set

from open_pico_local_api.shared_transport_manager import SharedTransportManager

_LOGGER = logging.getLogger(__name__)

_DISCOVERY_IDP = 0  # IDP 0 is never allocated to any PicoClient range (ranges start at 1)
_PROBE_CMD = "stato_sync"


def _build_probe(pin: str) -> bytes:
    return json.dumps({
        "cmd": _PROBE_CMD,
        "frm": "app",
        "pin": pin,
        "idp": _DISCOVERY_IDP,
    }).encode("utf-8")


def _is_valid_pico_response(response: Dict[str, Any]) -> bool:
    """Check if a UDP response looks like a Pico device status reply."""
    return (
        isinstance(response, dict)
        and response.get("idp") == _DISCOVERY_IDP
        and "fw_ver" in response
        and "mod" in response
    )


class PicoAutoDiscovery:
    """
    Discovers Pico devices on the local network.

    Uses the :class:`SharedTransportManager` so all traffic flows through
    port 40069, which is the only port Pico devices will respond to.

    Usage::

        ips = await PicoAutoDiscovery.discover(pin="1234", subnet="192.168.1.0/24")
        # ["192.168.1.42", "192.168.1.55"]
    """

    @staticmethod
    async def discover(
        pin: str,
        subnet: str,
        device_port: int = 40070,
        local_port: int = 40069,
        scan_timeout: float = 2.0,
        max_concurrent: int = 50,
        verbose: bool = False,
    ) -> List[str]:
        """
        Discover Pico devices on the local network via subnet scan.

        Probes every host in *subnet* concurrently and collects replies on
        port 40069 via the shared transport.

        Args:
            pin: Device PIN used for the probe command.
            subnet: CIDR notation for the scan (e.g. ``"192.168.1.0/24"``).
            device_port: UDP port Pico devices listen on (default 40070).
            local_port: Local port to bind the shared transport on (default 40069).
            scan_timeout: Per-IP timeout during subnet scan.
            max_concurrent: Maximum simultaneous probes during subnet scan.
            verbose: Enable debug logging.

        Returns:
            Sorted list of IP address strings of discovered devices.
        """
        probe = _build_probe(pin)
        discovered: Set[str] = set()

        manager = await SharedTransportManager.get_instance()
        if not manager.is_initialized:
            await manager.initialize(local_port=local_port, verbose=verbose)

        unmatched_queue: asyncio.Queue = asyncio.Queue()
        manager.set_unmatched_queue(unmatched_queue)

        try:
            await PicoAutoDiscovery._subnet_scan(
                probe=probe,
                manager=manager,
                unmatched_queue=unmatched_queue,
                discovered=discovered,
                subnet=subnet,
                device_port=device_port,
                timeout=scan_timeout,
                max_concurrent=max_concurrent,
                verbose=verbose,
            )
            return sorted(discovered)
        finally:
            manager.clear_unmatched_queue()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _collect_responses(
        unmatched_queue: asyncio.Queue,
        discovered: Set[str],
        duration: float,
        verbose: bool,
    ) -> None:
        """Drain *unmatched_queue* for *duration* seconds, collecting valid Pico IPs."""
        loop = asyncio.get_running_loop()
        end_time = loop.time() + duration
        while True:
            remaining = end_time - loop.time()
            if remaining <= 0:
                break
            try:
                response, addr = await asyncio.wait_for(
                    unmatched_queue.get(), timeout=min(remaining, 0.5)
                )
                if _is_valid_pico_response(response):
                    ip = addr[0]
                    discovered.add(ip)
                    if verbose:
                        _LOGGER.debug(f"✓ Discovered Pico at {ip} (fw: {response.get('fw_ver', '?')})")
            except asyncio.TimeoutError:
                continue

    @staticmethod
    async def _subnet_scan(
        probe: bytes,
        manager: SharedTransportManager,
        unmatched_queue: asyncio.Queue,
        discovered: Set[str],
        subnet: str,
        device_port: int,
        timeout: float,
        max_concurrent: int,
        verbose: bool,
    ) -> None:
        try:
            network = ip_network(subnet, strict=False)
        except ValueError as e:
            raise ValueError(f"Invalid subnet '{subnet}': {e}")

        if not isinstance(network, IPv4Network):
            raise ValueError(f"Only IPv4 subnets are supported, got: {subnet}")

        hosts = list(network.hosts())
        semaphore = asyncio.Semaphore(max_concurrent)

        async def probe_host(ip_str: str) -> None:
            async with semaphore:
                manager.send_raw(probe, (ip_str, device_port))

        # Start collection concurrently with probing so responses from fast-responding
        # devices are captured even before all probes have been sent.
        collect_task = asyncio.create_task(
            PicoAutoDiscovery._collect_responses(unmatched_queue, discovered, timeout, verbose)
        )
        try:
            await asyncio.gather(*[probe_host(str(ip)) for ip in hosts])
            await collect_task
        except BaseException:
            collect_task.cancel()
            raise

