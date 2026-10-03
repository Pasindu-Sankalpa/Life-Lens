"""Self-hosted Qwen client. The model may extract and explain. It may not invent coverage math."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

LLM_BASE_URL = os.environ.get("LIFELENS_LLM_BASE_URL", "http://127.0.0.1:8000/v1")
LLM_MODEL = os.environ.get("LIFELENS_LLM_MODEL", "Qwen/Qwen3.5-9B")
LLM_API_KEY = os.environ.get("LIFELENS_LLM_API_KEY", "local")

_STATUS: dict[str, Any] = {"checked_at": 0.0, "payload": None}

SYSTEM_PROMPT = """You are the conversational interface for LincolnLens, a life-insurance needs analysis.

Your job is to understand the user's financial situation, identify missing information, and explain results clearly.

You MUST NOT calculate coverage amounts, gaps, premiums, or years of income a face amount would buy.
All calculations are performed by tools. If you need a number, call a tool.

Never invent:
- coverage amounts
- premiums
- policy guarantees
- product features that are not in retrieved notes
- interest rates
- tax consequences

Ask at most one or two questions at a time.
Use calm, non-alarming language.
Do not say the user might die. Talk about what coverage protects.

If information is missing, leave it out of profile_updates. Do not assume a value.
When you do extract a number, it must be a number the user actually wrote.

Distinguish, in your own reasoning only:
FACTS PROVIDED BY THE USER
ASSUMPTIONS
CALCULATED RESULTS
EDUCATIONAL INFORMATION

Tools:
- update_customer_profile: record facts the user just stated
- simulate_scenario: record a what-if change, without applying it permanently
- calculate_coverage_need: ask the engine for the current gap
- get_coverage_timeline: read the year-by-year need
- retrieve_lincoln_guidance: read approved educational notes
- compare_coverage_types: read the term versus permanent comparison for this household

You may propose facts. You may not save them. Return proposals the backend will validate:

{"field": "annual_income", "value": 110000, "evidence": "I make about 110k", "confidence": 0.9}

The evidence string must be copied from the user's message. If you cannot point at the words, omit the proposal.

Return tool calls or one JSON object with proposals, profile_updates, scenario_patch, life_event, topics, and preface.
If you also write prose, do not put dollar amounts in it.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_customer_profile",
            "description": "Record facts the user explicitly stated. Omit unknown fields.",
            "parameters": {
                "type": "object",
                "properties": {
                    "age": {"type": "integer"},
                    "partner": {"type": "boolean"},
                    "annual_income": {"type": "number"},
                    "income_replacement_years": {"type": "integer"},
                    "income_replacement_percent": {"type": "number"},
                    "mortgage_balance": {"type": "number"},
                    "mortgage_years_remaining": {"type": "integer"},
                    "other_debt": {"type": "number"},
                    "existing_employer_coverage": {"type": "number"},
                    "existing_personal_coverage": {"type": "number"},
                    "savings_allocated": {"type": "number"},
                    "lifelong_legacy_goal": {"type": "number"},
                    "other_needs": {"type": "number"},
                    "include_education": {"type": "boolean"},
                    "cash_value_interest": {"type": "boolean"},
                    "dependents": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "age": {"type": "integer"},
                                "label": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_scenario",
            "description": "Preview a what-if change. Do not calculate the resulting dollars.",
            "parameters": {
                "type": "object",
                "properties": {
                    "income_replacement_years": {"type": "integer"},
                    "income_replacement_percent": {"type": "number"},
                    "annual_income": {"type": "number"},
                    "mortgage_balance": {"type": "number"},
                    "other_debt": {"type": "number"},
                    "existing_employer_coverage": {"type": "number"},
                    "existing_personal_coverage": {"type": "number"},
                    "include_education": {"type": "boolean"},
                    "lifelong_legacy_goal": {"type": "number"},
                    "clear_education": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_coverage_need",
            "description": "Run the deterministic coverage engine on the saved profile.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_coverage_timeline",
            "description": "Read how the protection need changes over time.",
            "parameters": {
                "type": "object",
                "properties": {"year_offset": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_lincoln_guidance",
            "description": "Retrieve educational notes grounded in Lincoln's public product categories.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_coverage_types",
            "description": "Read the personalized term versus permanent/whole-life comparison.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def llm_status(force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force and _STATUS["payload"] is not None and now - _STATUS["checked_at"] < 8:
        return _STATUS["payload"]
    payload: dict[str, Any] = {
        "reachable": False,
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
        "gpu": "GPU 0",
    }
    try:
        response = httpx.get(f"{LLM_BASE_URL}/models", timeout=1.5)
        payload["reachable"] = response.status_code == 200
        if response.status_code == 200:
            body = response.json()
            names = [item.get("id") for item in body.get("data", [])]
            payload["served_models"] = names
    except Exception as exc:  # noqa: BLE001
        payload["detail"] = str(exc)
    _STATUS["checked_at"] = now
    _STATUS["payload"] = payload
    return payload


def interpret(user_text: str, profile: dict[str, Any], missing: list[str]) -> dict[str, Any] | None:
    """Ask Qwen for tool calls or JSON. Returns None when the server is down."""

    if not llm_status().get("reachable"):
        return None
    user_payload = {
        "profile": profile,
        "missing": missing,
        "message": user_text,
        "instruction": "Call tools for any fact or what-if in the message. Do not compute a coverage amount.",
    }
    try:
        response = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "temperature": 0,
                "max_tokens": 700,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_payload)},
                ],
                "tools": TOOLS,
                "tool_choice": "auto",
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=90,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "tool_calls": [], "preface": ""}
    return _normalize_message(message)


def explain_with_notes(question: str, notes: list[dict[str, Any]], allowed_numbers: set[int]) -> str:
    if not notes or not llm_status().get("reachable"):
        return ""
    packet = [{"title": note["title"], "content": note["content"], "source": note["source_url"]} for note in notes]
    try:
        response = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "temperature": 0.2,
                "max_tokens": 420,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Explain the question using only the supplied notes. "
                            "Do not add product features, premiums, tax advice, or coverage recommendations. "
                            "Do not invent dollar amounts. Two short paragraphs."
                        ),
                    },
                    {"role": "user", "content": json.dumps({"question": question, "notes": packet})},
                ],
                "chat_template_kwargs": {"enable_thinking": False},
            },
            timeout=90,
        )
        response.raise_for_status()
        text = _strip_think(response.json()["choices"][0]["message"].get("content") or "")
    except Exception:
        return ""
    if _invented_money(text, allowed_numbers):
        return ""
    return text.strip()


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    tool_calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        name = function.get("name")
        if name not in TOOL_NAMES:
            continue
        raw = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            arguments = {}
        tool_calls.append({"name": name, "arguments": arguments or {}})
    content = _strip_think(message.get("content") or "")
    parsed = _loose_json(content)
    if not tool_calls and isinstance(parsed, dict):
        updates = parsed.get("profile_updates") or parsed.get("update_customer_profile") or {}
        proposals = parsed.get("proposals") or []
        if updates or parsed.get("dependents") or proposals:
            tool_calls.append({
                "name": "update_customer_profile",
                "arguments": {**updates, "dependents": parsed.get("dependents"), "proposals": proposals},
            })
        scenario = parsed.get("scenario_patch") or parsed.get("simulate_scenario")
        if isinstance(scenario, dict) and scenario:
            tool_calls.append({"name": "simulate_scenario", "arguments": scenario})
        if parsed.get("life_event"):
            tool_calls.append({"name": "life_event", "arguments": {"event": parsed.get("life_event")}})
        topics = parsed.get("topics") or []
        if topics:
            tool_calls.append({"name": "retrieve_lincoln_guidance", "arguments": {"query": " ".join(topics)}})
    preface = ""
    if isinstance(parsed, dict):
        preface = str(parsed.get("preface") or "")
    elif content and not content.startswith("{"):
        preface = content
    return {"tool_calls": tool_calls, "preface": preface, "error": None}


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _loose_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    fenced = re.sub(r"^```(?:json)?", "", text.strip()).strip()
    fenced = re.sub(r"```$", "", fenced).strip()
    start = fenced.find("{")
    end = fenced.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(fenced[start : end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _invented_money(text: str, allowed: set[int]) -> bool:
    for raw in re.findall(r"\$\s*\d[\d,]*(?:\.\d+)?\s*[kKmM]?", text):
        number = raw.lower().replace("$", "").replace(",", "").strip()
        multiplier = 1
        if number.endswith("k"):
            multiplier = 1_000
            number = number[:-1]
        elif number.endswith("m"):
            multiplier = 1_000_000
            number = number[:-1]
        try:
            value = int(round(float(number) * multiplier))
        except ValueError:
            return True
        if value not in allowed:
            return True
    return False
