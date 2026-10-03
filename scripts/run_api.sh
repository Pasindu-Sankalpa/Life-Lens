#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export CUDA_VISIBLE_DEVICES=""
export LIFELENS_LLM_BASE_URL="${LIFELENS_LLM_BASE_URL:-http://127.0.0.1:8000/v1}"
export LIFELENS_LLM_MODEL="${LIFELENS_LLM_MODEL:-Qwen/Qwen3.5-9B}"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
