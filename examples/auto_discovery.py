#!/usr/bin/env python3
"""
Auto-discovery then connect.

Scans the subnet for Pico devices, prints what it finds,
then connects to each discovered device and reads its status.

Usage:
    python3 auto_discovery.py --subnet 192.168.1.0/24 --pin 1234
    python3 auto_discovery.py --subnet 192.168.1.0/24 --pin 1234 --timeout 5.0
"""

import asyncio
import argparse

from open_pico_local_api import PicoAutoDiscovery, PicoClient, PicoConnectionError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Pico devices then read their status.")
    parser.add_argument("--subnet",  required=True, help="CIDR subnet to scan (e.g. 192.168.1.0/24)")
    parser.add_argument("--pin",     required=True, help="Device PIN (all devices must share the same PIN)")
    parser.add_argument("--timeout", type=float, default=2.0, help="Scan timeout in seconds (default: 2.0)")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    print(f"Scanning {args.subnet}…")
    ips = await PicoAutoDiscovery.discover(
        pin=args.pin,
        subnet=args.subnet,
        scan_timeout=args.timeout,
    )

    if not ips:
        print("No Pico devices found.")
        return

    print(f"Found {len(ips)} device(s): {', '.join(ips)}\n")

    for ip in ips:
        try:
            async with PicoClient(ip=ip, pin=args.pin) as device:
                status = await device.get_status()
                print(f"[{ip}]")
                print(f"  Power   : {'ON' if status.is_on else 'OFF'}")
                print(f"  Mode    : {status.operating.mode.name}")
                print(f"  Temp    : {status.sensors.temperature_celsius}°C")
                print(f"  Humidity: {status.sensors.humidity_percent}%")
                print(f"  Fan     : {status.operating.speed}%")
                print(f"  Healthy : {'✅' if status.is_healthy else '⚠️'}")
                print()
        except PicoConnectionError as e:
            print(f"[{ip}] Connection failed: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
