#!/usr/bin/env python3
"""
Adaptive climate control.

Reads current sensor values and automatically picks the best operating
mode and fan speed for the conditions.

  - Humidity > 70%  → HUMIDITY_EXTRACTION, high fan
  - CO₂ > 1000 ppm → CO2_RECOVERY, medium-high fan
  - Otherwise       → HEAT_RECOVERY, comfortable fan

Usage:
    python3 adaptive_climate.py --ip 192.168.1.100 --pin 1234
    python3 adaptive_climate.py --ip 192.168.1.100 --pin 1234 --loop --interval 60
    python3 adaptive_climate.py --ip 192.168.1.100 --pin 1234 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging

from open_pico_local_api import (
    PicoClient,
    DeviceModeEnum,
    NotSupportedError,
    PicoConnectionError,
    PicoTimeoutError,
)

HIGH_HUMIDITY_THRESHOLD = 70   # %
HIGH_CO2_THRESHOLD      = 1000 # ppm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Adaptive climate control for a Pico device.")
    parser.add_argument("--ip",       required=True,          help="Device IP address")
    parser.add_argument("--pin",      required=True,          help="Device PIN")
    parser.add_argument("--loop",     action="store_true",    help="Keep running and re-evaluate periodically")
    parser.add_argument("--interval", type=int, default=60,   help="Re-evaluation interval in seconds (default: 60)")
    parser.add_argument("--verbose",  action="store_true",    help="Enable verbose debug logging")
    return parser.parse_args()


async def apply_adaptive_control(device: PicoClient) -> None:
    status = await device.get_status()
    humidity = status.sensors.humidity_percent
    co2      = status.sensors.eco2

    print(f"  Sensors → humidity={humidity}%  CO₂={co2} ppm")

    if humidity > HIGH_HUMIDITY_THRESHOLD:
        print(f"  ⚠️  High humidity ({humidity}%) — switching to HUMIDITY_EXTRACTION at 80%")
        await device.turn_on()
        await device.change_operating_mode(DeviceModeEnum.HUMIDITY_EXTRACTION)
        try:
            await device.change_fan_speed(80)
        except NotSupportedError:
            pass  # mode doesn't support custom fan speed
    elif co2 > HIGH_CO2_THRESHOLD:
        print(f"  ⚠️  High CO₂ ({co2} ppm) — switching to CO2_RECOVERY at 70%")
        await device.turn_on()
        await device.change_operating_mode(DeviceModeEnum.CO2_RECOVERY)
        try:
            await device.change_fan_speed(70)
        except NotSupportedError:
            pass
    else:
        print("  ✅  Conditions normal — switching to HEAT_RECOVERY at 50%")
        await device.turn_on()
        await device.change_operating_mode(DeviceModeEnum.HEAT_RECOVERY)
        try:
            await device.change_fan_speed(50)
        except NotSupportedError:
            pass


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    async with PicoClient(ip=args.ip, pin=args.pin, verbose=args.verbose) as device:
        if args.loop:
            print(f"Running adaptive control loop every {args.interval}s. Press Ctrl+C to stop.\n")
            while True:
                print("Evaluating…")
                await apply_adaptive_control(device)
                await asyncio.sleep(args.interval)
        else:
            await apply_adaptive_control(device)
            print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except (PicoConnectionError, PicoTimeoutError) as e:
        print(f"Error: {e}")
