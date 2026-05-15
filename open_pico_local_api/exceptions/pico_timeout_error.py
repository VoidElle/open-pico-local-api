from open_pico_local_api.exceptions.pico_device_error import PicoDeviceError


class PicoTimeoutError(PicoDeviceError):
    """Raised when operation times out"""
    pass