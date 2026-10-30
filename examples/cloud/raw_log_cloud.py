#!/usr/bin/env python3
"""
Log the raw cloud traffic: every request we send and every reply we get.

PicoCloudClient(verbose=True) emits both at DEBUG level on the
`open_pico_local_api.cloud.pico_cloud_client` logger:
    → METHOD /path {request body}
    ← HTTP_STATUS {raw reply text}
The login password is already encrypted in the body; the Token header is never logged.

Usage:
    python3 raw_log_cloud.py --email me@x.com --password '...' --serial SER123 --pin 1234 [--file traffic.log]
"""

import logging

import _common
from open_pico_local_api.cloud import PicoCloudClient


async def main() -> None:
    p = _common.make_parser("Log raw Pico cloud requests/replies.")
    p.add_argument("--file", help="Also write the raw traffic to this file")
    args = _common.parse(p)

    # Only the cloud client logger: keep other libraries quiet.
    log = logging.getLogger("open_pico_local_api.cloud.pico_cloud_client")
    log.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    if args.file:
        handler = logging.FileHandler(args.file)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    log.addHandler(handler)
    log.propagate = False

    async with PicoCloudClient(args.email, args.password, args.serial, args.pin, verbose=True) as device:
        await device.get_status()  # login + GetPICOState both get logged


if __name__ == "__main__":
    _common.run(main)
