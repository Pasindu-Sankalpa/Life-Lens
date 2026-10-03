"""Named tools the model may call. Every number they return comes from the coverage engine or the knowledge base."""

from __future__ import annotations

from typing import Any

from app.engine.coverage import Inputs, apply_patch, calculate
from app.knowledge import keyword_search, semantic_search

TOOL_NAMES = (
    "update_customer_profile",
    "calculate_coverage_need",
    "simulate_scenario",
    "get_coverage_timeline",
    "retrieve_lincoln_guidance",
    "compare_coverage_types",
)


def calculate_coverage_need(inputs: Inputs) -> dict[str, Any]:
    return calculate(inputs)


def simulate_scenario(inputs: Inputs, patch: dict[str, Any]) -> dict[str, Any]:
    updated = apply_patch(inputs, patch)
    result = calculate(updated)
    return {"patch": patch, "calculation": result}


def get_coverage_timeline(calculation: dict[str, Any], year_offset: int | None = None) -> dict[str, Any]:
    timeline = calculation.get("timeline") or {}
    if year_offset is None:
        return timeline
    points = timeline.get("points") or []
    chosen = next((point for point in points if point["year_offset"] == year_offset), None)
    return {"horizon": timeline.get("horizon"), "point": chosen, "rows": timeline.get("rows"), "notes": {
        "debt": timeline.get("debt_note"),
        "existing": timeline.get("existing_note"),
    }}


def compare_coverage_types(calculation: dict[str, Any]) -> dict[str, Any]:
    return calculation.get("comparison") or {}


def stress_coverage(calculation: dict[str, Any], coverage: int) -> dict[str, Any] | None:
    samples = calculation.get("stress_samples") or []
    if not samples:
        return None
    return min(samples, key=lambda sample: abs(sample["coverage"] - coverage))


def retrieve_lincoln_guidance(query: str, chunks: list[dict[str, Any]], embedder, limit: int = 3) -> list[dict[str, Any]]:
    found = semantic_search(query, chunks, embedder, limit=limit)
    if not found:
        found = keyword_search(query, chunks, limit=limit)
    return [
        {
            "title": chunk["title"],
            "topic": chunk["topic"],
            "content": chunk["content"],
            "source_name": chunk["source_name"],
            "source_url": chunk["source_url"],
        }
        for chunk in found
    ]
