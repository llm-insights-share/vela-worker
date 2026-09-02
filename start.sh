#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

export VELA_AGENT_BASE_URL="${VELA_AGENT_BASE_URL:-http://localhost:8000/api/v1}"
export VELA_AGENT_USERNAME="${VELA_AGENT_USERNAME:-admin}"
export VELA_AGENT_PASSWORD="${VELA_AGENT_PASSWORD:-admin123}"

echo "=== 启动 Vela Worker ==="
echo "VELA_AGENT_BASE_URL=$VELA_AGENT_BASE_URL"
echo "VELA_AGENT_USERNAME=$VELA_AGENT_USERNAME"

# Probe vela-agent
AGENT_HEALTH="${VELA_AGENT_BASE_URL%/api/v1}/api/v1/health"
AGENT_HEALTH="${VELA_AGENT_BASE_URL}/health"
if curl -sf "$AGENT_HEALTH" >/dev/null 2>&1; then
  echo "✓ vela-agent 可达 ($VELA_AGENT_BASE_URL)"
else
  echo "⚠ vela-agent 未检测到 ($VELA_AGENT_BASE_URL)。入职/问答/任务将依赖其可用。"
  echo "  若 8000 被占用，可另起 agent：cd ../vela-agent/backend && uvicorn main:app --port 8001"
  echo "  然后：VELA_AGENT_BASE_URL=http://localhost:8001/api/v1 ./start.sh"
  echo "  若 agent 启用了 JWT（v0.9+），请设置 VELA_AGENT_USERNAME / VELA_AGENT_PASSWORD（默认 admin/admin123）"
fi

echo "启动后端服务 (端口 8100)..."
cd "$BACKEND_DIR"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt -q
fi
nohup env VELA_AGENT_BASE_URL="$VELA_AGENT_BASE_URL" VELA_AGENT_USERNAME="$VELA_AGENT_USERNAME" VELA_AGENT_PASSWORD="$VELA_AGENT_PASSWORD" .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8100 --reload > "$PROJECT_DIR/backend.log" 2>&1 &
echo "后端已启动 (PID: $!), 日志: $PROJECT_DIR/backend.log"

echo "启动前端服务 (端口 5174)..."
cd "$FRONTEND_DIR"
if [ ! -d "node_modules" ]; then
  npm install
fi
nohup npx vite --host 0.0.0.0 --port 5174 > "$PROJECT_DIR/frontend.log" 2>&1 &
echo "前端已启动 (PID: $!), 日志: $PROJECT_DIR/frontend.log"

echo "=== 启动完成 ==="
echo "后端 API: http://localhost:8100/docs"
echo "前端页面: http://localhost:5174"
echo "默认用户: u-admin（顶部可切换）"
