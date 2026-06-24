#!/usr/bin/env python3
"""
Maintenance reset.

Checks whether filter maintenance is required and, if so,
resets the maintenance flag on the device.

Usage:
    python3 maintenance.py --ip 192.168.1.100 --pin 1234
    python3 maintenance.py --ip 192.168.1.100 --pin 1234 --force
    python3 maintenance.py --ip 192.168.1.100 --pin 1234 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging

from open_pico_local_api import PicoClient, PicoDeviceError, PicoConnectionError, PicoTimeoutError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check and reset Pico device maintenance flag.")
    parser.add_argument("--ip",      required=True,       help="Device IP address")
    parser.add_argument("--pin",     required=True,       help="Device PIN")
    parser.add_argument("--force",   action="store_true", help="Reset even if maintenance flag is not set")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    async with PicoClient(ip=args.ip, pin=args.pin, verbose=args.verbose) as device:
        status = await device.get_status()
        maintenance = status.device_info.maintenance

        if maintenance is None:
            print("Maintenance status not available on this device.")
            return

        needs_reset = any(maintenance)
        print(f"Maintenance flags: {maintenance}")

        if not needs_reset and not args.force:
            print("✅ No maintenance required.")
            return

        if not needs_reset and args.force:
            print("No flag set, but --force was passed. Sending reset anyway…")
        else:
            print("🔧 Maintenance required. Resetting…")

        try:
            await device.reset_maintenance()
            print("✅ Maintenance reset successfully.")
        except PicoDeviceError as e:
            print(f"❌ Reset failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (PicoConnectionError, PicoTimeoutError) as e:
        print(f"Error: {e}")
