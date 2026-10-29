#!/usr/bin/env python3
"""
All PICO devices of the account with ONE login (mirror of multi_device.py).

Devices come from the account; PINs are not stored in the cloud, so pass them:
a default PIN for all and/or per-serial overrides.

Usage:
    python3 multi_device_cloud.py --pin 1234
    python3 multi_device_cloud.py --pin 1234 --pins SER111=4321 SER222=1111
    python3 multi_device_cloud.py --pin 1234 --set-mode 1 --turn on
"""

import asyncio

from _common import make_parser, parse, run

from open_pico_local_api import DeviceModeEnum, PicoDeviceError
from open_pico_local_api.cloud import PicoCloudClient

PICO_TYPE = 1


async def main() -> None:
    parser = make_parser("Control every PICO of the account.", device=False)
    parser.add_argument("--pin", default=None, help="Default PIN for all devices")
    parser.add_argument("--pins", nargs="*", default=[], metavar="SERIAL=PIN", help="Per-device PIN overrides")
    parser.add_argument("--set-mode", type=int, help="Operating mode (1..12) to apply to every device")
    parser.add_argument("--turn", choices=["on", "off"], help="Power state to apply to every device")
    args = parse(parser)
    pins = dict(p.split("=", 1) for p in args.pins)

    async with PicoCloudClient(args.email, args.password, verbose=args.verbose) as cloud:
        devices = [d for d in await cloud.get_devices() if d.get("LVDV_Type") == PICO_TYPE]
        print(f"{len(devices)} PICO device(s)\n")

        # One session = one rolling-token counter, so devices are handled one after the other.
        for d in devices:
            serial = d["Serial"].upper()
            pin = pins.get(serial, args.pin)
            label = f"{d.get('PlantName')}/{d.get('Name') or serial}"
            if not pin:
                print(f"  {label}: skipped (no PIN)")
                continue
            cloud.use_device(serial, pin, d.get("Name") or "")
            try:
                if args.turn:
                    await (cloud.turn_on() if args.turn == "on" else cloud.turn_off())
                if args.set_mode:
                    await cloud.change_operating_mode(DeviceModeEnum(args.set_mode))
                if args.turn or args.set_mode:
                    await asyncio.sleep(6)
                s = await cloud.get_status()
                print(f"  {label}: {'ON' if s.is_on else 'OFF'} {s.operating.mode.name} "
                      f"{s.sensors.temperature_celsius}°C {s.sensors.humidity_percent}%")
            except PicoDeviceError as e:
                print(f"  {label}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    run(main)
