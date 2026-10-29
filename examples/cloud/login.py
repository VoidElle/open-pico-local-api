#!/usr/bin/env python3
"""
Login only: check that the credentials work and show what the account returns.

Usage:
    python3 login.py --email me@x.com --password '...'
    PICO_EMAIL=me@x.com PICO_PASSWORD=... python3 login.py
"""

from _common import make_parser, parse, run

from open_pico_local_api.cloud import PicoCloudClient


async def main() -> None:
    args = parse(make_parser("Login to the Pico cloud.", device=False))
    async with PicoCloudClient(args.email, args.password, verbose=args.verbose) as cloud:
        print("Login OK.")
        print(f"  Plants : {len(cloud.plants)}")
        print(f"  Devices: {sum(len(p.get('ListDevices') or []) for p in cloud.plants)}")


if __name__ == "__main__":
    run(main)
