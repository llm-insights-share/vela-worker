from __future__ import annotations

import typer

from worker_cli.cmds._util import call

app = typer.Typer(help="Workbench summary.")


@app.command("summary")
def summary() -> None:
    call("GET", "/projects/workbench")
