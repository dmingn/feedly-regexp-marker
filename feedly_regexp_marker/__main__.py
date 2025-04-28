import typer

from feedly_regexp_marker.commands.gen_json_schema_for_rules import (
    app as gen_json_schema_for_rules_app,
)
from feedly_regexp_marker.commands.mark_entries_by_rules import (
    app as mark_entries_by_rules_app,
)

app = typer.Typer()
app.add_typer(gen_json_schema_for_rules_app)
app.add_typer(mark_entries_by_rules_app)

if __name__ == "__main__":
    app()
