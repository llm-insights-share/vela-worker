# 办公操作助手

`vela-worker-ops-assistant` 通过对齐 vela-agent `vela-ops-assistant` 的方式，用对话执行办公工作台操作。

## 架构

1. 右下角悬浮对话调用 worker `POST /api/v1/ops-assistant/sessions` 与消息接口。
2. worker 在 vela-agent 上为当前登录用户创建会话（`caller_id` = worker 用户名）。
3. Agent 调用 `services.worker_ops_tools` 中的 `worker_*` 工具，以该用户身份请求 worker `/api/v1`。
4. 创建、委派、启动、暂停、继续执行需要 HITL 批准。

## 配置

两边密钥必须一致，工具才能签发可被 worker 接受的 JWT：

| 变量 | 默认 | 说明 |
|------|------|------|
| `VELA_WORKER_API_BASE` | `http://127.0.0.1:8100/api/v1` | worker API（vela-agent 进程与 CLI 使用） |
| `VELA_WORKER_SECRET_KEY` | `vela-worker-dev-secret-change-me` | 与 worker `VELA_WORKER_SECRET_KEY` 相同 |
| `VELA_WORKER_API_TOKEN` | 空 | 若设置则工具直接使用该 Bearer，不再按 caller 签发 |
| `VELA_AGENT_BASE_URL` | `http://localhost:8000/api/v1` | worker 访问 vela-agent |

## 安装与种子

```bash
cd backend
pip install -r requirements.txt
python -m worker_cli --help
python -m scripts.seed_ops_assistant
```

种子会在 vela-agent 上幂等创建 LOCAL_PYTHON 工具、发布 `vela-worker-ops-assistant`，并把 `agent_id` 写到 `backend/data/ops_assistant.json`。

CLI 登录（可选，给人用）：

```bash
python -m worker_cli auth login -u admin -p admin123
python -m worker_cli --json projects list
```

## 验收

1. 登录工作台，右下角出现操作按钮；未 seed 时面板提示运行 `python -m scripts.seed_ops_assistant`。
2. 对话「列出我的项目」返回与左侧项目树一致的名称。
3. 「在某项目下创建事项并委派给某数字员工」先出现批准，批准后事项为待启动。
4. 「启动 / 暂停 / 继续」经批准后，事项与步骤状态与界面一致。
