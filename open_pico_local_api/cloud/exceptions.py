from ..exceptions.pico_device_error import PicoDeviceError


class PicoAuthError(PicoDeviceError):
    """Login rejected or session expired."""
