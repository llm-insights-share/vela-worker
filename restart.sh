#!/bin/bash
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
"$PROJECT_DIR/stop.sh"
sleep 1
"$PROJECT_DIR/start.sh"
