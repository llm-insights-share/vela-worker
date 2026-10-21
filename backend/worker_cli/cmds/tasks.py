from __future__ import annotations

from typing import Optional

import typer

from worker_cli.cmds._util import call

app = typer.Typer(help="Work tasks.")


@app.command("list")
def list_tasks(
    worker_id: Optional[str] = typer.Option(None, "--worker-id"),
    status: Optional[str] = typer.Option(None, "--status"),
    page_size: int = typer.Option(20, "--page-size"),
) -> None:
    params = {"page": 1, "page_size": page_size}
    if worker_id:
        params["worker_id"] = worker_id
    if status:
        params["status"] = status
    call("GET", "/tasks", params=params)


@app.command("get")
def get_task(task_id: str) -> None:
    call("GET", f"/tasks/{task_id}")
