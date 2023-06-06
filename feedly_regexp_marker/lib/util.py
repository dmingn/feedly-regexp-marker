import time
from pathlib import Path
from typing import Callable, Optional

from feedly.api_client.protocol import UnauthorizedAPIError, WrappedHTTPError
from logzero import logger
from slack_sdk import WebhookClient
from watchfiles import watch


def log_function_call(f: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        logger.info(f"function {f.__name__} called with {args, kwargs}.")
        ret = f(*args, **kwargs)
        logger.info(f"function {f.__name__} returned {ret}.")
        return ret

    return wrapper


def report_exception(client: WebhookClient) -> Callable:
    def report_exception(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except WrappedHTTPError as e:
                logger.exception(e)
                client.send(text=e.reason)
                raise
            except BaseException as e:
                logger.exception(e)
                client.send(text=str(e))
                raise

        return wrapper

    return report_exception


@log_function_call
def wait_for_creation(path: Path):
    while not path.exists():
        time.sleep(1)


@log_function_call
def wait_for_change(path: Path):
    for _ in watch(path, rust_timeout=0):
        break


def sleep_and_repeat(
    minutes_to_sleep: Optional[int], access_token_path: Path
) -> Callable:
    def sleep_and_repeat(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if minutes_to_sleep:
                while True:
                    try:
                        f(*args, **kwargs)
                    except UnauthorizedAPIError:
                        wait_for_change(access_token_path)
                    except FileNotFoundError as e:
                        if e.filename == str(access_token_path):
                            wait_for_creation(access_token_path)
                        else:
                            logger.info(f"sleep for {minutes_to_sleep} minutes.")
                            time.sleep(minutes_to_sleep * 60)
                    except BaseException as e:
                        logger.exception(e)
                        logger.info(f"sleep for {minutes_to_sleep} minutes.")
                        time.sleep(minutes_to_sleep * 60)
                    else:
                        logger.info(f"sleep for {minutes_to_sleep} minutes.")
                        time.sleep(minutes_to_sleep * 60)
            else:
                f(*args, **kwargs)

        return wrapper

    return sleep_and_repeat
