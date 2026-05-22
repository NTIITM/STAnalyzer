"""
Cascade deletion orchestration for analysis artifacts.
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from fastapi import HTTPException, status
from pymongo import MongoClient
from pymongo.collection import Collection

from textmsa.logging_config import get_logger
from textmsa.services.analysis.deletion_helper import (
    DeletionPlan,
    get_analysis_deletion_helper,
)
from textmsa.services.auth.auth_service import resolve_test_user_id
from textmsa.services.data.user_data_manager_mongodb import get_user_data_manager
from textmsa.services.file.file_manager import get_file_manager
from textmsa.settings import get_mongodb_config

logger = get_logger(__name__)


class CascadeDeletionService:
    """Builds and executes cascade deletion plans."""

    def __init__(self) -> None:
        self.user_data_manager = get_user_data_manager()
        self.file_manager = get_file_manager()
        self.deletion_helper = get_analysis_deletion_helper()

        mongo_config = get_mongodb_config()
        self.mongo_client = MongoClient(
            mongo_config["uri"],
            serverSelectionTimeoutMS=mongo_config["server_selection_timeout_ms"],
            connectTimeoutMS=mongo_config["connect_timeout_ms"],
            socketTimeoutMS=mongo_config["socket_timeout_ms"],
            maxPoolSize=mongo_config["max_pool_size"],
            minPoolSize=mongo_config["min_pool_size"],
        )
        self.database = self.mongo_client[mongo_config["database"]]
        self.service_executions_collection: Collection = self.database.service_executions

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def delete_files(
        self,
        *,
        user_id: str,
        root_file_ids: Sequence[str],
        project_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, object]:
        resolved_user_id = resolve_test_user_id(user_id)
        normalized_root_ids = self._normalize_ids(root_file_ids)
        if not normalized_root_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要提供一个文件ID",
            )

        project_scope = self._resolve_project_scope(
            user_id=resolved_user_id,
            target_ids=normalized_root_ids,
            explicit_project_ids=project_ids,
            subject_type="file",
        )

        plan = self.deletion_helper.collect_from_files(
            user_id=resolved_user_id,
            root_file_ids=normalized_root_ids,
            project_ids=project_scope or None,
        )

        deleted_files, failed_files = self._delete_files_in_plan(
            user_id=resolved_user_id,
            sanitized_user_id=self.user_data_manager._sanitize_user_id(resolved_user_id),
            plan=plan,
            project_scope=project_scope,
        )
        deleted_executions, failed_executions = self._delete_executions_in_plan(
            sanitized_user_id=self.user_data_manager._sanitize_user_id(resolved_user_id),
            plan=plan,
            user_id=resolved_user_id,
            project_scope=project_scope,
        )

        return {
            "deleted_file_ids": deleted_files,
            "deleted_execution_ids": deleted_executions,
            "failed_file_ids": failed_files,
            "failed_execution_ids": failed_executions,
            "project_scope": project_scope,
        }

    def delete_executions(
        self,
        *,
        user_id: str,
        root_execution_ids: Sequence[str],
        project_ids: Optional[Sequence[str]] = None,
    ) -> Dict[str, object]:
        resolved_user_id = resolve_test_user_id(user_id)
        normalized_exec_ids = self._normalize_ids(root_execution_ids)
        if not normalized_exec_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要提供一个执行ID",
            )

        project_scope = self._resolve_project_scope(
            user_id=resolved_user_id,
            target_ids=normalized_exec_ids,
            explicit_project_ids=project_ids,
            subject_type="execution",
        )

        plan = self.deletion_helper.collect_from_executions(
            user_id=resolved_user_id,
            root_execution_ids=normalized_exec_ids,
            project_ids=project_scope or None,
        )

        deleted_files, failed_files = self._delete_files_in_plan(
            user_id=resolved_user_id,
            sanitized_user_id=self.user_data_manager._sanitize_user_id(resolved_user_id),
            plan=plan,
            project_scope=project_scope,
        )
        deleted_executions, failed_executions = self._delete_executions_in_plan(
            sanitized_user_id=self.user_data_manager._sanitize_user_id(resolved_user_id),
            plan=plan,
            user_id=resolved_user_id,
            project_scope=project_scope,
        )

        return {
            "deleted_file_ids": deleted_files,
            "deleted_execution_ids": deleted_executions,
            "failed_file_ids": failed_files,
            "failed_execution_ids": failed_executions,
            "project_scope": project_scope,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _normalize_ids(self, ids: Sequence[str]) -> List[str]:
        normalized: List[str] = []
        seen: Set[str] = set()
        for item in ids or []:
            if not item:
                continue
            value = item.strip()
            if not value or value in seen:
                continue
            normalized.append(value)
            seen.add(value)
        return normalized

    def _resolve_project_scope(
        self,
        *,
        user_id: str,
        target_ids: Sequence[str],
        explicit_project_ids: Optional[Sequence[str]],
        subject_type: str,
    ) -> List[str]:
        if explicit_project_ids:
            sanitized = [
                self.user_data_manager._sanitize_project_id(pid)
                for pid in explicit_project_ids
                if pid and self.user_data_manager._sanitize_project_id(pid)
            ]
            return list(dict.fromkeys(sanitized))

        scope: Set[str] = set()
        finder = (
            self.user_data_manager.find_project_ids_by_file
            if subject_type == "file"
            else self.user_data_manager.find_project_ids_by_execution
        )
        for target_id in target_ids or []:
            scope.update(finder(user_id, target_id))
        return sorted(scope)

    def _delete_files_in_plan(
        self,
        *,
        user_id: str,
        sanitized_user_id: str,
        plan: DeletionPlan,
        project_scope: Sequence[str],
    ) -> Tuple[List[str], Dict[str, str]]:
        deleted_files: List[str] = []
        failures: Dict[str, str] = {}
        project_ids = list(project_scope or [])

        # ========== 新增：级联删除逻辑 ==========
        # 辅助函数：递归查找所有子文件
        def collect_children_recursive(file_id: str, visited: Set[str]) -> Set[str]:
            """递归收集所有子文件ID"""
            if file_id in visited:
                return set()
            visited.add(file_id)
            
            children = self.user_data_manager.get_file_children(file_id)
            child_file_ids = {c["child_file_id"] for c in children}
            
            all_children = child_file_ids.copy()
            for child_id in child_file_ids:
                all_children.update(collect_children_recursive(child_id, visited))
            
            return all_children
        
        # 第一步：收集所有需要删除的文件（包括子文件）
        all_files_to_delete = set(plan.file_order)
        visited = set()
        for file_id in plan.file_order:
            children = collect_children_recursive(file_id, visited)
            all_files_to_delete.update(children)
        
        # 第二步：扩展删除计划，包含所有子文件
        # 注意：需要确保不重复删除，且保持原有 execution 删除逻辑
        if all_files_to_delete != set(plan.file_order):
            # 需要重新收集删除计划，包含子文件
            # 但要注意：不要重复收集已经在 plan 中的文件
            additional_files = all_files_to_delete - set(plan.file_order)
            
            if additional_files:
                # 只对新增的文件收集删除计划
                extended_plan = self.deletion_helper.collect_from_files(
                    user_id=user_id,
                    root_file_ids=list(additional_files),
                    project_ids=project_scope or None,
                )
                # 合并执行顺序（保持原有顺序，然后添加子文件）
                extended_file_order = list(plan.file_order) + [
                    fid for fid in extended_plan.file_order 
                    if fid not in plan.file_order
                ]
            else:
                extended_file_order = plan.file_order
        else:
            extended_file_order = plan.file_order
        # ========== 级联删除逻辑结束 ==========

        # 第三步：按顺序删除文件
        # 注意：保持原有的 execution 删除逻辑不变
        for file_id in extended_file_order:
            try:
                # 检查文件是否已经在删除列表中（避免重复删除）
                if file_id in deleted_files:
                    logger.info(f"文件已在删除列表中，跳过: {file_id}")
                    continue
                
                file_info = self.user_data_manager.get_file_info(user_id, file_id)
                
                # 从项目中移除文件
                for project_id in project_ids:
                    try:
                        self.user_data_manager.remove_file_from_project(
                            user_id, project_id, file_id
                        )
                    except Exception as remove_err:
                        logger.warning(
                            "移除项目文件失败: %s/%s/%s (%s)",
                            user_id,
                            project_id,
                            file_id,
                            remove_err,
                        )

                if not file_info:
                    logger.info("文件已不存在，跳过删除: %s", file_id)
                    continue

                # ========== 新增：删除文件关系 ==========
                # 删除文件关系（作为父文件和子文件）
                try:
                    # 删除作为父文件的关系
                    self.user_data_manager.delete_file_relations(
                        parent_file_id=file_id,
                    )
                    # 删除作为子文件的关系
                    self.user_data_manager.delete_file_relations(
                        child_file_id=file_id,
                    )
                except Exception as rel_err:
                    logger.warning(
                        "删除文件关系失败: %s (%s)",
                        file_id,
                        rel_err,
                    )
                # ========== 关系删除结束 ==========
                
                # 删除MongoDB记录（保持原有逻辑）
                mongo_deleted = self.user_data_manager.delete_file(user_id, file_id)
                if not mongo_deleted:
                    failures[file_id] = "数据库记录删除失败"
                    continue

                # 删除物理文件（保持原有逻辑）
                self._delete_physical_file_if_needed(file_info, file_id)
                deleted_files.append(file_id)
                
            except Exception as exc:
                logger.error("删除文件失败: %s (%s)", file_id, exc, exc_info=True)
                failures[file_id] = str(exc)

        return deleted_files, failures

    def _delete_executions_in_plan(
        self,
        *,
        sanitized_user_id: str,
        plan: DeletionPlan,
        user_id: str,
        project_scope: Sequence[str],
    ) -> Tuple[List[str], Dict[str, str]]:
        deleted_executions: List[str] = []
        failures: Dict[str, str] = {}
        project_ids = list(project_scope or [])

        for execution_id in plan.execution_order:
            try:
                result = self.service_executions_collection.delete_one(
                    {"user_id": sanitized_user_id, "execution_id": execution_id}
                )
                if result.deleted_count == 0:
                    logger.info("执行记录不存在或已删除: %s", execution_id)
                    continue
                deleted_executions.append(execution_id)

                for project_id in project_ids:
                    try:
                        self.user_data_manager.remove_execution_from_project(
                            user_id, project_id, execution_id
                        )
                    except Exception as remove_err:
                        logger.warning(
                            "移除项目执行失败: %s/%s/%s (%s)",
                            user_id,
                            project_id,
                            execution_id,
                            remove_err,
                        )
            except Exception as exc:
                logger.error("删除执行记录失败: %s (%s)", execution_id, exc, exc_info=True)
                failures[execution_id] = str(exc)

        return deleted_executions, failures

    def delete_executions_by_input_file(
        self,
        *,
        user_id: str,
        input_file_id: str,
        project_ids: Optional[Sequence[str]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Delete service executions that directly use the given file as input.

        This is primarily used by higher-level services that need to remove
        executions when cleaning up derived child files while keeping the
        root file itself.
        """
        if not input_file_id:
            return [], {}

        resolved_user_id = resolve_test_user_id(user_id)
        sanitized_user_id = self.user_data_manager._sanitize_user_id(resolved_user_id)

        # Reuse project scope resolution logic so that we only touch executions
        # within the same project context as the file.
        project_scope = self._resolve_project_scope(
            user_id=resolved_user_id,
            target_ids=[input_file_id],
            explicit_project_ids=project_ids,
            subject_type="file",
        )

        try:
            # We intentionally reach into the helper's query method so that the
            # semantics stay consistent with the cascade deletion planning logic.
            executions = self.deletion_helper._find_executions_by_input(  # type: ignore[attr-defined]
                sanitized_user_id=sanitized_user_id,
                file_id=input_file_id,
                project_ids=list(project_scope) if project_scope else None,
            )
        except Exception as exc:
            logger.error(
                "查询执行记录失败（按输入文件）: user=%s file=%s (%s)",
                resolved_user_id,
                input_file_id,
                exc,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="查询执行记录失败",
            )

        deleted_executions: List[str] = []
        failures: Dict[str, str] = {}

        for exec_doc in executions:
            execution_id = exec_doc.get("execution_id")
            if not execution_id:
                continue

            try:
                result = self.service_executions_collection.delete_one(
                    {"user_id": sanitized_user_id, "execution_id": execution_id}
                )
                if result.deleted_count == 0:
                    logger.info("执行记录不存在或已删除（按输入文件）: %s", execution_id)
                    continue

                deleted_executions.append(execution_id)

                for project_id in project_scope:
                    try:
                        self.user_data_manager.remove_execution_from_project(
                            resolved_user_id, project_id, execution_id
                        )
                    except Exception as remove_err:
                        logger.warning(
                            "移除项目执行失败（按输入文件）: %s/%s/%s (%s)",
                            resolved_user_id,
                            project_id,
                            execution_id,
                            remove_err,
                        )
            except Exception as exc:
                logger.error(
                    "删除执行记录失败（按输入文件）: %s (%s)",
                    execution_id,
                    exc,
                    exc_info=True,
                )
                failures[execution_id] = str(exc)

        return deleted_executions, failures

    def _delete_physical_file_if_needed(self, file_info: Dict[str, object], file_id: str) -> None:
        status_value = str(file_info.get("analysis_status", "") or "").lower()
        file_path = file_info.get("file_path")

        if status_value not in {"uploaded", "completed"}:
            return
        if not file_path or not isinstance(file_path, str):
            return

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("物理文件已删除: %s", file_path)
        except Exception as exc:
            logger.warning("删除物理文件失败: %s (%s)", file_path, exc)

        try:
            self.file_manager.delete_file(file_id)
        except Exception:
            logger.debug("从FileManager映射中删除失败（可能已不存在）: %s", file_id)


_cascade_service: Optional[CascadeDeletionService] = None


def get_cascade_deletion_service() -> CascadeDeletionService:
    global _cascade_service
    if _cascade_service is None:
        _cascade_service = CascadeDeletionService()
    return _cascade_service

