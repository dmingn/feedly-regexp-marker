import os
import time
from pathlib import Path
from typing import Callable, Optional

import click
from feedly.api_client.protocol import WrappedHTTPError
from feedly.api_client.session import FileAuthStore
from slack_sdk import WebhookClient

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


@click.command()
@click.option("--rules", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--every-n-minutes",
    type=click.IntRange(min=1),
    default=None,
)
@click.option("-n", "--dry-run", is_flag=True)
def main(rules: Path, every_n_minutes: Optional[int], dry_run: bool):
    @report_exception(client=WebhookClient(url=os.environ["SLACK_WEBHOOK_URL"]))
    def inner_main():
        feedly_controller = FeedlyController(auth=FileAuthStore())

        def job():
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

        if every_n_minutes:
            while True:
                job()
                time.sleep(every_n_minutes * 60)
        else:
            job()

    inner_main()
