"""HTTP client for worker_cli → vela-worker /api/v1."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

DEFAULT_API_BASE = "http://127.0.0.1:8100/api/v1"
CREDENTIALS_PATH = Path.home() / ".vela-worker" / "credentials.json"


class WorkerApiError(Exception):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


def get_api_base() -> str:
    return (os.environ.get("VELA_WORKER_API_BASE") or DEFAULT_API_BASE).rstrip("/")


def load_token() -> str:
    env = (os.environ.get("VELA_WORKER_API_TOKEN") or "").strip()
    if env:
        return env
    if CREDENTIALS_PATH.exists():
        try:
            data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
            return str(data.get("access_token") or "").strip()
        except (OSError, json.JSONDecodeError):
            return ""
    return ""


def save_credentials(access_token: str, api_base: Optional[str] = None) -> None:
    CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"access_token": access_token, "api_base": api_base or get_api_base()}
    CREDENTIALS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ApiClient:
    def __init__(self, token: Optional[str] = None, base: Optional[str] = None):
        self.base = (base or get_api_base()).rstrip("/")
        self.token = (token if token is not None else load_token()).strip()
        self._http = httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        auth: bool = True,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base}{path if path.startswith('/') else '/' + path}"
        headers = {"Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        resp = self._http.request(method.upper(), url, headers=headers, json=json_body, params=params)
        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise WorkerApiError(resp.status_code, body)
        if resp.status_code == 204 or not resp.content:
            return {"ok": True}
        try:
            return resp.json()
        except Exception:
            return {"text": resp.text}
