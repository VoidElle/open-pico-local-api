from exceptions.pico_device_error import PicoDeviceError


class PicoTimeoutError(PicoDeviceError):
    """Raised when operation times out"""
    pass