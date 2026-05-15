import socket
import time
from functools import wraps

from open_pico_local_api.exceptions.pico_connection_error import PicoConnectionError


def auto_reconnect(func):
    """
    Decorator to automatically reconnect on connection failures.

    Attempts to reconnect up to max_reconnect_attempts times before raising an error.
    Only works on methods of PicoClient class.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self._auto_reconnect:
            # Auto-reconnect disabled, execute normally
            return func(self, *args, **kwargs)

        max_attempts = self._max_reconnect_attempts

        for attempt in range(max_attempts):
            try:
                # Ensure we're connected before attempting
                if not self._connected:
                    if self.verbose:
                        print(f"⚠ Not connected, attempting to connect...")
                    self.connect()

                return func(self, *args, **kwargs)

            except (PicoConnectionError, OSError, socket.error) as e:
                if attempt < max_attempts - 1:
                    if self.verbose:
                        print(
                            f"⚠ Connection lost during {func.__name__}, reconnecting... ({attempt + 1}/{max_attempts})")

                    # Clean up current connection
                    try:
                        self.disconnect()
                    except (PicoConnectionError, OSError, socket.error):
                        pass

                    # Wait before reconnecting
                    time.sleep(self._reconnect_delay)

                    # Attempt reconnection
                    try:
                        self.connect()
                        if self.verbose:
                            print(f"✓ Reconnected successfully")
                    except Exception as reconnect_error:
                        if self.verbose:
                            print(f"✗ Reconnection attempt {attempt + 1} failed: {reconnect_error}")
                        if attempt == max_attempts - 2:
                            raise PicoConnectionError(
                                f"Failed to reconnect after {max_attempts} attempts. Last error: {reconnect_error}"
                            )
                else:
                    raise PicoConnectionError(
                        f"Failed after {max_attempts} reconnection attempts. Last error: {e}"
                    )

            except Exception:
                # For non-connection errors, don't retry
                raise

        return None

    return wrapper