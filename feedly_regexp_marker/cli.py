import os
import time
from pathlib import Path
from typing import Callable, Optional

import click
from feedly.api_client.protocol import UnauthorizedAPIError, WrappedHTTPError
from feedly.api_client.session import FileAuthStore
from slack_sdk import WebhookClient
from watchfiles import watch

from feedly_regexp_marker.lib.classifier import Classifier
from feedly_regexp_marker.lib.feedly_controller import FeedlyController


def report_exception(client: WebhookClient) -> Callable:
    def report_exception(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                f(*args, **kwargs)
            except WrappedHTTPError as e:
                client.send(text=e.reason)
                raise
            except BaseException as e:
                client.send(text=e)
                raise

        return wrapper

    return report_exception


def sleep_and_repeat(minutes_to_sleep: Optional[int]) -> Callable:
    def sleep_and_repeat(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            if minutes_to_sleep:
                while True:
                    try:
                        f(*args, **kwargs)
                    except UnauthorizedAPIError:
                        for _ in watch(
                            Path.home() / ".config" / "feedly" / "access.token",
                            rust_timeout=0,
                        ):
                            break
                    except BaseException:
                        time.sleep(minutes_to_sleep * 60)
                    else:
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
