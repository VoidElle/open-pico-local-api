from typing import Optional, Dict, Any


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

    return None