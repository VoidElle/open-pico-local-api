#!/usr/bin/env python3
"""
Basic cloud control (mirror of examples/basic_control.py of open-pico-local-api).

Usage:
    python3 basic_cloud.py --email me@x.com --password '...' --serial SER123 --pin 1234
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import argparse
import asyncio
import logging

from open_pico_local_api import DeviceModeEnum
from open_pico_local_api.cloud import PicoCloudClient


async def main() -> None:
    p = argparse.ArgumentParser(description="Basic Pico cloud control.")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--serial", required=True)
    p.add_argument("--pin", required=True)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    async with PicoCloudClient(args.email, args.password, args.serial, args.pin, verbose=args.verbose) as device:
        status = await device.get_status()
        print(f"Power {'ON' if status.is_on else 'OFF'} | mode {status.operating.mode.name} | "
              f"{status.sensors.temperature_celsius}°C | {status.sensors.humidity_percent}%")
        await device.turn_on()
        await device.change_operating_mode(DeviceModeEnum.HEAT_RECOVERY)
        await asyncio.sleep(6)  # command is async on the backend; next poll shows it
        print("Mode now:", (await device.get_status()).operating.mode.name)


if __name__ == "__main__":
    asyncio.run(main())
