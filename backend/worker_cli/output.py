"""JSON / text output for worker_cli."""
from __future__ import annotations

import json
import sys
from typing import Any

_JSON = False


def set_json_mode(enabled: bool) -> None:
    global _JSON
    _JSON = enabled


def emit(data: Any) -> None:
    if _JSON:
        print(json.dumps(data, ensure_ascii=False, default=str))
    else:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        else:
            print(data)


def fail(status_code: int, body: Any) -> None:
    payload = {"success": False, "status_code": status_code, "body": body}
    print(json.dumps(payload, ensure_ascii=False, default=str), file=sys.stdout if _JSON else sys.stderr)
    raise SystemExit(1)
