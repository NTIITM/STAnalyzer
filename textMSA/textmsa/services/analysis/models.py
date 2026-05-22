"""
分析流程数据模型
用于存储文件分析流程的树形结构
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class FileStatus(str, Enum):
    """文件状态枚举"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    IDLE = "idle"
    RUNNING = "running"


class AlgorithmStatus(str, Enum):
    """算法执行状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileNodeModel(BaseModel):
    """文件节点模型"""
    model_config = ConfigDict(extra="allow")
    
    id: str = Field(..., description="文件节点唯一标识")
    fileName: str = Field(..., description="文件名")
    fileType: str = Field(..., description="文件类型")
    description: Optional[str] = Field(None, description="文件描述")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    path: Optional[str] = Field(None, description="文件路径")
    url: Optional[str] = Field(None, description="文件下载URL")
    status: Optional[FileStatus] = Field(None, description="文件状态")
    createdAt: Optional[str] = Field(None, description="创建时间")
    updatedAt: Optional[str] = Field(None, description="更新时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="文件元数据")
    children: Optional[List['FileNodeModel']] = Field(None, description="子文件节点列表")
    algorithm: Optional['AlgorithmEdgeModel'] = Field(None, description="关联的算法信息")


class AlgorithmEdgeModel(BaseModel):
    """算法边模型"""
    model_config = ConfigDict(extra="allow")
    
    algorithmId: str = Field(..., description="算法ID")
    algorithmName: str = Field(..., description="算法名称")
    description: Optional[str] = Field(None, description="算法描述")
    algorithmType: Optional[str] = Field(None, description="算法类型")
    icon: Optional[str] = Field(None, description="算法图标")
    keyParams: Optional[Dict[str, Any]] = Field(None, description="关键参数")
    status: AlgorithmStatus = Field(..., description="执行状态")
    startTime: Optional[str] = Field(None, description="开始时间")
    endTime: Optional[str] = Field(None, description="结束时间")
    duration: Optional[int] = Field(None, description="执行耗时（毫秒）")
    error: Optional[str] = Field(None, description="错误信息")
    summary: Optional[str] = Field(None, description="执行结果摘要")


# 解决前向引用
FileNodeModel.model_rebuild()


class AnalysisTreeModel(BaseModel):
    """分析流程树模型"""
    model_config = ConfigDict(extra="allow")
    
    fileId: str = Field(..., description="原始文件ID")
    user_id: str = Field(..., description="用户ID")
    root: FileNodeModel = Field(..., description="根文件节点")
    createdAt: Optional[str] = Field(None, description="创建时间")
    updatedAt: Optional[str] = Field(None, description="更新时间")
    status: Optional[str] = Field(None, description="当前执行状态")
    progress: Optional[int] = Field(None, description="总体进度（0-100）")
    totalNodes: Optional[int] = Field(None, description="总文件节点数")
    completedNodes: Optional[int] = Field(None, description="已完成文件节点数")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump(exclude_none=True)

