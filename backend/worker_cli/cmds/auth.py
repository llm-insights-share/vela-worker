from __future__ import annotations

import httpx
import typer

from worker_cli.client import get_api_base, save_credentials
from worker_cli.cmds._util import call
from worker_cli.output import emit, fail

app = typer.Typer(help="Login and identity.")


@app.command("login")
def login(
    username: str = typer.Option(..., "-u", "--username"),
    password: str = typer.Option(..., "-p", "--password"),
) -> None:
    resp = httpx.post(
        f"{get_api_base()}/auth/login",
        data={"username": username, "password": password},
        timeout=30.0,
    )
    if resp.status_code >= 400:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        fail(resp.status_code, body)
    data = resp.json()
    token = data.get("access_token") or ""
    if not token:
        fail(502, "login missing access_token")
    save_credentials(token)
    emit({"ok": True, "username": username})


@app.command("whoami")
def whoami() -> None:
    call("GET", "/auth/me")
