"""
Shared JSON utilities used across the textMSA project.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


def clean_json_response(text: str) -> str:
    """
    Strip markdown fences or stray characters surrounding JSON payloads.
    """
    if not text:
        return ""

    json_block_pattern = r"```(?:json)?\s*(.*?)\s*```"
    matches = re.findall(json_block_pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()

    json_pattern = r"\{.*\}"
    matches = re.findall(json_pattern, text, re.DOTALL)
    if matches:
        return matches[0].strip()

    return text.strip()


def safe_json_parse(raw_text: str) -> Dict[str, Any]:
    """
    Safely parse JSON text, cleaning markdown wrappers when necessary.
    """
    if not raw_text:
        return {}

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        logger.debug("Initial JSON parse failed; attempting to clean content.")

    # Attempt to extract code fences
    match = re.search(r"```json\s*(.*?)\s*```", raw_text, re.DOTALL)
    if match:
        cleaned = match.group(1)
    else:
        start_idx = raw_text.find("{")
        end_idx = raw_text.rfind("}")
        cleaned = raw_text[start_idx : end_idx + 1] if start_idx != -1 and end_idx != -1 else raw_text

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Failed to parse JSON content. Returning empty dict.")
        logger.debug("Original content: %s", cleaned)
        return {}

