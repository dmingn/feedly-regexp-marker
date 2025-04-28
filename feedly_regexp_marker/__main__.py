import typer

from feedly_regexp_marker.commands.mark_entries_by_rules import (
    app as mark_entries_by_rules_app,
)

app = typer.Typer()
app.add_typer(mark_entries_by_rules_app)

if __name__ == "__main__":
    app()
