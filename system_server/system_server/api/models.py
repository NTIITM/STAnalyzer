"""
API 数据模型
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

class ServiceInfo(BaseModel):
    """服务信息"""
    service_id: str = Field(..., description="服务 ID")
    name: str = Field(..., description="服务名称")
    description: Optional[str] = Field(None, description="服务描述")
    version: str = Field("1.0.0", description="版本号")
    baseurl: str = Field(..., description="服务基础 URL")
    port: int = Field(..., description="服务端口")
    service_suffix: Optional[str] = Field(None, description="服务端点后缀")
    download_suffix: Optional[str] = Field(None, description="下载端点后缀")
    parameter_template: Optional[Dict[str, Any]] = Field(None, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(None, description="参数模式")
    accepted_files: Optional[Dict[str, Any]] = Field(None, description="接受的输入文件配置，格式：{filename: {file_type_ids: [...], description: ...}}")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出配置")
    status: str = Field("stopped", description="服务状态: running, stopped, error")
    docker: bool = Field(False, description="是否使用 Docker")

    class Config:
        json_schema_extra = {
            "example": {
                "service_id": "single-cell-clustering",
                "name": "单细胞聚类服务",
                "description": "单细胞数据聚类分析",
                "version": "1.0.0",
                "baseurl": "http://localhost:42903",
                "port": 42903,
                "service_suffix": "/api/cluster",
                "download_suffix": "/api/download",
                "status": "running",
                "docker": False
            }
        }

class ServiceListResponse(BaseModel):
    """服务列表响应"""
    services: List[ServiceInfo]
    total: int

class ServiceStatusResponse(BaseModel):
    """服务状态响应"""
    service_id: str
    status: str
    message: Optional[str] = None

class ServiceActionResponse(BaseModel):
    """服务操作响应"""
    service_id: str
    action: str
    success: bool
    message: str

class ServiceLogsResponse(BaseModel):
    """服务日志响应"""
    success: bool
    service_name: Optional[str] = None
    container_name: Optional[str] = None
    logs: str = ""
    error: Optional[str] = None
    tail: Optional[int] = None
    follow: Optional[bool] = None

