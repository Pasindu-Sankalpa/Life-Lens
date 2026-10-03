"""OpenAI-compatible Qwen server on GPU 0.

vLLM 0.30 can load Qwen3.5-9B, but its Gated-DeltaNet and FlashInfer kernels
JIT-compile on first boot and fail on this machine (GCC 13 vs. the CUDA
headers, and gcc-12 has no cc1plus). This process serves the same model with
Transformers, still bound to GPU 0, behind the API the app already calls.
"""

from __future__ import annotations

import os

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForImageTextToText, AutoTokenizer

MODEL = os.environ.get("LIFELENS_LLM_MODEL", "Qwen/Qwen3.5-9B")
tokenizer = AutoTokenizer.from_pretrained(MODEL)
model = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16).to("cuda")
model.eval()

app = FastAPI(title="LifeLens Qwen")


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[dict] = Field(default_factory=list)
    temperature: float = 0
    max_tokens: int = 700
    tools: list | None = None
    tool_choice: object | None = None
    chat_template_kwargs: dict | None = None


@app.get("/v1/models")
def models() -> dict:
    return {"object": "list", "data": [{"id": MODEL, "object": "model"}]}


def _prompt(messages: list[dict], tools: list | None) -> str:
    prepared = [dict(message) for message in messages]
    instruction = (
        "Reply with one JSON object only, no markdown. Keys: "
        "profile_updates (object), dependents (list or null), "
        "scenario_patch (object or null), life_event (string or null), "
        "topics (list of strings), preface (short sentence with no dollar amounts). "
        "Do not calculate a coverage gap."
    )
    if tools:
        if prepared and prepared[0].get("role") == "system":
            prepared[0]["content"] = f"{prepared[0]['content']}\n\n{instruction}"
        else:
            prepared.insert(0, {"role": "system", "content": instruction})
    try:
        return tokenizer.apply_chat_template(
            prepared, tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
    except Exception:
        # Qwen3.5's template rejects a system turn anywhere but the start, and
        # some payloads trip that check. Fold everything into one user turn.
        folded = "\n\n".join(f"{message.get('role', 'user')}: {message.get('content', '')}" for message in prepared)
        return tokenizer.apply_chat_template(
            [{"role": "user", "content": folded}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )


@app.post("/v1/chat/completions")
def chat(body: ChatRequest) -> dict:
    prompt = _prompt(body.messages, body.tools)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    with torch.inference_mode():
        generated = model.generate(
            **inputs,
            max_new_tokens=body.max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    text = tokenizer.decode(generated[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True)
    return {
        "id": "lifelens",
        "object": "chat.completion",
        "model": MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
