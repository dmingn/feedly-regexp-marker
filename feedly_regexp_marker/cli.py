import os
import time
from pathlib import Path
from typing import Callable, Optional

import click
from feedly.api_client.protocol import UnauthorizedAPIError, WrappedHTTPError
from feedly.api_client.session import FileAuthStore
from logzero import logger
from slack_sdk import WebhookClient
from watchfiles import watch

from feedly_regexp_marker.lib.classifier import Classifier
from feedly_regexp_marker.lib.feedly_controller import FeedlyController

access_token_path = Path.home() / ".config" / "feedly" / "access.token"


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


def sleep_and_repeat(minutes_to_sleep: Optional[int]) -> Callable:
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
                    except BaseException:
                        logger.info(f"sleep for {minutes_to_sleep} minutes.")
                        time.sleep(minutes_to_sleep * 60)
                    else:
                        logger.info(f"sleep for {minutes_to_sleep} minutes.")
                        time.sleep(minutes_to_sleep * 60)
            else:
                f(*args, **kwargs)

        return wrapper

    return sleep_and_repeat


@click.command()
@click.option("--rules", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--minutes-to-sleep",
    type=click.IntRange(min=1),
    default=None,
)
@click.option("-n", "--dry-run", is_flag=True)
def main(rules: Path, minutes_to_sleep: Optional[int], dry_run: bool):
    @sleep_and_repeat(minutes_to_sleep=minutes_to_sleep)
    @report_exception(client=WebhookClient(url=os.environ["SLACK_WEBHOOK_URL"]))
    @log_function_call
    def job():
        feedly_controller = FeedlyController(auth=FileAuthStore())

        entries = feedly_controller.fetch_unread_entries()

        clf = Classifier.from_yaml(rules)

        feedly_controller.save_entries(
            entries=[entry for entry in entries if clf.to_save(entry)],
            dry_run=dry_run,
        )

        feedly_controller.read_entries(
            entries=[entry for entry in entries if clf.to_read(entry)],
            dry_run=dry_run,
        )

    job()
