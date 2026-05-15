from open_pico_local_api.exceptions.pico_device_error import PicoDeviceError


class PicoConnectionError(PicoDeviceError):
    """Raised when connection fails"""
    pass