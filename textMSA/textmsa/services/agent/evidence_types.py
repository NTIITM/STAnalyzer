"""
Lightweight evidence data structures and helpers used across the agent stack.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional


@dataclass
class Evidence:
    """Normalized evidence item used by downstream fusion / answer generation."""

    content: str
    source_type: str
    source_id: str
    priority: int
    confidence: float
    metadata: Dict[str, Any]


def summarize_text(text: Optional[str], max_length: int = 400) -> str:
    """Normalize whitespace and truncate long passages for logging / evidence."""
    if not text:
        return ""
    normalized = " ".join(text.strip().split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[:max_length].rstrip() + "..."


def _clamp_confidence(value: Optional[float], default: float) -> float:
    """Ensure confidence stays within [0, 1]."""
    if value is None:
        return default
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, numeric))


def make_evidence(
    *,
    content: str,
    source_type: str,
    source_id: str,
    priority: int,
    confidence: float = 0.6,
    metadata: Optional[Dict[str, Any]] = None,
) -> Evidence:
    """Factory helper for Evidence objects."""
    return Evidence(
        content=content,
        source_type=source_type,
        source_id=source_id,
        priority=priority,
        confidence=_clamp_confidence(confidence, confidence),
        metadata=dict(metadata or {}),
    )


def build_private_evidence_from_doc(doc: Mapping[str, Any]) -> Optional[Evidence]:
    """Create a simple evidence item from a private knowledge document."""
    text = (
        doc.get("text")
        or doc.get("content")
        or doc.get("snippet")
        or doc.get("summary")
        or ""
    )
    snippet = summarize_text(text)
    if not snippet:
        return None

    source_id = str(
        doc.get("id") or doc.get("doc_id") or doc.get("source_id") or "private_doc"
    )
    score = doc.get("score")
    confidence = _clamp_confidence(score, 0.7 if score else 0.6)
    metadata = {
        "source": doc.get("source") or "private",
        "score": score,
        "metadata": doc.get("metadata") or {},
    }
    return make_evidence(
        content=snippet,
        source_type="private_knowledge",
        source_id=source_id,
        priority=2,
        confidence=confidence,
        metadata=metadata,
    )


def build_experiment_evidence(
    result: Optional[str],
    tool_name: Optional[str],
) -> Optional[Evidence]:
    """Convert a raw experiment result into evidence."""
    snippet = summarize_text(result)
    if not snippet:
        return None
    return make_evidence(
        content=snippet,
        source_type="experiment",
        source_id=tool_name or "experiment",
        priority=3,
        confidence=0.75,
        metadata={"tool_name": tool_name},
    )


def build_literature_evidence(article: Mapping[str, Any]) -> Optional[Evidence]:
    """Create evidence from a PubMed / literature entry."""
    title = article.get("title") or article.get("paper_title") or ""
    abstract = article.get("abstract") or article.get("snippet") or ""
    combined = "\n".join(part for part in (title, abstract) if part)
    snippet = summarize_text(combined)
    if not snippet:
        return None

    source_id = str(
        article.get("pmid")
        or article.get("pubmed_id")
        or article.get("id")
        or article.get("source_id")
        or "literature"
    )
    metadata = {
        "title": title,
        "journal": article.get("journal") or article.get("source"),
        "year": article.get("year"),
    }
    return make_evidence(
        content=snippet,
        source_type="literature",
        source_id=source_id,
        priority=1,
        confidence=0.55,
        metadata=metadata,
    )


__all__ = [
    "Evidence",
    "build_experiment_evidence",
    "build_literature_evidence",
    "build_private_evidence_from_doc",
    "make_evidence",
    "summarize_text",
]

