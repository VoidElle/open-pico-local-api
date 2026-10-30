#!/usr/bin/env python3
"""
Adaptive climate control over the cloud (mirror of adaptive_climate.py).

  - Humidity > 70%  -> HUMIDITY_EXTRACTION, fan 80
  - CO2 > 1000 ppm  -> CO2_RECOVERY, fan 70
  - Otherwise       -> HEAT_RECOVERY, fan 50

Unlike the local version it only sends commands when the target mode/state differs from the
device's current one, because every cloud command is a full HTTPS round trip and the
backend applies it asynchronously.

Usage:
    python3 adaptive_cloud.py --loop --interval 120
"""

import asyncio

from _common import make_parser, parse, run

from open_pico_local_api import DeviceModeEnum, NotSupportedError
from open_pico_local_api.cloud import PicoCloudClient

HIGH_HUMIDITY, HIGH_CO2 = 70, 1000


def decide(humidity: float, co2: int) -> tuple[DeviceModeEnum, int]:
    if humidity > HIGH_HUMIDITY:
        return DeviceModeEnum.HUMIDITY_EXTRACTION, 80
    if co2 > HIGH_CO2:
        return DeviceModeEnum.CO2_RECOVERY, 70
    return DeviceModeEnum.HEAT_RECOVERY, 50


async def evaluate(pico: PicoCloudClient) -> None:
    s = await pico.get_status()
    mode, fan = decide(s.sensors.humidity_percent, s.sensors.eco2)
    print(f"humidity={s.sensors.humidity_percent}% co2={s.sensors.eco2}ppm "
          f"| now {s.operating.mode.name}/{s.operating.speed_requested}% -> want {mode.name}/{fan}%")

    if not s.is_on:
        await pico.turn_on()
    if s.operating.mode != mode:
        await pico.change_operating_mode(mode)
        await asyncio.sleep(6)  # let the device apply the mode before fan control is validated
    if s.operating.speed_requested != fan:
        try:
            await pico.change_fan_speed(fan)
        except NotSupportedError:
            pass  # mode has no manual fan control


async def main() -> None:
    parser = make_parser("Adaptive Pico control over the cloud.")
    parser.add_argument("--loop", action="store_true", help="Keep re-evaluating")
    parser.add_argument("--interval", type=int, default=120, help="Seconds between evaluations (default 120)")
    args = parse(parser)

    async with PicoCloudClient(args.email, args.password, args.serial, args.pin, verbose=args.verbose) as pico:
        while True:
            await evaluate(pico)
            if not args.loop:
                break
            await asyncio.sleep(args.interval)


if __name__ == "__main__":
    run(main)
