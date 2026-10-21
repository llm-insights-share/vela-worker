from __future__ import annotations

from typing import Any, Optional

import typer

from worker_cli.client import ApiClient, WorkerApiError
from worker_cli.output import emit, fail


def call(method: str, path: str, *, json_body: Any = None, params: Optional[dict] = None, auth: bool = True) -> None:
    client = ApiClient()
    try:
        data = client.request(method, path, json_body=json_body, params=params, auth=auth)
        emit(data)
    except WorkerApiError as exc:
        fail(exc.status_code, exc.body)
    finally:
        client.close()


def opt_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = value.strip()
    return text or None
