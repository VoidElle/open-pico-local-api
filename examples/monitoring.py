#!/usr/bin/env python3
"""
Device monitoring.

Continuously polls a Pico device and prints a status report.
Prints an alert if maintenance is required or errors are detected.

Usage:
    python3 monitoring.py --ip 192.168.1.100 --pin 1234
    python3 monitoring.py --ip 192.168.1.100 --pin 1234 --interval 10
    python3 monitoring.py --ip 192.168.1.100 --pin 1234 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging
from datetime import datetime

from open_pico_local_api import PicoClient, PicoConnectionError, PicoTimeoutError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuously monitor a Pico device.")
    parser.add_argument("--ip",       required=True,        help="Device IP address")
    parser.add_argument("--pin",      required=True,        help="Device PIN")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds (default: 30)")
    parser.add_argument("--verbose",  action="store_true",  help="Enable verbose debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    print(f"Monitoring {args.ip} every {args.interval}s. Press Ctrl+C to stop.\n")

    async with PicoClient(ip=args.ip, pin=args.pin, verbose=args.verbose) as device:
        while True:
            try:
                status = await device.get_status()
                now = datetime.now().strftime("%H:%M:%S")

                health = "✅ Healthy" if status.is_healthy else "⚠️  Issues"
                power  = "🟢 ON"     if status.is_on      else "🔴 OFF"
                night  = "🌙 Active" if status.operating.is_night_mode_active else "Inactive"

                print(f"[{now}]  {health}  {power}")
                print(f"  Mode    : {status.operating.mode.name}")
                print(f"  Fan     : {status.operating.speed}%")
                print(f"  Temp    : {status.sensors.temperature_celsius}°C")
                print(f"  Humidity: {status.sensors.humidity_percent}%")
                print(f"  CO₂     : {status.sensors.eco2} ppm")
                print(f"  Night   : {night}")
                print(f"  Uptime  : {status.system.uptime_days:.1f} days")

                if status.parameters.has_errors:
                    print(f"  ❌ Errors: {status.parameters.active_errors}")

                if status.device_info.maintenance and any(status.device_info.maintenance):
                    print("  🔧 Maintenance required — run maintenance.py to reset")

                print()

            except PicoTimeoutError:
                print(f"[{datetime.now().strftime('%H:%M:%S')}]  ⚠️  Timeout — retrying next interval\n")

            await asyncio.sleep(args.interval)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except PicoConnectionError as e:
        print(f"Connection error: {e}")
