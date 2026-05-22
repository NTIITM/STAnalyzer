"""
Utility helpers to figure out which files/executions must be removed
when performing cascade deletions inside a project analysis tree.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Iterable, List, Optional, Set

from pymongo import MongoClient
from pymongo.collection import Collection

from textmsa.logging_config import get_logger
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
from textmsa.settings import get_mongodb_config

logger = get_logger(__name__)


@dataclass
class DeletionPlan:
    """Represents the items that should be deleted (and in what order)."""

    file_order: List[str]
    execution_order: List[str]


class AnalysisDeletionHelper:
    """
    Builds cascade deletion plans by traversing service execution graphs.

    The traversal strategy only walks "downstream" edges (file -> execution ->
    output file).  This matches the product requirement where deleting an
    original dataset should only impact derived artifacts.
    """

    def __init__(self):
        self.user_data_manager = get_user_data_manager()
        mongo_config = get_mongodb_config()
        self.client = MongoClient(
            mongo_config["uri"],
            serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
            connectTimeoutMS=mongo_config["connect_timeout_ms"],
            socketTimeoutMS=mongo_config["socket_timeout_ms"],
            maxPoolSize=mongo_config["max_pool_size"],
            minPoolSize=mongo_config["min_pool_size"],
        )
        self.db = self.client[mongo_config["database"]]
        self.service_executions_collection: Collection = self.db.service_executions

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def collect_from_files(
        self,
        *,
        user_id: str,
        root_file_ids: Iterable[str],
        project_ids: Optional[List[str]] = None,
    ) -> DeletionPlan:
        """Collects all descendant files/executions starting from file nodes."""
        sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
        return self._collect(
            sanitized_user_id=sanitized_user_id,
            seed_files=set(filter(None, root_file_ids or [])),
            seed_executions=set(),
            project_ids=project_ids,
        )

    def collect_from_executions(
        self,
        *,
        user_id: str,
        root_execution_ids: Iterable[str],
        project_ids: Optional[List[str]] = None,
    ) -> DeletionPlan:
        """
        Collects descendant files/executions starting from execution nodes.

        Root executions are always included in the deletion result so that
        callers can remove the execution itself after derived artifacts are gone.
        """
        sanitized_user_id = self.user_data_manager._sanitize_user_id(user_id)
        seed_execution_ids = set(filter(None, root_execution_ids or []))
        seed_files = self._collect_seed_files_from_executions(
            sanitized_user_id=sanitized_user_id,
            execution_ids=seed_execution_ids,
            project_ids=project_ids,
        )
        return self._collect(
            sanitized_user_id=sanitized_user_id,
            seed_files=seed_files,
            seed_executions=seed_execution_ids,
            project_ids=project_ids,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _collect(
        self,
        *,
        sanitized_user_id: str,
        seed_files: Set[str],
        seed_executions: Set[str],
        project_ids: Optional[List[str]],
    ) -> DeletionPlan:
        file_depth: Dict[str, int] = {}
        execution_depth: Dict[str, int] = {}
        queue: Deque[str] = deque()

        for file_id in seed_files:
            if file_id not in file_depth:
                file_depth[file_id] = 0
                queue.append(file_id)

        for execution_id in seed_executions:
            execution_depth[execution_id] = 0

        while queue:
            current_file_id = queue.popleft()
            current_depth = file_depth[current_file_id]
            executions = self._find_executions_by_input(
                sanitized_user_id=sanitized_user_id,
                file_id=current_file_id,
                project_ids=project_ids,
            )

            for exec_doc in executions:
                execution_id = exec_doc.get("execution_id")
                if not execution_id:
                    continue

                next_exec_depth = current_depth + 1
                if execution_id not in execution_depth or next_exec_depth > execution_depth[execution_id]:
                    execution_depth[execution_id] = next_exec_depth

                for output_file_id in self._extract_output_file_ids(exec_doc):
                    if output_file_id in file_depth:
                        continue
                    file_depth[output_file_id] = next_exec_depth + 1
                    queue.append(output_file_id)

        file_order = [fid for fid, _ in sorted(file_depth.items(), key=lambda item: item[1], reverse=True)]
        execution_order = [
            eid for eid, _ in sorted(execution_depth.items(), key=lambda item: item[1], reverse=True)
        ]

        return DeletionPlan(file_order=file_order, execution_order=execution_order)

    def _find_executions_by_input(
        self,
        *,
        sanitized_user_id: str,
        file_id: str,
        project_ids: Optional[List[str]],
    ) -> List[Dict]:
        if not file_id:
            return []

        query: Dict[str, object] = {
            "user_id": sanitized_user_id,
            "$or": [
                {"input_file_ids": file_id},
                {"input_file_id": file_id},
            ],
        }

        if project_ids:
            query["project_id"] = {"$in": list(project_ids)}

        return list(self.service_executions_collection.find(query))

    def _collect_seed_files_from_executions(
        self,
        *,
        sanitized_user_id: str,
        execution_ids: Set[str],
        project_ids: Optional[List[str]],
    ) -> Set[str]:
        if not execution_ids:
            return set()

        query: Dict[str, object] = {
            "user_id": sanitized_user_id,
            "execution_id": {"$in": list(execution_ids)},
        }
        if project_ids:
            query["project_id"] = {"$in": list(project_ids)}

        seed_files: Set[str] = set()
        for exec_doc in self.service_executions_collection.find(query):
            execution_id = exec_doc.get("execution_id")
            if execution_id not in execution_ids:
                continue
            for output_file_id in self._extract_output_file_ids(exec_doc):
                seed_files.add(output_file_id)

        return seed_files

    @staticmethod
    def _extract_output_file_ids(exec_doc: Dict) -> List[str]:
        output_ids: List[str] = []
        primary_output = exec_doc.get("output_file_id")
        if primary_output:
            output_ids.append(primary_output)

        list_outputs = exec_doc.get("output_file_ids") or []
        for output_id in list_outputs:
            if output_id and output_id not in output_ids:
                output_ids.append(output_id)

        return output_ids


_deletion_helper: Optional[AnalysisDeletionHelper] = None


def get_analysis_deletion_helper() -> AnalysisDeletionHelper:
    """Singleton accessor used by services that need deletion plans."""
    global _deletion_helper
    if _deletion_helper is None:
        _deletion_helper = AnalysisDeletionHelper()
    return _deletion_helper


