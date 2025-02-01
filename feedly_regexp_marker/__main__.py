from pathlib import Path
from typing import Annotated

import typer
from feedly.api_client.session import FileAuthStore
from logzero import logger

from feedly_regexp_marker.lib.classifier import Classifier
from feedly_regexp_marker.lib.feedly_controller import FeedlyController


def main(
    rules: Annotated[Path, typer.Argument(exists=True)],
    token_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path.home()
    / ".config"
    / "feedly",
    dry_run: bool = False,
):
    try:
        feedly_controller = FeedlyController(auth=FileAuthStore(token_dir=token_dir))

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
    except Exception as e:
        logger.exception(e)
        raise e


if __name__ == "__main__":
    typer.run(main)
