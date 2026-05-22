# """
# Persistence helpers to insert extracted knowledge into Neo4j.

# This module integrates with textMSA.graph.neo4j_client.Neo4jClient and applies
# basic upsert logic for entities, relations, and publication support.
# """

# from __future__ import annotations

# from typing import Any, Dict, List
# from datetime import datetime

# from textmsa.graph.neo4j_client import Neo4jClient
# from textmsa.knowledge.validation import Entity, Relation
# from textmsa.logging_config import get_logger

# logger = get_logger(__name__)


# def _collect_support_pmids(rel: Relation) -> List[str]:
#     pmids = []
#     for ev in rel.evidence_sentences:
#         if ev.pmid and ev.pmid not in pmids:
#             pmids.append(ev.pmid)
#     return pmids


# def persist_entities_and_relations(
#     client: Neo4jClient,
#     entities: List[Entity],
#     relations: List[Relation],
# ) -> None:
#     # Upsert entities
#     for ent in entities:
#         if not client.has_node(ent.type.value, ent.name):
#             client.add_node(ent.type.value, ent.name, {
#                 "name": ent.name,
#                 "primary_name": ent.primary_name,
#                 "aliases": ent.aliases,
#                 "source_sentence": ent.source_sentence,
#                 "source_pmids": ent.source_pmids,
#                 "created_at": datetime.now().isoformat(),
#                 "last_updated": datetime.now().isoformat(),
#             })
#         else:
#             # merge aliases and source_pmids
#             client.add_alias_to_node(ent.type.value, ent.name, ent.aliases)
#             # accumulate pmids
#             client.update_node_properties(ent.type.value, ent.name, {
#                 "source_pmids": ent.source_pmids,
#                 "last_updated": datetime.now().isoformat(),
#             })

#     # Upsert relations
#     for rel in relations:
#         support_pmids = _collect_support_pmids(rel)
#         props = {
#             "confidence": rel.confidence,
#             "supporting_publications": support_pmids,
#             "sentence": rel.sentence,
#             "head_alias_used": rel.head_alias_used,
#             "tail_alias_used": rel.tail_alias_used,
#             "created_at": datetime.now().isoformat(),
#             "last_updated": datetime.now().isoformat(),
#         }
#         client.add_edge(
#             rel.head_type.value, rel.head,
#             rel.tail_type.value, rel.tail,
#             rel.relation.value,
#             props,
#         )


# def persist_publications(client: Neo4jClient, pubmed_results: List[Dict[str, Any]]) -> None:
#     for art in pubmed_results:
#         pmid = art.get("pmid") or art.get("PMID")
#         if not pmid:
#             continue
#         client.add_node("Publication", pmid, {
#             "pmid": pmid,
#             "title": art.get("title", ""),
#             "authors": art.get("authors", []),
#             "journal": art.get("journal", ""),
#             "pub_date": art.get("pub_date", ""),
#             "created_at": datetime.now().isoformat(),
#             "last_updated": datetime.now().isoformat(),
#         })

