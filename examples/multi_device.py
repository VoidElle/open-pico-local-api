#!/usr/bin/env python3
"""
Multi-device control.

Controls multiple Pico devices concurrently over a shared UDP transport.
Connects all devices at once, reads their status in parallel, and sets
a uniform mode across all of them.

Usage:
    python3 multi_device.py --pin 1234 --ips 192.168.1.100 192.168.1.101 192.168.1.102
    python3 multi_device.py --pin 1234 --ips 192.168.1.100 192.168.1.101 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging

from open_pico_local_api import PicoClient, DeviceModeEnum, PicoConnectionError, PicoTimeoutError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Control multiple Pico devices concurrently.")
    parser.add_argument("--pin",     required=True,        help="Shared device PIN")
    parser.add_argument("--ips",     required=True, nargs="+", help="Device IP addresses")
    parser.add_argument("--verbose", action="store_true",  help="Enable verbose debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    devices = [
        PicoClient(ip=ip, pin=args.pin, device_id=f"device_{i}", verbose=args.verbose)
        for i, ip in enumerate(args.ips)
    ]

    async with asyncio.TaskGroup() as tg:
        for device in devices:
            tg.create_task(device.connect())

    print(f"Connected to {len(devices)} device(s).\n")

    try:
        # Read all statuses in parallel
        statuses = await asyncio.gather(*[d.get_status() for d in devices])

        print("Current status:")
        for device, status in zip(devices, statuses):
            print(f"  [{device.device_id}]  {device.ip}  "
                  f"{'ON' if status.is_on else 'OFF'}  "
                  f"{status.operating.mode.name}  "
                  f"{status.sensors.temperature_celsius}°C  "
                  f"{status.sensors.humidity_percent}%")

        # Turn all on and set the same mode concurrently
        print("\nTurning all ON and setting HEAT_RECOVERY mode…")
        await asyncio.gather(*[d.turn_on() for d in devices])
        await asyncio.gather(*[d.change_operating_mode(DeviceModeEnum.HEAT_RECOVERY) for d in devices])
        print("Done.")

    finally:
        await asyncio.gather(*[d.disconnect() for d in devices])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except* (PicoConnectionError, PicoTimeoutError) as eg:
        for e in eg.exceptions:
            print(f"Error: {e}")
