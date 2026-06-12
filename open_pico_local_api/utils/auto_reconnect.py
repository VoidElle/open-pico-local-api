import asyncio
from functools import wraps

from open_pico_local_api.exceptions.pico_connection_error import PicoConnectionError


def auto_reconnect(func):
    """
    Decorator to automatically reconnect on connection failures.

    Attempts to reconnect up to _max_reconnect_attempts times before raising.
    Only works on async methods of PicoClient.
    """

    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not self._auto_reconnect:
            return await func(self, *args, **kwargs)

        max_attempts = self._max_reconnect_attempts

        for attempt in range(max_attempts):
            try:
                if not self._connected:
                    if self.verbose:
                        print(f"⚠ Not connected, attempting to connect...")
                    await self.connect()

                return await func(self, *args, **kwargs)

            except (PicoConnectionError, OSError) as e:
                if attempt < max_attempts - 1:
                    if self.verbose:
                        print(f"⚠ Connection lost during {func.__name__}, reconnecting... ({attempt + 1}/{max_attempts})")

                    try:
                        await self.disconnect()
                    except (PicoConnectionError, OSError):
                        pass

                    await asyncio.sleep(self._reconnect_delay)

                    try:
                        await self.connect()
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
                raise

        return None

    return wrapper