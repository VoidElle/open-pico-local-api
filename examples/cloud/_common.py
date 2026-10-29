"""Shared helpers for the cloud examples: import paths, credentials, logging."""

import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


def make_parser(description: str, device: bool = True) -> argparse.ArgumentParser:
    """Credentials come from flags or PICO_EMAIL / PICO_PASSWORD / PICO_SERIAL / PICO_PIN."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--email", default=os.environ.get("PICO_EMAIL"), help="Account email (or PICO_EMAIL)")
    p.add_argument("--password", default=os.environ.get("PICO_PASSWORD"), help="Account password (or PICO_PASSWORD)")
    if device:
        p.add_argument("--serial", default=os.environ.get("PICO_SERIAL"), help="Device serial (or PICO_SERIAL)")
        p.add_argument("--pin", default=os.environ.get("PICO_PIN"), help="Device PIN (or PICO_PIN)")
    p.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")
    return p


def parse(parser: argparse.ArgumentParser) -> argparse.Namespace:
    args = parser.parse_args()
    missing = [k for k in ("email", "password", "serial", "pin") if k in args and not getattr(args, k)]
    if missing:
        parser.error("missing: " + ", ".join("--" + m for m in missing))
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    return args


def run(main) -> None:
    import asyncio
    from open_pico_local_api import PicoDeviceError
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped.")
    except PicoDeviceError as e:  # auth, connection, timeout and device errors all derive from it
        print(f"Error: {type(e).__name__}: {e}")
