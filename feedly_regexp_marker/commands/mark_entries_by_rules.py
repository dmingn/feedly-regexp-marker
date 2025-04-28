from pathlib import Path
from typing import Annotated

import typer
from feedly.api_client.session import FeedlySession, FileAuthStore
from logzero import logger

from feedly_regexp_marker.classifier import Classifier
from feedly_regexp_marker.feedly_client import FeedlyClient

app = typer.Typer()


@app.command()
def mark_entries_by_rules(
    rules_yaml_paths: Annotated[
        list[Path],
        typer.Argument(
            file_okay=True,
            dir_okay=False,
            exists=True,
            readable=True,
            help="Path(s) to the rules YAML file(s)",
        ),
    ],
    token_dir: Annotated[Path, typer.Option(exists=True, file_okay=False)] = Path.home()
    / ".config"
    / "feedly",
    dry_run: bool = False,
):
    try:
        feedly_client = FeedlyClient(
            session=FeedlySession(auth=FileAuthStore(token_dir=token_dir))
        )

        entries = list(feedly_client.fetch_all_unread_entries())
        logger.info(f"fetched {len(entries)} entries.")

        clf = Classifier.from_yaml_paths(rules_yaml_paths)

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
        typer.Exit(1)
