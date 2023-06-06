import os
from pathlib import Path
from typing import Optional

import click
from feedly.api_client.session import FileAuthStore
from logzero import logger
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

        entries = feedly_controller.fetch_all_unread_entries()
        logger.info(f"fetched {len(entries)} entries.")

        clf = Classifier.from_yml(rules)

        entries_to_save = [entry for entry in entries if clf.to_save(entry)]
        feedly_controller.save_entries(
            entries=entries_to_save,
            dry_run=dry_run,
        )
        logger.info(f"saved {len(entries_to_save)} entries.")

        entries_to_read = [entry for entry in entries if clf.to_read(entry)]
        feedly_controller.read_entries(
            entries=entries_to_read,
            dry_run=dry_run,
        )
        logger.info(f"read {len(entries_to_read)} entries.")

    job()
