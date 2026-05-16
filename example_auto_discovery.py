#!/usr/bin/env python3
"""
Example script to discover Pico HVAC devices on the local network.

Usage:
    python3 example_auto_discovery.py --subnet 192.168.1.0/24 --pin 1234
    python3 example_auto_discovery.py --subnet 192.168.1.0/24 --pin 1234 --timeout 5.0 --verbose
"""

import asyncio
import argparse
import logging

from open_pico_local_api import PicoAutoDiscovery


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Pico HVAC devices on the local network.")
    parser.add_argument("--subnet",  required=True, help="Subnet to scan in CIDR notation (e.g. 192.168.1.0/24)")
    parser.add_argument("--pin",     required=True, help="Device PIN")
    parser.add_argument("--timeout", type=float, default=2.0, help="Per-scan timeout in seconds (default: 2.0)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    print(f"Scanning {args.subnet} …")

    devices = await PicoAutoDiscovery.discover(
        pin=args.pin,
        subnet=args.subnet,
        scan_timeout=args.timeout,
        verbose=args.verbose,
    )

    if not devices:
        print("No Pico devices found.")
        return

    print(f"\nFound {len(devices)} device(s):")
    for ip in devices:
        print(f"  • {ip}")


if __name__ == "__main__":
    asyncio.run(main())
