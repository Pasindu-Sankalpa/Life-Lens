#!/usr/bin/env bash
# Self-hosted Qwen3.5-9B on GPU 0.
# vLLM 0.30 loads this model, but its Gated-DeltaNet and FlashInfer kernels
# JIT-compile at startup and fail on this host compiler. The server below is
# the same weights, the same OpenAI-compatible API, bound to GPU 0 only.
set -euo pipefail
cd "$(dirname "$0")/.."
export CUDA_VISIBLE_DEVICES=0
exec .venv/bin/python scripts/serve_transformers.py
