"""Deterministic coverage mathematics. The language model never imports this to invent numbers."""

from app.engine.coverage import Inputs, calculate
from app.engine.parse import extract_message

__all__ = ["Inputs", "calculate", "extract_message"]
