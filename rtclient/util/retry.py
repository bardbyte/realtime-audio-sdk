import asyncio
import random
import logging
import functools
from typing import Callable, Any, Tuple, Type

# Use the root logger or get a specific one
logger = logging.getLogger(__name__)

def retry_async(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
    backoff_factor: float = 2.0,
    jitter: float = 0.1,
    retry_on_exceptions: Tuple[Type[Exception], ...] = (Exception,) # Default: retry on any Exception
):
    """
    A decorator for retrying an async function with exponential backoff and jitter.

    Args:
        max_attempts: Maximum number of attempts.
        initial_delay: Delay before the first retry (seconds).
        max_delay: Maximum delay between retries (seconds).
        backoff_factor: Multiplier for the delay calculation (e.g., 2 for exponential).
        jitter: Factor for adding randomness to delay (0 to 1). Delay will be
                calculated_delay * (1 +/- jitter).
        retry_on_exceptions: A tuple of exception classes that should trigger a retry.
                             If not specified, retries on base Exception.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt = 0
            current_delay = initial_delay
            while attempt < max_attempts:
                attempt += 1
                try:
                    # logger.debug(f"Attempt {attempt}/{max_attempts} calling {func.__name__}")
                    return await func(*args, **kwargs)
                except retry_on_exceptions as e:
                    if attempt >= max_attempts:
                        logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts. Last error: {e}",
                            exc_info=True # Include traceback in log
                        )
                        raise # Re-raise the last exception
                    else:
                        # Calculate delay with backoff
                        delay = current_delay * (backoff_factor ** (attempt - 1))
                        # Apply jitter: delay * (1 +/- jitter_factor)
                        jitter_amount = delay * jitter * (random.random() * 2 - 1) # range [-jitter, +jitter]
                        actual_delay = min(max_delay, delay) + jitter_amount
                        # Ensure delay isn't negative due to jitter
                        actual_delay = max(0, actual_delay)

                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__} with error: {e}. "
                            f"Retrying in {actual_delay:.2f} seconds..."
                        )
                        await asyncio.sleep(actual_delay)
                        # Update delay for next potential attempt (only used if factor > 1)
                        # current_delay *= backoff_factor # This was causing too rapid increase, calc directly instead
                # Do not retry on exceptions not in retry_on_exceptions
                except Exception as e:
                     logger.error(f"Function {func.__name__} failed with non-retryable error: {e}", exc_info=True)
                     raise

        return wrapper
    return decorator
