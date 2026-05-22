"""
Validation and normalization of entities and relations extracted from text.

This adds rule constraints similar to the KG_workfolw project while keeping
the implementation local to textMSA.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from enum import Enum
from pydantic import BaseModel, Field, ValidationError

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


class EntityType(str, Enum):
    Gene = "Gene"
    Protein = "Protein"
    Disease = "Disease"
    Pathway = "Pathway"
    CellularProcess = "CellularProcess"
    MetabolicSignal = "MetabolicSignal"
    FunctionalMolecule = "FunctionalMolecule"
    Model = "Model"
    Intervention = "Intervention"


class RelationType(str, Enum):
    PROMOTE = "PROMOTE"
    INDUCE_ELEVATION_OF = "INDUCE_ELEVATION_OF"
    ACTIVATE = "ACTIVATE"
    UPREGULATE = "UPREGULATE"
    ELEVATE = "ELEVATE"
    PROMOTE_ACCUMULATION_OF = "PROMOTE_ACCUMULATION_OF"
    AUGMENT = "AUGMENT"
    TEND_TO_INDUCE = "TEND_TO_INDUCE"
    TRIGGER = "TRIGGER"
    DO_NOT_NOTABLY_DOWNREGULATE = "DO_NOT_NOTABLY_DOWNREGULATE"
    MAY_CONSTITUTIVELY_SUPPORT = "MAY_CONSTITUTIVELY_SUPPORT"
    MAY_PROMOTE = "MAY_PROMOTE"
    MAY_DELAY = "MAY_DELAY"


RELATION_SYNONYMS = {
    "ENHANCE": RelationType.PROMOTE,
    "INCREASE": RelationType.UPREGULATE,
    "RAISE": RelationType.ELEVATE,
}


class EvidenceSentence(BaseModel):
    sentence: str
    pmid: str = Field(default="Unknown")


class Entity(BaseModel):
    name: str
    type: EntityType
    aliases: List[str] = Field(default_factory=list)
    source_sentence: str = ""
    primary_name: str
    source_pmids: List[str] = Field(default_factory=list)


class Relation(BaseModel):
    head: str
    head_type: EntityType
    tail: str
    tail_type: EntityType
    relation: RelationType
    sentence: str
    confidence: float = 0.8
    head_alias_used: str | None = None
    tail_alias_used: str | None = None
    evidence_sentences: List[EvidenceSentence] = Field(default_factory=list)


class Extraction(BaseModel):
    entities: List[Entity]
    relations: List[Relation]


def _normalize_relation_type(value: str) -> RelationType:
    key = (value or "").upper().strip()
    try:
        return RelationType[key]
    except Exception:
        mapped = RELATION_SYNONYMS.get(key)
        if mapped:
            return mapped
        raise


def normalize_extraction(raw: Dict[str, Any]) -> Tuple[List[Entity], List[Relation]]:
    """
    Normalize and validate raw extraction into Entity/Relation lists.

    - Enforce allowed entity/relation types
    - Ensure head/tail refer to existing entity names
    - Normalize relation synonyms
    """
    entities: List[Entity] = []
    relations: List[Relation] = []

    # build entity name set for linking
    name_set: set[str] = set()

    for ent in raw.get("entities", []) or []:
        try:
            etype = EntityType(ent.get("type"))
            entity = Entity(
                name=ent.get("name"),
                type=etype,
                aliases=list(ent.get("aliases", []) or []),
                source_sentence=ent.get("source_sentence", ""),
                primary_name=ent.get("primary_name") or ent.get("name", ""),
                source_pmids=list(ent.get("source_pmids", []) or []),
            )
            entities.append(entity)
            name_set.add(entity.name)
        except Exception as exc:
            logger.warning("Invalid entity dropped: %s | error=%s", ent, exc)

    for rel in raw.get("relations", []) or []:
        try:
            rtype = _normalize_relation_type(rel.get("relation", ""))
            head_name = rel.get("head")
            tail_name = rel.get("tail")
            if head_name not in name_set or tail_name not in name_set:
                raise ValueError("Relation references unknown entity name")
            relation = Relation(
                head=head_name,
                head_type=EntityType(rel.get("head_type")),
                tail=tail_name,
                tail_type=EntityType(rel.get("tail_type")),
                relation=rtype,
                sentence=rel.get("sentence", ""),
                confidence=float(rel.get("confidence", 0.8)),
                head_alias_used=rel.get("head_alias_used"),
                tail_alias_used=rel.get("tail_alias_used"),
                evidence_sentences=[EvidenceSentence(**ev) for ev in (rel.get("evidence_sentences") or [])],
            )
            relations.append(relation)
        except Exception as exc:
            logger.warning("Invalid relation dropped: %s | error=%s", rel, exc)

    return entities, relations

