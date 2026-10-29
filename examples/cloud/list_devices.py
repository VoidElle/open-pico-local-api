#!/usr/bin/env python3
"""
List the plants and devices of the account.

The cloud does not return PINs: you need the PIN (printed on the device / set in the app)
to read or control a device.

Usage:
    python3 list_devices.py --email me@x.com --password '...'
    python3 list_devices.py --email me@x.com --password '...' --json
"""

import json

from _common import make_parser, parse, run

from open_pico_local_api.cloud import PicoCloudClient

DEVICE_TYPES = {1: "PICO"}  # other values are VMC / SeiX / control units


async def main() -> None:
    parser = make_parser("List account plants and devices.", device=False)
    parser.add_argument("--json", action="store_true", help="Print the raw plants JSON")
    args = parse(parser)

    async with PicoCloudClient(args.email, args.password, verbose=args.verbose) as cloud:
        plants = await cloud.get_plants()
        if args.json:
            print(json.dumps(plants, indent=2))
            return
        for plant in plants:
            print(f"Plant: {plant.get('LVPL_Name')} (id {plant.get('LVPL_Id')})")
            for d in plant.get("ListDevices") or []:
                kind = DEVICE_TYPES.get(d.get("LVDV_Type"), f"type {d.get('LVDV_Type')}")
                print(f"  - {d.get('Serial'):<14} {kind:<8} name={d.get('Name')!r} "
                      f"fw={d.get('FWVer')} errors={d.get('NUM_ERROR')}")
        if not plants:
            print("No plants on this account.")


if __name__ == "__main__":
    run(main)
