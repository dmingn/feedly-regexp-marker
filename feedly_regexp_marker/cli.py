import time
from pathlib import Path
from typing import Optional

import click
import schedule
from feedly.api_client.session import FileAuthStore

from feedly_regexp_marker.lib.classifier import Classifier
from feedly_regexp_marker.lib.feedly_controller import FeedlyController


@click.command()
@click.option("--rules", type=click.Path(exists=True, path_type=Path), required=True)
@click.option(
    "--every-n-minutes",
    type=click.IntRange(min=1),
    default=None,
)
@click.option("-n", "--dry-run", is_flag=True)
def main(rules: Path, every_n_minutes: Optional[int], dry_run: bool):
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
            schedule.every(every_n_minutes).minutes.do(job)

            while True:
                schedule.run_pending()
                time.sleep(1)
        else:
            job()

    inner_main()
