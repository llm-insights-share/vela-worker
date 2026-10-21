from __future__ import annotations

import typer

from worker_cli.cmds._util import call

app = typer.Typer(help="Projects.")


@app.command("list")
def list_projects() -> None:
    call("GET", "/projects")


@app.command("get")
def get_project(project_id: str) -> None:
    call("GET", f"/projects/{project_id}")


@app.command("create")
def create_project(
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option("", "--description"),
) -> None:
    call("POST", "/projects", json_body={"name": name, "description": description})
