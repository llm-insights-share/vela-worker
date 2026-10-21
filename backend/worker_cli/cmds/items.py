from __future__ import annotations

import typer

from worker_cli.cmds._util import call

app = typer.Typer(help="Project items.")


@app.command("list")
def list_items(project_id: str = typer.Option(..., "--project-id")) -> None:
    call("GET", f"/projects/{project_id}/items")


@app.command("get")
def get_item(item_id: str) -> None:
    call("GET", f"/projects/items/{item_id}")


@app.command("create")
def create_item(
    project_id: str = typer.Option(..., "--project-id"),
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option("", "--description"),
) -> None:
    call("POST", f"/projects/{project_id}/items", json_body={"name": name, "description": description})


@app.command("delegate")
def delegate_item(
    item_id: str,
    worker_id: str = typer.Option(..., "--worker-id"),
    instruction: str = typer.Option(..., "--instruction"),
    task_type: str = typer.Option("", "--task-type"),
) -> None:
    call(
        "POST",
        f"/projects/items/{item_id}/delegate",
        json_body={"worker_id": worker_id, "instruction": instruction, "task_type": task_type, "auto_start": False},
    )


@app.command("start")
def start_item(item_id: str) -> None:
    call("POST", f"/projects/items/{item_id}/start")


@app.command("pause")
def pause_item(item_id: str) -> None:
    call("PATCH", f"/projects/items/{item_id}", json_body={"status": "SUSPENDED"})


@app.command("resume")
def resume_item(item_id: str) -> None:
    call("POST", f"/projects/items/{item_id}/resume")
