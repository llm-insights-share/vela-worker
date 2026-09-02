"""HTTP client wrapping vela-agent REST API (zero-invasion adapter)."""
from typing import Any, Dict, List, Optional
import httpx
from config import (
    VELA_AGENT_BASE_URL,
    VELA_AGENT_USERNAME,
    VELA_AGENT_PASSWORD,
    VELA_AGENT_TOKEN,
)


class VelaAgentError(Exception):
    def __init__(self, message: str, status_code: int = 500, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class VelaAgentClient:
    def __init__(self, base_url: str = None):
        self.base_url = (base_url or VELA_AGENT_BASE_URL).rstrip("/")
        self._access_token: Optional[str] = VELA_AGENT_TOKEN or None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _raise(self, resp: httpx.Response):
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise VelaAgentError(
            f"vela-agent error {resp.status_code}: {detail}",
            status_code=resp.status_code,
            detail=detail,
        )

    def _login(self) -> str:
        if VELA_AGENT_TOKEN:
            self._access_token = VELA_AGENT_TOKEN
            return self._access_token
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                self._url("/auth/login"),
                data={"username": VELA_AGENT_USERNAME, "password": VELA_AGENT_PASSWORD},
            )
            if resp.status_code >= 400:
                self._raise(resp)
            data = resp.json()
            token = data.get("access_token")
            if not token:
                raise VelaAgentError("vela-agent login missing access_token", status_code=502)
            self._access_token = token
            return token

    def _auth_headers(self, *, auth: bool = True) -> dict:
        if not auth:
            return {}
        if not self._access_token:
            self._login()
        return {"Authorization": f"Bearer {self._access_token}"}

    def _maybe_refresh(self, resp: httpx.Response) -> bool:
        if resp.status_code != 401:
            return False
        self._access_token = None
        self._login()
        return True

    def _get(self, path: str, params: dict = None, *, auth: bool = True) -> Any:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(self._url(path), params=params, headers=self._auth_headers(auth=auth))
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                resp = client.get(self._url(path), params=params, headers=self._auth_headers(auth=True))
            if resp.status_code >= 400:
                self._raise(resp)
            return resp.json()

    def _post(
        self,
        path: str,
        json: dict = None,
        *,
        auth: bool = True,
        files: dict = None,
        data: dict = None,
        timeout: float = 120.0,
    ) -> Any:
        with httpx.Client(timeout=timeout) as client:
            kwargs = {"headers": self._auth_headers(auth=auth)}
            if files:
                kwargs["files"] = files
                if data:
                    kwargs["data"] = data
            else:
                kwargs["json"] = json or {}
            resp = client.post(self._url(path), **kwargs)
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                kwargs["headers"] = self._auth_headers(auth=True)
                resp = client.post(self._url(path), **kwargs)
            if resp.status_code >= 400:
                self._raise(resp)
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

    def _put(self, path: str, json: Any = None, *, auth: bool = True) -> Any:
        with httpx.Client(timeout=60.0) as client:
            resp = client.put(self._url(path), json=json, headers=self._auth_headers(auth=auth))
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                resp = client.put(self._url(path), json=json, headers=self._auth_headers(auth=True))
            if resp.status_code >= 400:
                self._raise(resp)
            if not resp.content:
                return {}
            return resp.json()

    def _delete(self, path: str, *, auth: bool = True) -> Any:
        with httpx.Client(timeout=60.0) as client:
            resp = client.delete(self._url(path), headers=self._auth_headers(auth=auth))
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                resp = client.delete(self._url(path), headers=self._auth_headers(auth=True))
            if resp.status_code >= 400:
                self._raise(resp)
            if not resp.content:
                return {}
            return resp.json()

    async def _aget(self, path: str, params: dict = None, *, auth: bool = True) -> Any:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(self._url(path), params=params, headers=self._auth_headers(auth=auth))
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                resp = await client.get(self._url(path), params=params, headers=self._auth_headers(auth=True))
            if resp.status_code >= 400:
                self._raise(resp)
            return resp.json()

    async def _apost(self, path: str, json: dict = None, *, auth: bool = True, timeout: float = 300.0) -> Any:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                self._url(path), json=json or {}, headers=self._auth_headers(auth=auth),
            )
            if resp.status_code == 401 and auth and self._maybe_refresh(resp):
                resp = await client.post(
                    self._url(path), json=json or {}, headers=self._auth_headers(auth=True),
                )
            if resp.status_code >= 400:
                self._raise(resp)
            if not resp.content:
                return {}
            return resp.json()

    # --- Catalog ---

    def list_model_services(self, page_size: int = 100) -> List[dict]:
        data = self._get("/model-services", {"page": 1, "page_size": page_size})
        return data.get("items", data) if isinstance(data, dict) else data

    def list_skills(self, page_size: int = 100) -> List[dict]:
        data = self._get("/skills", {"page": 1, "page_size": page_size})
        return data.get("items", data) if isinstance(data, dict) else data

    def list_tools(self, page_size: int = 100) -> List[dict]:
        data = self._get("/tools", {"page": 1, "page_size": page_size})
        return data.get("items", data) if isinstance(data, dict) else data

    def list_knowledge_bases(self, page_size: int = 100) -> List[dict]:
        data = self._get("/knowledge-bases", {"page": 1, "page_size": page_size})
        return data.get("items", data) if isinstance(data, dict) else data

    def list_agents(self, page_size: int = 100, status: str = None) -> List[dict]:
        params = {"page": 1, "page_size": page_size}
        if status:
            params["status"] = status
        data = self._get("/agents", params)
        return data.get("items", data) if isinstance(data, dict) else data

    def health(self) -> dict:
        return self.check_health()

    def check_health(self) -> dict:
        try:
            with httpx.Client(timeout=5.0) as client:
                url = self.base_url.rstrip("/") + "/health"
                resp = client.get(url)
                if resp.status_code == 200:
                    return resp.json()
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}

    # --- Agents ---

    def create_agent(self, payload: dict) -> dict:
        return self._post("/agents", payload)

    def get_agent(self, agent_id: str) -> dict:
        return self._get(f"/agents/{agent_id}")

    def update_agent(self, agent_id: str, payload: dict) -> dict:
        return self._put(f"/agents/{agent_id}", payload)

    def delete_agent(self, agent_id: str) -> dict:
        return self._delete(f"/agents/{agent_id}")

    def deprecate_agent(self, agent_id: str) -> dict:
        return self._post(f"/agents/{agent_id}/deprecate")

    def republish_agent(self, agent_id: str) -> dict:
        return self._post(f"/agents/{agent_id}/republish")

    def validate_agent(self, agent_id: str) -> dict:
        return self._post(f"/agents/{agent_id}/validate")

    def publish_agent(self, agent_id: str, change_summary: str = "数字员工入职发布") -> dict:
        return self._post(
            f"/agents/{agent_id}/publish",
            {"publish_strategy": "blue-green"},
        )

    def bind_skills(self, agent_id: str, skill_pack_ids: List[str]) -> dict:
        return self._put(f"/agents/{agent_id}/skills", skill_pack_ids)

    def bind_knowledge_bases(self, agent_id: str, kb_ids: List[str]) -> dict:
        return self._put(f"/agents/{agent_id}/knowledge-bases", kb_ids)

    def bind_tools(self, agent_id: str, tool_bindings: List[dict]) -> dict:
        """tool_bindings: [{tool_id, require_approval}] or [tool_id]"""
        return self._put(f"/agents/{agent_id}/tools", tool_bindings)

    # --- Composition (COMPOSITE entry agent) ---

    def get_composition(self, agent_id: str) -> dict:
        return self._get(f"/agents/{agent_id}/composition")

    def add_sub_agent(
        self,
        parent_agent_id: str,
        child_agent_id: str,
        role_name: str,
        role_description: str = "",
        task_keywords: List[str] = None,
    ) -> dict:
        return self._post(
            f"/agents/{parent_agent_id}/composition/sub-agents",
            {
                "child_agent_id": child_agent_id,
                "role_name": role_name,
                "role_description": role_description or "",
                "task_keywords": task_keywords or [],
            },
        )

    def remove_sub_agent(self, parent_agent_id: str, child_agent_id: str) -> dict:
        return self._delete(f"/agents/{parent_agent_id}/composition/sub-agents/{child_agent_id}")

    def update_coordinator_config(self, agent_id: str, config: dict) -> dict:
        return self._put(f"/agents/{agent_id}/composition/coordinator", config)

    def set_memory_enabled(self, agent_id: str, enabled: bool = True) -> dict:
        return self._put("/config/memory/agents", {"items": [{"agent_id": agent_id, "memory_enabled": enabled}]})

    # --- Sessions ---

    def create_session(
        self,
        agent_id: str,
        caller_type: str = "WORKER_TASK",
        caller_id: str = "",
        token_budget: int = 100000,
    ) -> dict:
        return self._post(
            "/sessions",
            {
                "agent_id": agent_id,
                "caller_type": caller_type,
                "caller_id": caller_id,
                "token_budget": token_budget,
            },
        )

    def get_session(self, session_id: str) -> dict:
        return self._get(f"/sessions/{session_id}")

    async def aget_session(self, session_id: str) -> dict:
        return await self._aget(f"/sessions/{session_id}")

    def chat(self, session_id: str, message: str = "", **kwargs) -> dict:
        payload = {"message": message, **kwargs}
        return self._post(f"/sessions/{session_id}/chat", payload)

    async def achat(self, session_id: str, message: str = "", **kwargs) -> dict:
        payload = {"message": message, **kwargs}
        return await self._apost(f"/sessions/{session_id}/chat", payload)

    def chat_async(self, session_id: str, message: str = "", **kwargs) -> dict:
        payload = {"message": message, **kwargs}
        return self._post(f"/sessions/{session_id}/chat/async", payload)

    async def achat_async(self, session_id: str, message: str = "", **kwargs) -> dict:
        payload = {"message": message, **kwargs}
        return await self._apost(f"/sessions/{session_id}/chat/async", payload)

    def upload_session_attachment(
        self,
        session_id: str,
        filename: str,
        file_bytes: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        files = {"file": (filename, file_bytes, content_type)}
        data = {"filename": filename}
        return self._post(f"/sessions/{session_id}/attachments", files=files, data=data)

    def abort_session(self, session_id: str) -> dict:
        return self._post(f"/sessions/{session_id}/abort")

    def close_session(self, session_id: str) -> dict:
        return self._post(f"/sessions/{session_id}/close")

    # --- HITL ---

    def list_pending_approvals(self, session_id: str) -> List[dict]:
        return self._get(f"/sessions/{session_id}/pending-approvals")

    async def alist_pending_approvals(self, session_id: str) -> List[dict]:
        return await self._aget(f"/sessions/{session_id}/pending-approvals")

    def _hitl_review_payload(
        self,
        *,
        approved: bool,
        reviewer: str = "",
        comment: str = "",
        otp_code: Optional[str] = None,
        param_values: Optional[dict] = None,
    ) -> dict:
        payload = {"approved": approved, "reviewer": reviewer, "comment": comment}
        if otp_code:
            payload["otp_code"] = otp_code
        if param_values:
            payload["param_values"] = param_values
        return payload

    def approve(
        self,
        session_id: str,
        approval_id: str,
        reviewer: str = "",
        comment: str = "",
        *,
        otp_code: Optional[str] = None,
        param_values: Optional[dict] = None,
    ) -> dict:
        return self._post(
            f"/sessions/{session_id}/approvals/{approval_id}/approve",
            self._hitl_review_payload(
                approved=True,
                reviewer=reviewer,
                comment=comment,
                otp_code=otp_code,
                param_values=param_values,
            ),
        )

    def reject(
        self,
        session_id: str,
        approval_id: str,
        reviewer: str = "",
        comment: str = "",
        *,
        otp_code: Optional[str] = None,
        param_values: Optional[dict] = None,
    ) -> dict:
        return self._post(
            f"/sessions/{session_id}/approvals/{approval_id}/reject",
            self._hitl_review_payload(
                approved=False,
                reviewer=reviewer,
                comment=comment,
                otp_code=otp_code,
                param_values=param_values,
            ),
        )


vela_agent_client = VelaAgentClient()
