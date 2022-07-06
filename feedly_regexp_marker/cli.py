import os
from pathlib import Path
from typing import Optional

import click
from feedly.api_client.session import FileAuthStore
from slack_sdk import WebhookClient

from feedly_regexp_marker.lib.classifier import Classifier
from feedly_regexp_marker.lib.feedly_controller import FeedlyController
from feedly_regexp_marker.lib.util import (
    log_function_call,
    report_exception,
    sleep_and_repeat,
)

access_token_path = Path.home() / ".config" / "feedly" / "access.token"


@click.command()
@click.option("--rules", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--minutes-to-sleep",
    type=click.IntRange(min=1),
    default=None,
)
@click.option("-n", "--dry-run", is_flag=True)
def main(rules: Path, minutes_to_sleep: Optional[int], dry_run: bool):
    @sleep_and_repeat(
        minutes_to_sleep=minutes_to_sleep, access_token_path=access_token_path
    )
    @report_exception(client=WebhookClient(url=os.environ["SLACK_WEBHOOK_URL"]))
    @log_function_call
    def job():
        feedly_controller = FeedlyController(auth=FileAuthStore())

        entries = feedly_controller.fetch_unread_entries()

        clf = Classifier.from_yml(rules)

        feedly_controller.save_entries(
            entries=[entry for entry in entries if clf.to_save(entry)],
            dry_run=dry_run,
        )

        feedly_controller.read_entries(
            entries=[entry for entry in entries if clf.to_read(entry)],
            dry_run=dry_run,
        )

    job()
