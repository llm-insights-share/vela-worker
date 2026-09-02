# Vela·Worker — AI Agent 数字员工服务

企业数字员工服务层。Agent 运行时复用 **vela-agent**（零侵入 REST 集成）。

## 快速启动

前提：vela-agent 已运行（默认 `http://localhost:8000`）。v0.9+ 需 JWT，worker 适配层默认使用 `admin` / `admin123` 登录（可通过环境变量覆盖）。

```bash
# 可选：覆盖 vela-agent 服务账号（出站调用 agent）
export VELA_AGENT_USERNAME=admin
export VELA_AGENT_PASSWORD=admin123
# 或静态 Token（跳过 login）
# export VELA_AGENT_TOKEN=eyJ...

# 可选：vela-worker 自身 JWT 配置
# export VELA_WORKER_SECRET_KEY=change-me
# export VELA_WORKER_ACCESS_TOKEN_EXPIRE_MINUTES=720

./start.sh
```

若本机 8000 已被占用，可另起 agent 并指定地址：

```bash
# 终端 1
cd ../vela-agent/backend && uvicorn main:app --host 127.0.0.1 --port 8001

# 终端 2
VELA_AGENT_BASE_URL=http://127.0.0.1:8001/api/v1 VELA_AGENT_USERNAME=admin VELA_AGENT_PASSWORD=admin123 ./start.sh
```

| 服务 | 地址 |
|---|---|
| 后端 API / Docs | http://localhost:8100/docs |
| 前端（管理后台 + IM） | http://localhost:5174 |
| 默认登录账号 | `admin` / `admin123`（平台管理员） |

### 登录与用户管理

- 打开前端后进入登录页；支持注册（默认角色 `EMPLOYEE`）
- 平台管理员可在侧栏「用户管理」中创建/启停/改角色/删除用户
- 个人设置：`/me/settings`（资料、密码、头像）
- 业务 API 需 `Authorization: Bearer <token>`；开放 API 仍使用 `X-API-Key`

种子用户（密码均为 `admin123`）：

| 用户名 | 角色 |
|---|---|
| `admin` | PLATFORM_ADMIN |
| `zhang` | DEPT_ADMIN |
| `lisi` / `wang` | EMPLOYEE |

## 功能范围（M1–M5）

- **M1** 角色 / 数字员工入职（自动创建并发布 vela-agent Agent）/ Worker Spec / 权限覆盖
- **M2** IM 单聊群聊、规格卡片、@问答、WebSocket
- **M3** 任务中心、IM 指派、Task Runner 轮询、结果卡
- **M4** HITL 审批卡桥接
- **M5** 开放应用 API Key、任务派发、Webhook（HMAC + 重试）
- **鉴权** JWT 注册/登录、用户管理（对齐 vela-agent）

## 目录

```
backend/   FastAPI + SQLAlchemy (worker.db)
frontend/  Vue3 + Ant Design Vue + Pinia
vela-worker-design.md
```
