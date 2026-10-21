from __future__ import annotations

import typer

from worker_cli.cmds._util import call

app = typer.Typer(help="Digital workers.")


@app.command("list")
def list_workers(page_size: int = typer.Option(50, "--page-size")) -> None:
    call("GET", "/workers", params={"page": 1, "page_size": page_size})


@app.command("get")
def get_worker(worker_id: str) -> None:
    call("GET", f"/workers/{worker_id}")
