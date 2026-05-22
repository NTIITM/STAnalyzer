"""
实验工具管理模块
提供实验工具的列表、调用和管理功能
"""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Mapping, Optional

from textmsa.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ExperimentTool:
    """实验工具定义"""
    name: str  # 工具名（service_id）
    display_name: str  # 显示名称
    description: str  # 工具描述
    parameters: Dict[str, Any]  # 参数schema（parameter_schema）
    category: Optional[str] = None  # 工具分类


class ToolCallContext:
    """工具调用上下文"""
    
    def __init__(self) -> None:
        self.selected_file_id: str | None = None
        self.metadata: dict[str, Any] = {}
    
    def summary(self) -> dict[str, Any]:
        """返回上下文的摘要信息"""
        return {
            "selected_file_id": self.selected_file_id,
            "metadata_keys": list(self.metadata.keys()) if self.metadata else [],
        }


class ExperimentTools:
    """实验工具管理器"""
    
    def __init__(self) -> None:
        """初始化工具管理器，从服务配置加载工具列表"""
        self._tools: Dict[str, ExperimentTool] = {}
        self._load_tools()
    
    def _load_tools(self) -> None:
        """从服务配置加载工具列表"""
        try:
            from textmsa.services.service.service_service import get_service_service
            from textmsa.services.data.mongodb_models import ServiceVisibility
            
            service_service = get_service_service()
            
            # 查询所有系统服务
            services = list(service_service.services_collection.find(
                {"visibility": ServiceVisibility.SYSTEM.value}
            ))
            
            for service in services:
                try:
                    tool = ExperimentTool(
                        name=service.get("service_id", ""),
                        display_name=service.get("name", ""),
                        description=service.get("description", ""),
                        parameters=service.get("parameter_schema", {}),
                        category=self._infer_category(service.get("service_id", "")),
                    )
                    if tool.name:
                        self._tools[tool.name] = tool
                except Exception as e:
                    logger.warning(f"加载服务 {service.get('service_id')} 失败: {e}")
                    continue
            
            logger.info(f"成功加载 {len(self._tools)} 个实验工具")
        
        except Exception as e:
            logger.warning(f"从服务配置加载工具失败: {e}，使用空工具列表", exc_info=True)
            self._tools = {}
    
    def _infer_category(self, service_id: str) -> str:
        """从service_id推断工具分类"""
        if "spatial" in service_id.lower():
            return "spatial_analysis"
        elif "clustering" in service_id.lower():
            return "clustering"
        elif "dge" in service_id.lower() or "differential" in service_id.lower():
            return "differential_expression"
        elif "enrichment" in service_id.lower():
            return "enrichment"
        else:
            return "other"
    
    def list_tools(self) -> List[ExperimentTool]:
        """列出所有可用的实验工具"""
        return list(self._tools.values())
    
    def get_tool(self, name: str) -> Optional[ExperimentTool]:
        """根据名称获取工具"""
        return self._tools.get(name)
    
    def build_context(
        self,
        task: Mapping[str, Any],
        state: Mapping[str, Any],
        default_task_id: str | None = None,
    ) -> ToolCallContext:
        """构建工具调用上下文"""
        context = ToolCallContext()
        
        # 从state中提取selected_file_id
        context.selected_file_id = state.get("selected_file_id")
        
        # 从task和state中提取metadata
        task_metadata = dict(task.get("metadata") or {})
        state_metadata = dict(state.get("metadata") or {})
        context.metadata = {**state_metadata, **task_metadata}
        
        # 如果metadata中有selected_file_id，也设置到context中
        if "selected_file_id" in context.metadata:
            context.selected_file_id = context.metadata["selected_file_id"]
        
        return context
    
    def execute_tool(
        self,
        name: str,
        params: Dict[str, Any],
        *,
        task: Mapping[str, Any] | None = None,
        state: Mapping[str, Any] | None = None,
        context: ToolCallContext | None = None,
    ) -> SimpleNamespace:
        """
        执行工具
        
        Args:
            name: 工具名称（service_id）
            params: 工具参数
            task: 任务信息（可选）
            state: 状态信息（可选）
            context: 工具调用上下文（可选）
        
        Returns:
            SimpleNamespace对象，包含output、metadata、artifacts属性
        """
        # 如果没有提供context，尝试从task和state构建
        if context is None:
            if task is not None and state is not None:
                context = self.build_context(task, state)
            else:
                context = ToolCallContext()
        
        # 获取工具定义
        tool = self.get_tool(name)
        if not tool:
            logger.warning(f"工具 {name} 不存在，返回空结果")
            return SimpleNamespace(
                output=f"工具 {name} 不存在或未加载",
                metadata={},
                artifacts=(),
            )
        
        # 调用服务执行工具
        try:
            from textmsa.services.service.service_service import get_service_service
            
            service_service = get_service_service()
            
            # 准备执行参数
            execution_params = {
                "service_id": name,
                "parameters": params,
            }
            
            # 如果有selected_file_id，添加到参数中
            if context.selected_file_id:
                execution_params["input_file_ids"] = [context.selected_file_id]
            
            # 执行服务
            input_file_ids = [context.selected_file_id] if context.selected_file_id else []
            user_id = state.get("user_id") if state else ""
            
            if not user_id:
                raise ValueError("执行工具需要提供user_id")
            
            result = service_service.execute_service(
                service_id=name,
                input_file_ids=input_file_ids,
                user_id=user_id,
                parameters=params,
                project_id=state.get("project_id") if state else None,
            )
            
            # 格式化输出
            output_text = self._format_output(result)
            
            # 提取artifacts（输出文件）
            artifacts = self._extract_artifacts(result)
            
            return SimpleNamespace(
                output=output_text,
                metadata={
                    "tool_name": name,
                    "tool_display_name": tool.display_name,
                    "params": params,
                },
                artifacts=artifacts,
            )
        
        except Exception as e:
            logger.error(f"执行工具 {name} 失败: {e}", exc_info=True)
            return SimpleNamespace(
                output=f"工具执行失败: {str(e)}",
                metadata={
                    "tool_name": name,
                    "error": str(e),
                },
                artifacts=(),
            )
    
    def _format_output(self, result: Dict[str, Any]) -> str:
        """格式化服务执行结果为文本输出"""
        if isinstance(result, dict):
            # 尝试提取文本输出
            if "output" in result:
                output = result["output"]
                if isinstance(output, str):
                    return output
                elif isinstance(output, dict):
                    # 如果是字典，尝试提取text字段
                    return output.get("text", str(output))
            
            # 如果没有output字段，尝试提取其他信息
            if "message" in result:
                return result["message"]
            
            # 默认返回字典的字符串表示
            return str(result)
        
        return str(result)
    
    def _extract_artifacts(self, result: Dict[str, Any]) -> tuple[str, ...]:
        """从执行结果中提取artifacts（输出文件ID）"""
        artifacts = []
        
        if isinstance(result, dict):
            # 尝试从不同字段提取文件ID
            if "output_file_ids" in result:
                artifacts.extend(result["output_file_ids"])
            elif "file_ids" in result:
                artifacts.extend(result["file_ids"])
            elif "files" in result:
                if isinstance(result["files"], list):
                    artifacts.extend([str(f) for f in result["files"]])
        
        return tuple(str(a) for a in artifacts)
    
    def call_tool(self, tool_name: str, params: Dict[str, Any]) -> str:
        """
        调用工具（简化版本，用于向后兼容）
        
        Args:
            tool_name: 工具名称
            params: 工具参数
        
        Returns:
            工具执行的文本结果
        """
        result = self.execute_tool(tool_name, params)
        return result.output


# 全局单例
_tools_instance: Optional[ExperimentTools] = None


def get_experiment_tools() -> ExperimentTools:
    """获取实验工具管理器单例"""
    global _tools_instance
    if _tools_instance is None:
        _tools_instance = ExperimentTools()
    return _tools_instance


__all__ = [
    "ExperimentTool",
    "ToolCallContext",
    "ExperimentTools",
    "get_experiment_tools",
]

