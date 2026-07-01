#!/usr/bin/env python3
"""
IDP bruteforce diagnostic.

When a Pico stops responding, its internal IDP counter may have drifted far
outside the range the client expects. The normal retry logic only probes 5
consecutive IDP values, so it cannot recover from a large drift. This tool
sweeps a range of IDP values to find the one the device actually responds to.

If a responsive IDP is found, the client realigns its counter automatically and
a follow-up status read is attempted to confirm the device is talking again.

Usage:
    python3 idp_diagnostic.py --ip 192.168.1.100 --pin 1234
    python3 idp_diagnostic.py --ip 192.168.1.100 --pin 1234 --start 1 --end 500
    python3 idp_diagnostic.py --ip 192.168.1.100 --pin 1234 --timeout 0.5 --all
    python3 idp_diagnostic.py --ip 192.168.1.100 --pin 1234 --verbose
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncio
import argparse
import logging

from open_pico_local_api import PicoClient, PicoConnectionError, PicoTimeoutError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bruteforce a Pico device's IDP to diagnose lost communication.")
    parser.add_argument("--ip",      required=True,       help="Device IP address")
    parser.add_argument("--pin",     required=True,       help="Device PIN")
    parser.add_argument("--start",   type=int, default=None, help="First IDP to probe (default: device range start)")
    parser.add_argument("--end",     type=int, default=None, help="Last IDP to probe (default: device range end)")
    parser.add_argument("--timeout", type=float, default=0.3, help="Seconds to wait per IDP (default: 0.3)")
    parser.add_argument("--all",     action="store_true", help="Probe the whole range instead of stopping at the first hit")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")

    async with PicoClient(ip=args.ip, pin=args.pin, verbose=args.verbose) as device:
        print("Connected. Starting IDP bruteforce…")
        print("(Tip: narrow the range with --start/--end for a faster sweep.)\n")

        result = await device.bruteforce_idp(
            start=args.start,
            end=args.end,
            per_idp_timeout=args.timeout,
            stop_on_first=not args.all,
        )

        print(f"Probed {result['probed']} IDP value(s).")

        if result["found"] is None:
            print("❌ No response on any probed IDP.")
            print("   The device may be offline, on a different IP/port, using a different PIN,")
            print("   or the responsive IDP is outside the probed range (try widening --start/--end).")
            return

        print(f"✅ Device responded to IDP {result['found']}.")
        if args.all and len(result["responsive_idps"]) > 1:
            print(f"   All responsive IDPs: {result['responsive_idps']}")

        print("\nClient counter realigned. Confirming with a status read…")
        try:
            status = await device.get_status()
            print(f"  Power   : {'ON' if status.is_on else 'OFF'}")
            print(f"  Mode    : {status.operating.mode.name}")
            print("✅ Communication restored.")
        except PicoTimeoutError:
            print("⚠ Bruteforce found a responsive IDP but the follow-up status read timed out.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (PicoConnectionError, PicoTimeoutError) as e:
        print(f"Error: {e}")
