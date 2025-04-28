from pathlib import Path
from typing import Annotated

import typer
from feedly.api_client.session import FileAuthStore
from logzero import logger

from feedly_regexp_marker.classifier import Classifier
from feedly_regexp_marker.feedly_client import FeedlyClient


def cli(
    rules: Annotated[Path, typer.Argument(exists=True)],
    token_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path.home()
    / ".config"
    / "feedly",
    dry_run: bool = False,
):
    try:
        feedly_client = FeedlyClient(auth=FileAuthStore(token_dir=token_dir))

        entries = feedly_client.fetch_all_unread_entries()
        logger.info(f"fetched {len(entries)} entries.")

        clf = Classifier.from_yml(rules)

        entries_to_save = [entry for entry in entries if clf.to_save(entry)]
        feedly_client.save_entries(
            entries=entries_to_save,
            dry_run=dry_run,
        )
        logger.info(f"saved {len(entries_to_save)} entries.")

        entries_to_read = [entry for entry in entries if clf.to_read(entry)]
        feedly_client.read_entries(
            entries=entries_to_read,
            dry_run=dry_run,
        )
        logger.info(f"read {len(entries_to_read)} entries.")
    except Exception as e:
        logger.exception(e)
        raise e


def main():
    typer.run(cli)


if __name__ == "__main__":
    main()
