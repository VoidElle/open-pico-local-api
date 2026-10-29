#!/usr/bin/env python3
"""
Monitor a device: poll like the official app (5 s) and print only when something changes.
Survives transient cloud errors (timeouts, 5xx-like non-JSON replies) and relogs in by itself.

Usage:
    python3 monitor_cloud.py
    python3 monitor_cloud.py --interval 15
"""

import asyncio
import time

from _common import make_parser, parse, run

from open_pico_local_api import PicoDeviceError
from open_pico_local_api.cloud import PicoCloudClient, PicoAuthError


def snapshot(s) -> dict:
    return {"power": "ON" if s.is_on else "OFF", "mode": s.operating.mode.name, "fan": s.operating.speed,
            "temp": s.sensors.temperature_celsius, "hum": s.sensors.humidity_percent,
            "co2": s.sensors.eco2, "errors": bool(s.parameters.has_errors)}


async def main() -> None:
    parser = make_parser("Monitor a Pico over the cloud.")
    parser.add_argument("--interval", type=float, default=5, help="Poll period in seconds (default 5, as the app)")
    args = parse(parser)

    async with PicoCloudClient(args.email, args.password, args.serial, args.pin,
                               retry_attempts=1, verbose=args.verbose) as pico:
        last: dict = {}
        failures = 0
        print("Monitoring. Ctrl+C to stop.")
        while True:
            try:
                snap = snapshot(await pico.get_status())
                failures = 0
                changes = {k: (last.get(k), v) for k, v in snap.items() if last.get(k) != v}
                if changes:
                    stamp = time.strftime("%H:%M:%S")
                    print(f"[{stamp}] " + ", ".join(f"{k}: {a} -> {b}" if last else f"{k}={b}"
                                                    for k, (a, b) in changes.items()))
                    last = snap
            except PicoAuthError:
                raise  # bad credentials / blocked account: do not hammer the server
            except PicoDeviceError as e:
                failures += 1
                print(f"[{time.strftime('%H:%M:%S')}] poll failed ({failures}): {e}")
            # linear backoff on repeated failures, capped at 60 s
            await asyncio.sleep(min(args.interval * (1 + failures), 60))


if __name__ == "__main__":
    run(main)
