from open_pico_local_api.exceptions.pico_device_error import PicoDeviceError


class NotSupportedError(PicoDeviceError):
    """Raised when an operation is not supported by the device"""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)