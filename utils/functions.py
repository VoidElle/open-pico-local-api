from typing import Optional, Dict, Any

from enums.device_mode_enum import DeviceModeEnum
from enums.on_off_state_enum import OnOffStateEnum


def quick_status(ip: str, pin: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    Quickly get device status without managing connection.

    Args:
        ip: Device IP address
        pin: Device PIN code
        **kwargs: Additional IoTDevice parameters

    Returns:
        Device status or None

    Example:
        >>> status = quick_status("192.168.1.208", "1234")
    """
    from pico_client import PicoClient
    with PicoClient(ip=ip, pin=pin, **kwargs) as iot_device:
        return iot_device.get_status()

def device_current_mode_supports_fan_control(mode: DeviceModeEnum, on_off_state: OnOffStateEnum) -> bool:
    """
    Check if the given device mode supports fan control.

    Args:
        :param mode: DeviceModeEnum to check
        :param on_off_state: OnOffStateEnum to check
    Returns:
        True if mode supports fan control and the device is on, False otherwise
    """
    from utils.constants import MODULAR_FAN_SPEED_PRESET_MODES
    return mode in MODULAR_FAN_SPEED_PRESET_MODES and on_off_state == OnOffStateEnum.ON

def device_current_mode_supports_target_humidity_selection(mode: DeviceModeEnum, on_off_state: OnOffStateEnum) -> bool:
    """
    Check if the given device mode supports humidity selection.

    Args:
        :param mode: DeviceModeEnum to check
        :param on_off_state: OnOffStateEnum to check
    Returns:
        True if mode supports humidity selection and the device is on, False otherwise
    """
    from utils.constants import HUMIDITY_SELECTOR_PRESET_MODES
    return mode in HUMIDITY_SELECTOR_PRESET_MODES and on_off_state == OnOffStateEnum.ON