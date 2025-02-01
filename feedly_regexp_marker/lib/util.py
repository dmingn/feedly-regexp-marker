from typing import Callable

from feedly.api_client.protocol import WrappedHTTPError
from logzero import logger
from slack_sdk import WebhookClient


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
