"""Typer entry for worker_cli."""
from __future__ import annotations

import typer

from worker_cli import __version__
from worker_cli.cmds import auth, items, projects, tasks, workbench, workers
from worker_cli.output import set_json_mode

app = typer.Typer(
    name="worker",
    help="Vela Worker workbench CLI (calls /api/v1).",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    set_json_mode(json_output)


@app.command("version")
def version() -> None:
    typer.echo(__version__)


app.add_typer(auth.app, name="auth")
app.add_typer(projects.app, name="projects")
app.add_typer(items.app, name="items")
app.add_typer(workers.app, name="workers")
app.add_typer(tasks.app, name="tasks")
app.add_typer(workbench.app, name="workbench")


def run() -> None:
    app()
