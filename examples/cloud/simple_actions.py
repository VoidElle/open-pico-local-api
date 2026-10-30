#!/usr/bin/env python3
"""
Simple one-shot actions on a device.

Usage:
    python3 simple_actions.py status
    python3 simple_actions.py on
    python3 simple_actions.py off
    python3 simple_actions.py mode 1          # DeviceModeEnum value 1..12
    python3 simple_actions.py fan 60          # needs a mode with fan control
    python3 simple_actions.py led off
    python3 simple_actions.py night on
    python3 simple_actions.py humidity 50     # 40 | 50 | 60

Credentials: --email --password --serial --pin (or PICO_* env vars).
Commands are acked by the cloud and applied by the device a moment later.
"""

import asyncio

from _common import make_parser, parse, run

from open_pico_local_api import DeviceModeEnum, TargetHumidityEnum
from open_pico_local_api.cloud import PicoCloudClient

HUMIDITY = {40: TargetHumidityEnum.FORTY_PERCENT, 50: TargetHumidityEnum.FIFTY_PERCENT,
            60: TargetHumidityEnum.SIXTY_PERCENT}


async def main() -> None:
    parser = make_parser("Simple Pico cloud actions.")
    parser.add_argument("action", choices=["status", "on", "off", "mode", "fan", "led", "night", "humidity"])
    parser.add_argument("value", nargs="?", help="mode number, percentage, or on/off")
    args = parse(parser)

    async with PicoCloudClient(args.email, args.password, args.serial, args.pin, verbose=args.verbose) as pico:
        match args.action:
            case "status":
                s = await pico.get_status()
                print(f"{'ON' if s.is_on else 'OFF'} | {s.operating.mode.name} | fan {s.operating.speed_requested}% | "
                      f"{s.sensors.temperature_celsius}°C | {s.sensors.humidity_percent}%")
                return
            case "on":
                await pico.turn_on()
            case "off":
                await pico.turn_off()
            case "mode":
                await pico.change_operating_mode(DeviceModeEnum(int(args.value)))
            case "fan":
                await pico.change_fan_speed(int(args.value))
            case "led":
                await pico.set_led_status(args.value == "on")
            case "night":
                await pico.set_night_mode(args.value == "on")
            case "humidity":
                await pico.set_target_humidity(HUMIDITY[int(args.value)])
        print(f"{args.action} {args.value or ''}: sent. Checking in 6 s...".replace("  ", " "))
        await asyncio.sleep(6)
        s = await pico.get_status()
        print(f"Now: {'ON' if s.is_on else 'OFF'} | {s.operating.mode.name} | fan {s.operating.speed_requested}%")


if __name__ == "__main__":
    run(main)
