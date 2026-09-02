#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "停止 Vela Worker..."
pkill -f "uvicorn main:app --host 0.0.0.0 --port 8100" 2>/dev/null || true
pkill -f "vite --host 0.0.0.0 --port 5174" 2>/dev/null || true
# also match by cwd logs
lsof -ti:8100 | xargs kill -9 2>/dev/null || true
lsof -ti:5174 | xargs kill -9 2>/dev/null || true
echo "已停止"
