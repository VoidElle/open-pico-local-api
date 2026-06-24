#!/usr/bin/env python3
"""
Basic device control.

Connects to a single Pico device, reads its current status,
turns it on, sets the operating mode, and disconnects.

Usage:
    python3 basic_control.py --ip 192.168.1.100 --pin 1234
    python3 basic_control.py --ip 192.168.1.100 --pin 1234 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging

from open_pico_local_api import PicoClient, DeviceModeEnum, PicoConnectionError, PicoTimeoutError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Basic Pico device control.")
    parser.add_argument("--ip",      required=True,       help="Device IP address")
    parser.add_argument("--pin",     required=True,       help="Device PIN")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    async with PicoClient(ip=args.ip, pin=args.pin, device_id="main", verbose=args.verbose) as device:
        print("Connected.")

        status = await device.get_status()
        print(f"  Power   : {'ON' if status.is_on else 'OFF'}")
        print(f"  Mode    : {status.operating.mode.name}")
        print(f"  Temp    : {status.sensors.temperature_celsius}°C")
        print(f"  Humidity: {status.sensors.humidity_percent}%")
        print(f"  Fan     : {status.operating.speed}%")

        print("\nTurning on and switching to HEAT_RECOVERY mode…")
        await device.turn_on()
        await device.change_operating_mode(DeviceModeEnum.HEAT_RECOVERY)

        status = await device.get_status()
        print(f"  Mode is now: {status.operating.mode.name}")
        print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (PicoConnectionError, PicoTimeoutError) as e:
        print(f"Error: {e}")
