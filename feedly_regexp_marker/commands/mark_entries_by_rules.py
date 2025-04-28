from pathlib import Path
from typing import Annotated

import typer
from feedly.api_client.session import FeedlySession, FileAuthStore
from logzero import logger
from pydantic import ValidationError
from requests import RequestException
from ruamel.yaml.parser import ParserError

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
    logger.info("Starting feedly-regexp-marker process...")
    if dry_run:
        logger.warning("Dry run mode enabled. No entries will be marked.")

    try:
        logger.info(f"Loading rules from: {', '.join(map(str, rules_yaml_paths))}")
        try:
            clf = Classifier.from_yaml_paths(rules_yaml_paths)
            logger.info("Rules loaded and classifier created successfully.")
        except (FileNotFoundError, ValidationError, ParserError):
            logger.exception("Failed to load or parse rules.")
            raise typer.Exit(code=1)
        except Exception:
            logger.exception("An unexpected error occurred during classifier creation.")
            raise typer.Exit(code=1)

        logger.info(f"Initializing Feedly client with token directory: {token_dir}")
        try:
            auth = FileAuthStore(token_dir=token_dir)
            session = FeedlySession(auth=auth)
            feedly_client = FeedlyClient(session=session)
            logger.info("Feedly client initialized successfully.")
        except Exception:
            logger.exception("Failed to initialize Feedly client.")
            raise typer.Exit(code=1)

        logger.info("Fetching unread entries...")
        try:
            entries = list(feedly_client.fetch_all_unread_entries())
            logger.info(f"Fetched {len(entries)} unread entries.")
        except RequestException:
            logger.exception("Failed to fetch entries from Feedly API.")
            raise typer.Exit(code=1)
        except Exception:
            logger.exception("An unexpected error occurred during entry fetching.")
            raise typer.Exit(code=1)

        logger.info("Classifying entries to save...")
        try:
            entries_to_save = [entry for entry in entries if clf.to_save(entry)]
            logger.info(f"Found {len(entries_to_save)} entries to save.")
            if entries_to_save:
                feedly_client.save_entries(
                    entries=entries_to_save,
                    dry_run=dry_run,
                )
                action_verb = "Would save" if dry_run else "Saved"
                logger.info(f"{action_verb} {len(entries_to_save)} entries.")
            else:
                logger.info("No entries to save.")
        except RequestException:
            logger.exception("Failed to save entries via Feedly API.")
            raise typer.Exit(code=1)
        except Exception:
            logger.exception("An unexpected error occurred during saving entries.")
            raise typer.Exit(code=1)

        logger.info("Classifying entries to mark as read...")
        try:
            entries_to_read = [entry for entry in entries if clf.to_read(entry)]
            logger.info(f"Found {len(entries_to_read)} entries to mark as read.")
            if entries_to_read:
                feedly_client.read_entries(
                    entries=entries_to_read,
                    dry_run=dry_run,
                )
                action_verb = "Would mark as read" if dry_run else "Marked as read"
                logger.info(f"{action_verb} {len(entries_to_read)} entries.")
            else:
                logger.info("No entries to mark as read.")
        except RequestException:
            logger.exception("Failed to mark entries as read via Feedly API.")
            raise typer.Exit(code=1)
        except Exception:
            logger.exception(
                "An unexpected error occurred during marking entries as read."
            )
            raise typer.Exit(code=1)

        logger.info("feedly-regexp-marker process finished successfully.")
    except typer.Exit:
        raise
    except Exception:
        logger.exception("An unexpected error occurred in the main process.")
        raise typer.Exit(code=1)
