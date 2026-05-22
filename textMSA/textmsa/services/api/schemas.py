"""
API请求和响应模型（Pydantic）
"""
from typing import Optional, List, Dict, Any, Union, Literal
from pydantic import BaseModel, Field, EmailStr, validator, model_validator, ConfigDict, AliasChoices
from textmsa.services.data.mongodb_models import ProjectKnowledgeConfig, ProjectServiceConfig, ServiceOutputConfig


# ============= 用户相关模型 =============

class UserRegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: EmailStr = Field(..., description="邮箱")
    
    @validator('username')
    def validate_username(cls, v):
        """验证用户名：不能为空，trim后长度1-50字符"""
        if not v or not v.strip():
            raise ValueError("用户名不能为空")
        trimmed = v.strip()
        if len(trimmed) < 1 or len(trimmed) > 50:
            raise ValueError("用户名长度必须在1-50字符之间")
        return trimmed
    
    @validator('password')
    def validate_password(cls, v):
        """验证密码：不能为空，长度至少6位"""
        if not v or not v.strip():
            raise ValueError("密码不能为空")
        trimmed = v.strip()
        if len(trimmed) < 6:
            raise ValueError("密码长度至少6位")
        if len(trimmed) > 100:
            raise ValueError("密码长度不能超过100位")
        return trimmed


class UserLoginRequest(BaseModel):
    """用户登录请求"""
    token: Optional[str] = Field(None, description="token字符串（可选，如果提供则直接验证并登录）")
    username: Optional[str] = Field(None, description="用户名（可选，如果提供则忽略）")
    password: Optional[str] = Field(None, description="密码（可选，如果提供则忽略）")
    
    @validator('token')
    def validate_token(cls, v):
        """验证token：如果提供，则trim"""
        if v is not None:
            return v.strip() if v.strip() else None
        return v
    
    @validator('username', 'password')
    def validate_optional_fields(cls, v):
        """验证可选字段：如果提供，则trim（但会被忽略）"""
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(None, description="邮箱")


class UserProfileUpdateRequest(BaseModel):
    """更新用户信息请求"""
    username: Optional[str] = Field(None, min_length=1, max_length=50, description="新的用户名")
    email: Optional[str] = Field(None, description="新的邮箱地址")

    @validator('username')
    def validate_username(cls, v):
        """验证用户名：如果提供，则trim并验证长度"""
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("用户名不能为空")
            if len(cleaned) < 1 or len(cleaned) > 50:
                raise ValueError("用户名长度必须在1-50字符之间")
            return cleaned
        return v

    @validator('email')
    def normalize_email(cls, v):
        """规范化邮箱：trim并转为小写，允许 .local 域名"""
        if v is not None and isinstance(v, str):
            v = v.strip().lower()
            # 允许 .local 域名（系统内部使用的默认邮箱格式）
            if v.endswith('@default.local'):
                return v
            # 对于其他邮箱，进行基本格式验证
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError("邮箱格式无效")
            return v
        return v

    @model_validator(mode='after')
    def ensure_at_least_one(self):
        """确保至少提供一个字段（用户名或邮箱）"""
        if not self.username and not self.email:
            raise ValueError("至少需要提供用户名或邮箱其中之一")
        return self


class UserPasswordChangeRequest(BaseModel):
    """修改密码请求"""
    current_password: str = Field(..., min_length=6, description="当前密码")
    new_password: str = Field(..., min_length=6, description="新密码")

    @validator('current_password', 'new_password')
    def validate_password(cls, v):
        """验证密码：不能为空，长度至少6位"""
        if not v or not v.strip():
            raise ValueError("密码不能为空")
        trimmed = v.strip()
        if len(trimmed) < 6:
            raise ValueError("密码长度至少6位")
        return trimmed

    @validator('new_password')
    def passwords_not_same(cls, v, values):
        """验证新密码不能与当前密码相同"""
        current = values.get('current_password')
        if current and current == v:
            raise ValueError("新密码不能与当前密码相同")
        return v


class UserLoginResponse(BaseModel):
    """用户登录响应"""
    token: str = Field(..., description="token字符串")
    user_id: str = Field(..., description="用户ID")
    username: Optional[str] = Field(None, description="用户名")


class UserRegisterResponse(BaseModel):
    """用户注册响应"""
    user_id: str = Field(..., description="用户ID")


# ============= 文件类型模型 =============


class FileTypeBase(BaseModel):
    """文件类型基础字段"""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=100, description="唯一名称/slug")
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="展示名称",
        validation_alias=AliasChoices("display_name", "displayName"),
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="类型描述",
    )
    category: Optional[str] = Field(
        None,
        max_length=200,
        description="类型分类",
    )
    extensions: List[str] = Field(
        ...,
        min_length=1,
        description="允许的扩展名（含点）",
    )

# TODO：可能需要修改
class FileTypeResponse(FileTypeBase):
    """文件类型响应"""

    id: Optional[str] = Field(
        default=None,
        description="文件类型ID（兼容 metadata 块）",
    )
    file_type_id: Optional[str] = Field(
        default=None,
        description="文件类型ID",
        validation_alias=AliasChoices("file_type_id", "fileTypeId"),
        serialization_alias="file_type_id",
    )
    created_at: Optional[str] = Field(
        default=None,
        description="创建时间",
        validation_alias=AliasChoices("created_at", "createdAt"),
        serialization_alias="created_at",
    )
    updated_at: Optional[str] = Field(
        default=None,
        description="更新时间",
        validation_alias=AliasChoices("updated_at", "updatedAt"),
        serialization_alias="updated_at",
    )

    @model_validator(mode="after")
    def sync_identifiers(self):
        """保持 id 与 file_type_id 一致"""
        if not self.id and self.file_type_id:
            self.id = self.file_type_id
        if not self.file_type_id and self.id:
            self.file_type_id = self.id
        return self


class FileTypeCreateRequest(FileTypeBase):
    """创建文件类型请求"""
    pass


class FileTypeUpdateRequest(BaseModel):
    """更新文件类型请求"""

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="唯一名称/slug",
    )
    display_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="展示名称",
        validation_alias=AliasChoices("display_name", "displayName"),
        serialization_alias="display_name",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="类型描述",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=200,
        description="类型分类",
    )
    extensions: Optional[List[str]] = Field(
        default=None,
        description="允许的扩展名（含点）",
    )


class FileTypeListResponse(BaseModel):
    """文件类型列表响应"""

    items: List[FileTypeResponse] = Field(default_factory=list, description="文件类型列表")
    total: int = Field(0, description="总数")

    @model_validator(mode="after")
    def populate_total(self):
        if not self.total:
            self.total = len(self.items)
        return self


# ============= 文件相关模型 =============

class FileUploadRequest(BaseModel):
    """
    文件上传请求（用于文档和验证）
    
    注意：实际文件上传使用 multipart/form-data，文件通过 UploadFile 参数传递。
    此 schema 主要用于 API 文档和验证 project_id 参数。
    """
    project_id: Optional[str] = Field(
        None,
        alias="projectId",
        description="项目ID（可选，如果提供，上传后自动添加到项目）"
    )
    file_type_id: str = Field(
        ...,
        description="文件类型ID",
        validation_alias=AliasChoices("file_type_id", "fileTypeId"),
        serialization_alias="file_type_id",
    )
    
    class Config:
        populate_by_name = True  # 允许使用别名和原始名称


class FileUploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str = Field(..., description="文件ID")
    filename: Optional[str] = Field(None, description="文件名")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    upload_time: Optional[str] = Field(None, description="上传时间")
    file_type: Optional[FileTypeResponse] = Field(None, description="文件类型信息")
    # h5ad文件元信息（可选）
    n_spots: Optional[int] = Field(None, description="Spots数量（h5ad文件）")
    n_genes: Optional[int] = Field(None, description="基因数量（h5ad文件）")
    has_spatial: Optional[bool] = Field(None, description="是否有空间信息（h5ad文件）")


class FileInfoItem(BaseModel):
    """文件信息项（用于列表）"""
    file_id: str = Field(..., description="文件ID")
    name: str = Field(..., description="文件名")
    size: int = Field(..., description="文件大小（字节）")
    status: str = Field(..., description="状态")
    time: str = Field(..., description="上传时间")
    file_type: FileTypeResponse = Field(..., description="文件类型")
    # h5ad文件元信息（可选）
    n_spots: Optional[int] = Field(None, description="Spots数量（h5ad文件）")
    n_genes: Optional[int] = Field(None, description="基因数量（h5ad文件）")
    has_spatial: Optional[bool] = Field(None, description="是否有空间信息（h5ad文件）")


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: List[FileInfoItem] = Field(default_factory=list, description="文件列表")


class FileDetailResponse(BaseModel):
    """文件详情响应"""
    file_id: str = Field(..., description="文件ID")
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    upload_time: str = Field(..., description="上传时间")
    last_viewed_time: str = Field(..., description="最后查看时间")
    status: str = Field(..., description="状态")
    description: Optional[str] = Field(None, description="文件描述")
    metadata: dict = Field(default_factory=dict, description="元数据")
    file_type: FileTypeResponse = Field(..., description="文件类型信息")


class FileUpdateRequest(BaseModel):
    """
    更新文件信息请求
    
    至少需要提供一个字段（name 或 description）
    """
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="新的文件名")
    description: Optional[str] = Field(None, max_length=1000, description="新的文件描述")
    
    @validator('name')
    def validate_name(cls, v):
        """验证文件名：如果提供，则不能为空，trim后验证长度"""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("文件名不能为空")
            trimmed = v.strip()
            if len(trimmed) < 1 or len(trimmed) > 255:
                raise ValueError("文件名长度必须在1-255字符之间")
            return trimmed
        return v


# ============= Agent / Project Agent 模型 =============


class AgentMessageRequest(BaseModel):
    """发送消息请求"""
    project_id: str = Field(..., description="项目ID")
    conversation_id: Optional[str] = Field(None, description="现有项目对话ID")
    message: str = Field(..., min_length=1, description="用户输入消息")

    context_files: Optional[List[str]] = Field(
        default=None,
        description="额外上下文文件ID列表"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="附加业务元数据"
    )



class SpatialCoordinateColumns(BaseModel):
    """空间坐标列名"""
    x: str = Field(..., min_length=1, description="obs中表示X/列坐标的字段名")
    y: str = Field(..., min_length=1, description="obs中表示Y/行坐标的字段名")


class CellMicroenvironmentParams(BaseModel):
    """细胞微环境分析所需参数"""
    file_id: str = Field(..., description="空间表达文件的file_id")
    cell_id: str = Field(..., description="目标细胞ID（需与AnnData.obs.index匹配）")
    neighbor_count: int = Field(5, ge=1, le=100, description="纳入分析的邻居细胞数量")
    cluster_key: Optional[str] = Field("cluster", description="用于保存聚类标签的obs列名")
    cluster_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="细胞ID到聚类标签的映射，若提供将写入obs[cluster_key]"
    )
    cell_indices: List[Union[str, int]] = Field(
        default_factory=list,
        description="可选的细胞索引列表（字符串ID或整数索引），为空则使用全部细胞"
    )
    coordinate_columns: Optional[SpatialCoordinateColumns] = Field(
        None,
        description="自定义坐标列名，默认自动识别"
    )


class SpatialExpressionPatternParams(BaseModel):
    """空间表达模式分析参数"""
    file_id: str = Field(..., description="空间表达文件的file_id")
    cluster_key: Optional[str] = Field("cluster", description="聚类标签列名，不存在时会自动计算")
    target_regions: Optional[List[str]] = Field(None, description="待重点分析的region/cluster列表")
    cluster_labels: Dict[str, str] = Field(
        default_factory=dict,
        description="细胞ID到聚类标签的映射"
    )
    cell_indices: List[Union[str, int]] = Field(
        default_factory=list,
        description="可选的细胞索引列表（用于子集化）"
    )
    coordinate_columns: Optional[SpatialCoordinateColumns] = Field(
        None,
        description="自定义坐标列名"
    )


class RAGMessageResponse(BaseModel):
    """RAG工作流消息响应"""
    conversation_id: str = Field(..., description="对话ID")
    answer: str = Field(..., description="Agent回答")
    evidence_sources: List[Dict[str, Any]] = Field(default_factory=list, description="证据来源列表")
    execution_time: float = Field(..., description="执行耗时（秒）")


class AgentConversationMessage(BaseModel):
    """对话消息项（统一字段 message/time/extra）"""
    message_id: Optional[str] = Field(None, description="消息ID")
    role: str = Field(..., description="角色，例如 user/assistant/system")
    message: str = Field(..., description="消息内容")
    time: Optional[str] = Field(None, description="时间戳（ISO8601）")
    extra: Dict[str, Any] = Field(default_factory=dict, description="附加信息（结构化字段，如代码片段、引用等）")


class AgentConversationResponse(BaseModel):
    """对话详情"""
    conversation_id: str = Field(..., description="对话ID")
    project_id: str = Field(..., description="项目ID")
    context_summary: Optional[str] = Field(None, description="上下文摘要")
    updated_at: Optional[str] = Field(None, description="更新时间")
    messages: List[AgentConversationMessage] = Field(default_factory=list, description="消息列表")


class AgentJobStep(BaseModel):
    """工作流步骤（对齐 Mongo AgentJobStep）"""

    name: str = Field(..., description="步骤名称")
    status: Literal["pending", "running", "completed", "failed", "skipped"] = Field(
        "pending", description="步骤状态"
    )
    started_at: Optional[str] = Field(None, description="步骤开始时间（ISO8601）")
    finished_at: Optional[str] = Field(None, description="步骤结束时间（ISO8601）")
    output: Optional[str] = Field(None, description="步骤产出或摘要")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="步骤元数据")
    message: Optional[str] = Field(None, description="步骤备注或提示信息")


class AgentJobSummary(BaseModel):
    """Job 概要信息"""

    job_id: str = Field(..., description="job ID")
    project_id: str = Field(..., description="项目ID")
    status: Literal["pending", "running", "cancelling", "cancelled", "completed", "failed"] = Field(
        ..., description="job状态"
    )
    cancel_requested: bool = Field(False, description="是否请求取消")
    message: Optional[str] = Field(None, description="状态说明/提示")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    created_at: Optional[str] = Field(None, description="创建时间（ISO8601）")
    updated_at: Optional[str] = Field(None, description="更新时间（ISO8601）")
    finished_at: Optional[str] = Field(None, description="完成时间（ISO8601）")


class AgentJobResponse(AgentJobSummary):
    """完整 job 响应"""

    payload: Dict[str, Any] = Field(default_factory=dict, description="执行输入")
    steps: List[AgentJobStep] = Field(default_factory=list, description="步骤轨迹")
    result: Optional[Dict[str, Any]] = Field(None, description="最终结果（结构化）")
    error: Optional[Dict[str, Any]] = Field(None, description="错误信息（结构化）")


class AgentJobsResponse(BaseModel):
    """轮询活跃 job 响应"""

    job: Optional[AgentJobResponse] = Field(
        None,
        description="当前未完成的job详情；无活跃job时返回null",
    )


class AgentStopJobResponse(BaseModel):
    """停止 job 响应"""

    job_id: str = Field(..., description="job ID")
    status: Literal["pending", "running", "cancelling", "cancelled", "completed", "failed"] = Field(
        ..., description="job状态（包含cancelling用于中间态）"
    )
    message: Optional[str] = Field(None, description="附加消息")


class AgentSessionResponse(BaseModel):
    """会话响应（对话 + 当前job信息）"""

    conversation: AgentConversationResponse = Field(..., description="当前对话")
    job: Optional[AgentJobResponse] = Field(
        None,
        description="若存在未完成job，返回对应job详情；否则为None",
    )


class AgentKnowledgeResponse(BaseModel):
    """知识列表响应"""
    knowledge: List[Dict[str, Any]] = Field(default_factory=list, description="知识条目列表")


class FileUpdateResponse(BaseModel):
    """更新文件信息响应"""
    file_id: str = Field(..., description="文件ID")
    name: str = Field(..., description="更新后的文件名")
    description: Optional[str] = Field(None, description="更新后的文件描述")


class FileDeleteResponse(BaseModel):
    """文件删除响应"""
    message: str = Field(default="success", description="删除结果")
    deleted_file_ids: List[str] = Field(default_factory=list, description="已删除的文件ID列表")
    failed_file_ids: Dict[str, str] = Field(default_factory=dict, description="删除失败的文件及原因")
    project_scope: List[str] = Field(default_factory=list, description="此次删除涉及的项目范围")


class ExecutionDeleteResponse(FileDeleteResponse):
    """执行删除响应"""
    deleted_execution_ids: List[str] = Field(default_factory=list, description="已删除的执行ID列表")
    failed_execution_ids: Dict[str, str] = Field(default_factory=dict, description="删除失败的执行及原因")


# ============= 通用响应模型 =============

class ApiResponse(BaseModel):
    """通用API响应"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="消息")
    data: Optional[dict] = Field(None, description="数据")


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int = Field(..., description="错误码")
    message: str = Field(..., description="错误消息")
    detail: Optional[str] = Field(None, description="错误详情")


# ============= 分析流程相关模型 =============

class FileNode(BaseModel):
    """文件节点模型"""
    id: str = Field(..., description="文件节点唯一标识")
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    description: Optional[str] = Field(None, description="文件描述")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    path: Optional[str] = Field(None, description="文件路径")
    url: Optional[str] = Field(None, description="文件下载URL")
    status: Optional[str] = Field(None, description="文件状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="文件元数据")
    children: Optional[List['FileNode']] = Field(None, description="子文件节点列表")
    algorithm: Optional['AlgorithmEdge'] = Field(None, description="关联的算法信息")


class AlgorithmEdge(BaseModel):
    """算法边模型"""
    algorithm_id: str = Field(..., description="算法ID")
    algorithm_name: str = Field(..., description="算法名称")
    description: Optional[str] = Field(None, description="算法描述")
    algorithm_type: Optional[str] = Field(None, description="算法类型")
    icon: Optional[str] = Field(None, description="算法图标")
    key_params: Optional[Dict[str, Any]] = Field(None, description="关键参数")
    status: str = Field(..., description="执行状态")
    start_time: Optional[str] = Field(None, description="开始时间")
    end_time: Optional[str] = Field(None, description="结束时间")
    duration: Optional[int] = Field(None, description="执行耗时（毫秒）")
    error: Optional[str] = Field(None, description="错误信息")
    summary: Optional[str] = Field(None, description="执行结果摘要")


# 解决前向引用
FileNode.model_rebuild()


class FileAnalysisTreeResponse(BaseModel):
    """文件分析流程树响应"""
    file_id: str = Field(..., description="原始文件ID")
    root: FileNode = Field(..., description="根文件节点")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    status: Optional[str] = Field(None, description="当前执行状态")
    progress: Optional[int] = Field(None, description="总体进度（0-100）")
    total_nodes: Optional[int] = Field(None, description="总文件节点数")
    completed_nodes: Optional[int] = Field(None, description="已完成文件节点数")


class UpdateAlgorithmStatusRequest(BaseModel):
    """更新算法状态请求"""
    model_config = ConfigDict(populate_by_name=True)  # Allow both snake_case and camelCase
    
    status: str = Field(..., description="新状态")
    output_file: Optional[FileNode] = Field(None, alias="outputFile", description="输出的文件信息")
    error: Optional[str] = Field(None, description="错误信息")


class UpdateAlgorithmStatusResponse(BaseModel):
    """更新算法状态响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")


class ProjectTreeNode(BaseModel):
    """项目树节点（简化结构）"""
    id: str = Field(..., description="节点ID")
    type: str = Field(..., description="节点类型（project/file）")
    children: List['ProjectTreeNode'] = Field(default_factory=list, description="子节点列表")


# 解决前向引用
ProjectTreeNode.model_rebuild()


class ProjectTreeStatistics(BaseModel):
    """项目树统计信息"""
    total_files: int = Field(..., description="总文件数")
    total_executions: int = Field(..., description="总执行记录数")
    completed_files: int = Field(..., description="已完成文件数")
    completed_executions: int = Field(..., description="已完成执行记录数")
    failed_executions: int = Field(..., description="失败执行记录数")
    running_executions: int = Field(..., description="运行中执行记录数")


class ProjectAnalysisTreeResponse(BaseModel):
    """项目分析流程树响应"""
    project_id: str = Field(..., description="项目ID")
    project_name: Optional[str] = Field(None, description="项目名称")
    project_description: Optional[str] = Field(None, description="项目描述")
    file_id: Optional[str] = Field(None, description="原始文件ID（如果适用）")
    root: ProjectTreeNode = Field(..., description="根节点（项目节点）")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="文件列表（扁平化，包含完整信息）")
    executions: List[Dict[str, Any]] = Field(default_factory=list, description="执行记录列表（扁平化，包含完整信息）")
    statistics: ProjectTreeStatistics = Field(..., description="统计信息")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    status: Optional[str] = Field(None, description="当前执行状态")
    progress: Optional[int] = Field(None, description="总体进度（0-100）")
    total_nodes: Optional[int] = Field(None, description="总节点数")
    completed_nodes: Optional[int] = Field(None, description="已完成节点数")


class FileNodeResponse(BaseModel):
    """文件节点详情响应"""
    id: str = Field(..., description="文件节点唯一标识")
    file_id: str = Field(..., description="文件ID")
    file_name: str = Field(..., description="文件名")
    file_type: str = Field(..., description="文件类型")
    description: Optional[str] = Field(None, description="文件描述")
    size: Optional[int] = Field(None, description="文件大小（字节）")
    path: Optional[str] = Field(None, description="文件路径")
    status: Optional[str] = Field(None, description="文件状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    metadata: Optional[Dict[str, Any]] = Field(None, description="文件元数据")


class ExecutionDetailsResponse(BaseModel):
    """执行记录详情响应"""
    execution_id: str = Field(..., description="执行ID")
    algorithm_id: str = Field(..., description="算法ID（与execution_id相同）")
    algorithm_name: str = Field(..., description="算法名称")
    description: Optional[str] = Field(None, description="算法描述")
    status: str = Field(..., description="执行状态")
    duration: Optional[int] = Field(None, description="执行耗时（毫秒）")
    key_params: Optional[Dict[str, Any]] = Field(None, description="关键参数")
    input_file_id: Optional[str] = Field(None, description="输入文件ID")
    output_file_id: Optional[str] = Field(None, description="输出文件ID")
    error_message: Optional[str] = Field(None, description="错误信息")
    response_data: Optional[Dict[str, Any]] = Field(None, description="响应数据")
    created_at: Optional[str] = Field(None, description="创建时间")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")


# ============= 空间转录组数据相关模型 =============

class SpatialSlice(BaseModel):
    """空间切片信息"""
    id: str = Field(..., description="切片唯一标识符")
    name: str = Field(..., description="切片名称")
    description: Optional[str] = Field(None, description="切片描述")
    width: Optional[int] = Field(None, description="切片图像宽度（像素）")
    height: Optional[int] = Field(None, description="切片图像高度（像素）")


class GetSlicesResponse(BaseModel):
    """获取切片列表响应"""
    slices: List[SpatialSlice] = Field(..., description="切片列表")


class GetSliceImageResponse(BaseModel):
    """获取切片图像响应（单切片模式）"""
    image_url: str = Field(..., description="切片图像的URL")
    width: int = Field(..., description="图像宽度（像素）")
    height: int = Field(..., description="图像高度（像素）")


class GeneExpression(BaseModel):
    """基因表达信息"""
    name: str = Field(..., description="基因名称")
    value: float = Field(..., description="基因表达值")


class SpatialSpot(BaseModel):
    """空间Spot信息（包含位置信息和分组属性）"""
    id: str = Field(..., description="Spot唯一标识符")
    x: float = Field(..., description="Spot的X坐标")
    y: float = Field(..., description="Spot的Y坐标")
    group: Dict[str, Any] = Field(..., description="Spot的分组属性，包含obs中所有列的值（排除坐标列x和y）")


class GetSpotsResponse(BaseModel):
    """获取Spots响应（单切片模式）"""
    spots: List[SpatialSpot] = Field(..., description="Spot数据列表")
    total_count: int = Field(..., description="该文件的总spot数量")


class GeneExpressionItem(BaseModel):
    """基因表达项"""
    spot_id: str = Field(..., description="Spot唯一标识符")
    value: float = Field(..., description="基因在该Spot中的表达值")


# ============= 可视化API相关模型 =============

class VisualizationType(BaseModel):
    """可视化类型信息"""
    type: str = Field(..., description="可视化类型标识（如：spatial）")
    name: str = Field(..., description="可视化类型名称")
    description: str = Field(..., description="可视化类型描述")


class VisualizationTypesResponse(BaseModel):
    """获取可视化类型列表响应"""
    types: List[VisualizationType] = Field(..., description="支持的可视化类型列表")


class SpatialSliceImageResponse(BaseModel):
    """空间转录组学切片图像响应"""
    image_url: str = Field(..., alias="imageUrl", description="切片图像的URL")
    width: int = Field(..., description="图像宽度（像素）")
    height: int = Field(..., description="图像高度（像素）")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @validator('image_url')
    def validate_image_url(cls, v):
        """验证图像URL：不能为空"""
        if not v or not v.strip():
            raise ValueError("图像URL不能为空")
        return v.strip()
    
    @validator('width', 'height')
    def validate_dimensions(cls, v):
        """验证图像尺寸：必须大于0"""
        if v is not None and v <= 0:
            raise ValueError("图像尺寸必须大于0")
        return v


class SpatialSpotsResponse(BaseModel):
    """空间转录组学spots位置数据响应"""
    spots: List[SpatialSpot] = Field(..., description="Spot数据列表")
    total_count: int = Field(..., alias="totalCount", description="该文件的总spot数量")
    
    model_config = ConfigDict(populate_by_name=True)
    
    @validator('total_count')
    def validate_total_count(cls, v):
        """验证总数量：必须大于等于0"""
        if v < 0:
            raise ValueError("总数量不能为负数")
        return v


class SpatialGeneExpressionItem(BaseModel):
    """空间转录组学基因表达项（匹配服务返回格式）"""
    spot_id: str = Field(..., alias="spotId", description="Spot唯一标识符")
    value: float = Field(..., description="基因在该Spot中的表达值")
    
    model_config = ConfigDict(populate_by_name=True)


# 注意：SpatialGeneExpressionResponse 实际上是一个列表
# 服务返回 List[Dict[str, Any]]，其中每个字典包含 spotId 和 value
# 为了类型安全和文档，我们定义 SpatialGeneExpressionResponse 为 List[SpatialGeneExpressionItem]
SpatialGeneExpressionResponse = List[SpatialGeneExpressionItem]


class SpatialGenesResponse(BaseModel):
    """空间转录组学基因列表响应"""
    genes: List[str] = Field(..., description="基因名称列表")
    total_count: Optional[int] = Field(None, description="基因总数（可选，如果未提供则等于列表长度）")
    
    @validator('total_count')
    def validate_total_count(cls, v):
        """验证总数量：必须大于等于0"""
        if v is not None and v < 0:
            raise ValueError("总数量不能为负数")
        return v
    
    @model_validator(mode='after')
    def validate_genes_match_count(self):
        """验证基因列表长度与总数一致（如果提供了总数）"""
        if self.total_count is not None and len(self.genes) != self.total_count:
            raise ValueError("基因列表长度必须与总数一致")
        return self


class VisualizationDataResponse(BaseModel):
    """可视化数据响应（通用接口，支持未来扩展）"""
    data: Dict[str, Any] = Field(..., description="可视化数据")
    visualization_type: str = Field(..., description="可视化类型")
    data_type: Optional[str] = Field(None, description="数据类型（如：slice-image, spots, gene-expression, genes）")
    
    @validator('visualization_type')
    def validate_visualization_type(cls, v):
        """验证可视化类型：不能为空"""
        if not v or not v.strip():
            raise ValueError("可视化类型不能为空")
        return v.strip()


# ============= 参数验证模型 =============

class FileIdPath(BaseModel):
    """文件ID路径参数验证"""
    file_id: str = Field(..., min_length=1, description="文件ID")
    
    @validator('file_id')
    def validate_file_id(cls, v):
        """验证文件ID：不能为空，trim后长度至少1字符"""
        if not v or not v.strip():
            raise ValueError("文件ID不能为空")
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("文件ID不能为空")
        return trimmed


class GeneNamePath(BaseModel):
    """基因名称路径参数验证"""
    gene_name: str = Field(..., min_length=1, description="基因名称")
    
    @validator('gene_name')
    def validate_gene_name(cls, v):
        """验证基因名称：不能为空，trim后长度至少1字符"""
        if not v or not v.strip():
            raise ValueError("基因名称不能为空")
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("基因名称不能为空")
        return trimmed


class VisualizationTypePath(BaseModel):
    """可视化类型路径参数验证"""
    visualization_type: str = Field(..., min_length=1, description="可视化类型")
    
    @validator('visualization_type')
    def validate_visualization_type(cls, v):
        """验证可视化类型：不能为空，trim后长度至少1字符"""
        if not v or not v.strip():
            raise ValueError("可视化类型不能为空")
        trimmed = v.strip()
        if len(trimmed) < 1:
            raise ValueError("可视化类型不能为空")
        return trimmed


class SpatialGenesQuery(BaseModel):
    """空间转录组学基因列表查询参数"""
    query: Optional[str] = Field(None, description="搜索关键词（可选）")
    
    @validator('query')
    def validate_query(cls, v):
        """验证搜索关键词：如果提供，则trim"""
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class VisualizationDataQuery(BaseModel):
    """可视化数据查询参数"""
    data_type: Optional[str] = Field(None, description="数据类型（可选，如：slice-image, spots, gene-expression, genes）")
    gene_name: Optional[str] = Field(None, description="基因名称（当data_type为gene-expression时必填）")
    query: Optional[str] = Field(None, description="搜索关键词（当data_type为genes时可选）")
    
    @validator('gene_name')
    def validate_gene_name(cls, v):
        """验证基因名称：如果提供，则trim"""
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("基因名称不能为空")
            return trimmed
        return v
    
    @validator('query')
    def validate_query(cls, v):
        """验证搜索关键词：如果提供，则trim"""
        if v is not None:
            return v.strip() if v.strip() else None
        return v
    
    @model_validator(mode='after')
    def validate_gene_name_required(self):
        """验证当data_type为gene-expression时，gene_name必填"""
        if self.data_type == "gene-expression":
            if not self.gene_name:
                raise ValueError("获取基因表达数据需要提供gene_name参数")
        return self


# ============= Task相关模型 =============

class ServiceCreateRequest(BaseModel):
    """创建Service请求"""
    service_id: Optional[str] = Field(None, description="Service ID（可选，如果不提供则由系统自动生成UUID）")
    name: str = Field(..., min_length=1, max_length=200, description="Service名称")
    description: Optional[str] = Field(None, max_length=1000, description="Service描述")
    version: str = Field(default="1.0.0", max_length=50, description="Service版本")
    baseurl: str = Field(..., min_length=1, description="基础URL（IP和端口号，如 http://192.168.1.1:8080）")
    service_suffix: str = Field(..., min_length=1, description="Service后缀（与baseurl拼接后访问对应的service，如 /api/service）")
    download_suffix: Optional[str] = Field(None, description="Download后缀（如果输出存在文件则需要配置，用于下载生成文件，如 /api/download）")
    request_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="请求配置")
    parameter_template: Optional[Dict[str, Any]] = Field(default_factory=dict, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(default=None, description="参数定义schema，定义每个参数的类型、范围和约束")
    accepted_files: Optional[Dict[str, Any]] = Field(None, description="接受的文件类型配置，格式：{filename: {file_type_ids: [...], description: ...}}")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出结果配置，定义输出结果项集合（文件或文本信息）")
    visibility: Optional[str] = Field(default="private", description="Service权限（private/public/system），默认private")


class ServiceUpdateRequest(BaseModel):
    """更新Service请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Service名称")
    description: Optional[str] = Field(None, max_length=1000, description="Service描述")
    version: Optional[str] = Field(None, max_length=50, description="Service版本")
    baseurl: Optional[str] = Field(None, min_length=1, description="基础URL（IP和端口号，如 http://192.168.1.1:8080）")
    service_suffix: Optional[str] = Field(None, min_length=1, description="Service后缀（与baseurl拼接后访问对应的service，如 /api/service）")
    download_suffix: Optional[str] = Field(None, description="Download后缀（如果输出存在文件则需要配置，用于下载生成文件，如 /api/download）")
    request_config: Optional[Dict[str, Any]] = Field(None, description="请求配置")
    parameter_template: Optional[Dict[str, Any]] = Field(None, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(None, description="参数定义schema，定义每个参数的类型、范围和约束")
    accepted_files: Optional[Dict[str, Any]] = Field(None, description="接受的文件类型配置，格式：{filename: {file_type_ids: [...], description: ...}}")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出结果配置，定义输出结果项集合（文件或文本信息）")
    visibility: Optional[str] = Field(None, description="Service权限（private/public/system）")


class ServiceResponse(BaseModel):
    """Service响应"""
    service_id: str = Field(..., description="Service ID")
    name: str = Field(..., description="Service名称")
    description: Optional[str] = Field(None, description="Service描述")
    version: str = Field(..., description="Service版本")
    baseurl: str = Field(..., description="基础URL（IP和端口号，如 http://192.168.1.1:8080）")
    service_suffix: str = Field(..., description="Service后缀（与baseurl拼接后访问对应的service，如 /api/service）")
    download_suffix: Optional[str] = Field(None, description="Download后缀（如果输出存在文件则需要配置，用于下载生成文件，如 /api/download）")
    request_config: Dict[str, Any] = Field(default_factory=dict, description="请求配置")
    parameter_template: Dict[str, Any] = Field(default_factory=dict, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(default=None, description="参数定义schema，定义每个参数的类型、范围和约束")
    accepted_files: Optional[Dict[str, Any]] = Field(None, description="接受的文件类型配置，格式：{filename: {file_type_ids: [...], description: ...}}")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出结果配置，定义输出结果项集合（文件或文本信息）")
    visibility: str = Field(..., description="Service权限（private/public/system）")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    created_by: Optional[str] = Field(None, description="创建者用户ID")


class ServiceListResponse(BaseModel):
    """Service列表响应"""
    services: List[ServiceResponse] = Field(default_factory=list, description="Service列表")
    total: int = Field(default=0, description="总数")


class ServiceExecuteRequest(BaseModel):
    """执行Service请求"""
    input_file_ids: List[str] = Field(..., min_length=1, description="输入文件ID列表（支持多文件输入）")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="执行参数（覆盖parameterTemplate）")
    project_id: Optional[str] = Field(None, description="项目ID（可选，如果提供，执行记录将关联到该项目）")
    
    @validator('input_file_ids')
    def validate_input_file_ids(cls, v):
        """验证input_file_ids"""
        if not isinstance(v, list):
            raise ValueError("input_file_ids必须是字符串列表")
        if len(v) == 0:
            raise ValueError("input_file_ids列表不能为空")
        # 过滤空字符串并验证
        valid_ids = [id.strip() for id in v if id and id.strip()]
        if len(valid_ids) == 0:
            raise ValueError("input_file_ids列表中没有有效的文件ID")
        return valid_ids


class ServiceExecuteResponse(BaseModel):
    """执行Service响应"""
    execution_id: str = Field(..., description="执行ID")
    service_id: str = Field(..., description="Service ID")
    input_file_ids: List[str] = Field(..., description="输入文件ID列表")
    output_file_ids: Optional[List[str]] = Field(None, description="输出文件ID列表")
    status: str = Field(..., description="执行状态")
    response_data: Optional[Dict[str, Any]] = Field(None, description="远程服务器响应数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: Optional[str] = Field(None, description="创建时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")


class ServiceExecutionResponse(BaseModel):
    """Service执行记录响应"""
    execution_id: str = Field(..., description="执行ID")
    service_id: str = Field(..., description="Service ID")
    service_name: Optional[str] = Field(None, description="Service名称")
    user_id: str = Field(..., description="用户ID")
    input_file_ids: List[str] = Field(..., description="输入文件ID列表")
    output_file_ids: Optional[List[str]] = Field(None, description="输出文件ID列表")
    project_id: Optional[str] = Field(None, description="项目ID")
    status: str = Field(..., description="执行状态")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="执行参数")
    response_data: Optional[Dict[str, Any]] = Field(None, description="远程服务器响应数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: Optional[str] = Field(None, description="创建时间")
    started_at: Optional[str] = Field(None, description="开始执行时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")


class ServiceExecutionListResponse(BaseModel):
    """Service执行记录列表响应"""
    executions: List[ServiceExecutionResponse] = Field(default_factory=list, description="执行记录列表")
    total: int = Field(default=0, description="总数")


# ============= 知识图谱相关模型 =============

class KnowledgeRelationSummaryPayload(BaseModel):
    """知识关系摘要（三元组）"""
    from_entity: str = Field(..., description="头实体", min_length=1)
    relation: str = Field(..., description="关系类型", min_length=1)
    end_entity: str = Field(..., description="尾实体", min_length=1)

    @validator('from_entity', 'relation', 'end_entity')
    def validate_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("relation_summary 字段不能为空")
        return v.strip()


class KnowledgeItemResponse(BaseModel):
    """知识条目响应"""
    id: str = Field(..., description="知识ID")
    title: str = Field(..., description="标题")
    description: str = Field(..., description="描述")
    relation_summary: Optional[KnowledgeRelationSummaryPayload] = Field(None, description="关系摘要（三元组）")
    scope: str = Field(..., description="范围")
    edited_by_user: bool = Field(default=True, description="是否用户编辑")
    source: Optional[str] = Field(None, description="来源")
    owner_id: Optional[str] = Field(None, description="所属用户")
    created_at: Optional[str] = Field(None, description="创建时间")
    last_modified: Optional[str] = Field(None, description="最后更新时间")
    shared_at: Optional[str] = Field(None, description="分享时间")


class KnowledgeListResponse(BaseModel):
    """知识列表响应"""
    items: List[KnowledgeItemResponse] = Field(default_factory=list, description="知识列表")
    total: int = Field(default=0, description="总数")
    page: int = Field(default=1, description="当前页")
    page_size: int = Field(default=20, description="每页数量")


class KnowledgeCreateRequest(BaseModel):
    """创建知识请求"""
    title: str = Field(..., min_length=1, description="标题")
    description: str = Field(..., min_length=1, description="描述")
    relation_summary: KnowledgeRelationSummaryPayload = Field(..., description="关系摘要（三元组）")
    scope: Optional[Literal["private", "public", "system"]] = Field("private", description="范围（private/public/system）")
    kind: Optional[str] = Field("relation", description="类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")

    @validator('title', 'description')
    def validate_required(cls, v: str):
        """验证标题和描述不能为空"""
        if not v or not v.strip():
            raise ValueError("标题和描述不能为空")
        return v.strip()


class KnowledgeUpdateRequest(BaseModel):
    """更新知识请求"""
    title: Optional[str] = Field(None, description="标题")
    description: Optional[str] = Field(None, description="描述")
    relation_summary: Optional[KnowledgeRelationSummaryPayload] = Field(None, description="关系摘要（三元组）")
    kind: Optional[str] = Field(None, description="类型")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")

    @validator('title', 'description')
    def validate_not_empty_if_provided(cls, v: Optional[str]):
        """验证如果提供了标题或描述，则不能为空"""
        if v is not None and (not v or not v.strip()):
            raise ValueError("标题和描述不能为空")
        return v.strip() if v else v


class KnowledgeShareRequest(BaseModel):
    """分享知识请求"""
    visibility: Literal["public"] = Field("public", description="目标范围")
    note: Optional[str] = Field(None, description="备注")


class KnowledgeWorkflowImportRequest(BaseModel):
    """导入Workflow候选请求"""
    task_id: str = Field(..., min_length=1, description="任务ID")
    candidate_ids: List[str] = Field(..., min_length=1, description="候选ID列表")
    scope: Optional[Literal["private", "public", "system"]] = Field(None, description="导入后的范围（private/public/system）")

    @validator('task_id')
    def validate_task_id(cls, v: str):
        """验证任务ID不能为空"""
        if not v or not v.strip():
            raise ValueError("任务ID不能为空")
        return v.strip()

    @validator('candidate_ids')
    def validate_candidate_ids(cls, v: List[str]):
        """验证候选ID列表不能为空，且每个ID不能为空"""
        if not v or len(v) == 0:
            raise ValueError("候选ID列表不能为空")
        filtered = [item.strip() for item in v if item and item.strip()]
        if len(filtered) == 0:
            raise ValueError("候选ID列表不能为空")
        return filtered


class KnowledgeWorkflowTaskResponse(BaseModel):
    """Workflow任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    workflow: Optional[str] = Field(None, description="Workflow类型")
    raw_text: Optional[str] = Field(None, description="原始文本")
    prompt_id: Optional[str] = Field(None, description="Prompt模板")
    candidates: List[Dict[str, Any]] = Field(default_factory=list, description="候选列表")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    error_message: Optional[str] = Field(None, description="错误信息")


class KnowledgePromptConfigRequest(BaseModel):
    """Prompt配置请求"""
    template_id: Optional[str] = Field(None, description="模板ID（创建时可选，更新时必填）")
    name: Optional[str] = Field(None, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    entity_prompt: Dict[str, str] = Field(..., description="实体抽取描述（字典格式：{实体名: 描述, ...}）")
    relation_prompt: Dict[str, str] = Field(..., description="关系抽取描述（字典格式：{关系名: 描述, ...}）")
    constraints: Optional[str] = Field(None, description="输出约束")
    is_default: Optional[bool] = Field(False, description="是否为默认模板")

    @validator('entity_prompt', 'relation_prompt')
    def validate_prompts_not_empty(cls, v: Dict[str, str]):
        """验证实体和关系提示词不能为空字典"""
        if not v or len(v) == 0:
            raise ValueError("实体抽取描述和关系抽取描述不能为空")
        # 验证字典中的值不能为空
        for key, value in v.items():
            if not key or not key.strip():
                raise ValueError("实体名或关系名不能为空")
            if not value or not value.strip():
                raise ValueError(f"{key}的描述不能为空")
        return v


class KnowledgePromptConfigResponse(BaseModel):
    """Prompt配置响应"""
    template_id: Optional[str] = Field(None, description="模板ID")
    name: Optional[str] = Field(None, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    entity_prompt: Dict[str, str] = Field(..., description="实体抽取描述（字典格式：{实体名: 描述, ...}）")
    relation_prompt: Dict[str, str] = Field(..., description="关系抽取描述（字典格式：{关系名: 描述, ...}）")
    constraints: Optional[str] = Field(None, description="输出约束")
    is_default: bool = Field(False, description="是否为默认模板")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class KnowledgeExtractTextRequest(BaseModel):
    """从文本提取知识请求"""
    text: str = Field(..., min_length=1, description="待提取的文本")
    template_id: Optional[str] = Field(None, description="模板ID（可选）")
    source: Optional[str] = Field(None, description="来源说明（可选）")

    @validator('text')
    def validate_text_not_empty(cls, v: str):
        """验证文本不能为空"""
        if not v or not v.strip():
            raise ValueError("待提取的文本不能为空")
        return v.strip()


class KnowledgeExtractLiteratureRequest(BaseModel):
    """从文献提取知识请求"""
    query: str = Field(..., min_length=1, description="查询关键词")
    template_id: Optional[str] = Field(None, description="模板ID（可选）")
    max_results: int = Field(10, ge=1, le=50, description="最大检索文献数量")

    @validator('query')
    def validate_query_not_empty(cls, v: str):
        """验证查询关键词不能为空"""
        if not v or not v.strip():
            raise ValueError("查询关键词不能为空")
        return v.strip()


class KnowledgeExtractPromptRequest(BaseModel):
    """生成提示词请求"""
    query: str = Field(..., min_length=1, description="用户查询/需求描述")
    description: Optional[str] = Field(None, description="可选的描述信息")

    @validator('query')
    def validate_query_not_empty(cls, v: str):
        """验证用户查询不能为空"""
        if not v or not v.strip():
            raise ValueError("用户查询/需求描述不能为空")
        return v.strip()


class KnowledgePromptApproveRequest(BaseModel):
    """审批提示词请求"""
    pending_prompt_id: str = Field(..., min_length=1, description="待审批提示ID")
    template_id: Optional[str] = Field(None, description="模板ID（可选，如果不提供则自动生成）")
    name: Optional[str] = Field(None, description="模板名称（可选）")
    is_default: bool = Field(False, description="是否设为默认模板")

    @validator('pending_prompt_id')
    def validate_pending_prompt_id(cls, v: str):
        """验证待审批提示ID不能为空"""
        if not v or not v.strip():
            raise ValueError("待审批提示ID不能为空")
        return v.strip()


class KnowledgeDocumentDictCreateRequest(BaseModel):
    """创建知识文档字典请求"""
    project_id: str = Field(..., min_length=1, description="项目ID")
    query: str = Field(..., min_length=1, description="用户查询字符串")
    source: str = Field(..., min_length=1, description="数据源标识，如 pubmed/arxiv/crossref")
    title: str = Field(..., min_length=1, description="文献标题（主键，唯一标识）")
    snippet: str = Field("", description="摘要或内容片段")
    url: Optional[str] = Field(None, description="文献链接")
    doi: Optional[str] = Field(None, description="DOI，如有")
    published_at: Optional[str] = Field(None, description="发表时间（ISO字符串或年份）")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    journal: Optional[str] = Field(None, description="期刊或会议")
    source_type: Optional[str] = Field(None, description="文献类型")
    score: Optional[float] = Field(None, description="相关性评分")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    @validator('project_id', 'query', 'source', 'title')
    def validate_required_fields(cls, v: str):
        """验证必填字段不能为空"""
        if not v or not v.strip():
            raise ValueError("project_id、query、source、title 不能为空")
        return v.strip()


class KnowledgeDocumentDictResponse(BaseModel):
    """知识文档字典响应"""
    title: str = Field(..., description="文献标题")
    project_id: str = Field(..., description="项目ID")
    query: str = Field(..., description="用户查询字符串")
    source: str = Field(..., description="数据源标识")
    snippet: str = Field("", description="摘要或内容片段")
    url: Optional[str] = Field(None, description="文献链接")
    doi: Optional[str] = Field(None, description="DOI")
    published_at: Optional[str] = Field(None, description="发表时间")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    journal: Optional[str] = Field(None, description="期刊或会议")
    source_type: Optional[str] = Field(None, description="文献类型")
    score: Optional[float] = Field(None, description="相关性评分")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class KnowledgeDocumentDictDeleteResponse(BaseModel):
    """删除知识文档字典响应"""
    code: int = Field(200, description="状态码")
    message: str = Field("删除成功", description="提示信息")


class KnowledgeDocumentDictGroupedResponse(BaseModel):
    """按 query 分组的知识文档字典响应"""
    query: str = Field(..., description="用户查询字符串")
    documents: List[KnowledgeDocumentDictResponse] = Field(default_factory=list, description="该查询下的文档列表")


class KnowledgeDocumentDictListByProjectResponse(BaseModel):
    """根据 project_id 查询并按 query 分组的响应"""
    project_id: str = Field(..., description="项目ID")
    groups: List[KnowledgeDocumentDictGroupedResponse] = Field(default_factory=list, description="按 query 分组的文档列表")
    total_queries: int = Field(default=0, description="查询总数")
    total_documents: int = Field(default=0, description="文档总数")


# ============= 项目相关模型 =============

class ProjectKnowledgeConfigRequest(BaseModel):
    """项目知识配置请求"""
    mode: Literal["whitelist", "blacklist", "all"] = Field(default="all", description="配置模式")
    whitelist: List[str] = Field(default_factory=list, description="知识ID白名单")
    blacklist: List[str] = Field(default_factory=list, description="知识ID黑名单")
    
    @validator('whitelist', 'blacklist')
    def validate_id_list(cls, v):
        """验证ID列表：过滤空字符串，确保所有ID都是非空字符串"""
        if isinstance(v, list):
            # 过滤空字符串并去除空白
            filtered = [item.strip() for item in v if item and item.strip()]
            return filtered
        return v
    
    @model_validator(mode='after')
    def validate_config_consistency(self):
        """验证配置一致性：确保mode与对应的列表匹配"""
        if self.mode == "whitelist" and not self.whitelist:
            # whitelist 模式允许空列表（表示没有允许的知识）
            pass
        elif self.mode == "blacklist" and not self.blacklist:
            # blacklist 模式允许空列表（表示没有禁止的知识）
            pass
        return self


class ProjectServiceConfigRequest(BaseModel):
    """项目服务配置请求"""
    mode: Literal["whitelist", "blacklist", "all"] = Field(default="all", description="配置模式")
    whitelist: List[str] = Field(default_factory=list, description="服务ID白名单")
    blacklist: List[str] = Field(default_factory=list, description="服务ID黑名单")
    
    @validator('whitelist', 'blacklist')
    def validate_id_list(cls, v):
        """验证ID列表：过滤空字符串，确保所有ID都是非空字符串"""
        if isinstance(v, list):
            # 过滤空字符串并去除空白
            filtered = [item.strip() for item in v if item and item.strip()]
            return filtered
        return v
    
    @model_validator(mode='after')
    def validate_config_consistency(self):
        """验证配置一致性：确保mode与对应的列表匹配"""
        if self.mode == "whitelist" and not self.whitelist:
            # whitelist 模式允许空列表（表示没有允许的服务）
            pass
        elif self.mode == "blacklist" and not self.blacklist:
            # blacklist 模式允许空列表（表示没有禁止的服务）
            pass
        return self


class ProjectCreateRequest(BaseModel):
    """创建项目请求"""
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, max_length=1000, description="项目描述")
    knowledge_config: Optional[ProjectKnowledgeConfigRequest] = Field(None, description="知识配置")
    service_config: Optional[ProjectServiceConfigRequest] = Field(None, description="服务配置")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError("项目名称不能为空")
        return v.strip()


class ProjectUpdateRequest(BaseModel):
    """更新项目请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, max_length=1000, description="项目描述")
    knowledge_config: Optional[ProjectKnowledgeConfigRequest] = Field(None, description="知识配置")
    service_config: Optional[ProjectServiceConfigRequest] = Field(None, description="服务配置")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError("项目名称不能为空")
        return v.strip() if v else v


class ProjectResponse(BaseModel):
    """项目响应"""
    project_id: str = Field(..., description="项目ID")
    user_id: str = Field(..., description="用户ID")
    name: str = Field(..., description="项目名称")
    file_ids: List[str] = Field(default_factory=list, description="文件ID列表")
    description: Optional[str] = Field(None, description="项目描述")
    knowledge_ids: List[str] = Field(default_factory=list, description="知识ID列表")
    service_ids: List[str] = Field(default_factory=list, description="服务ID列表")
    knowledge_prompt_config_id: Optional[str] = Field(None, description="知识提示配置ID")
    conversation_id: Optional[str] = Field(None, description="会话ID")
    file_ids: List[str] = Field(default_factory=list, description="文件ID列表")
    execution_ids: List[str] = Field(default_factory=list, description="执行ID列表")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")



class ProjectListResponse(BaseModel):
    """项目列表响应"""
    code: int = Field(200, description="响应码")
    message: str = Field("success", description="响应消息")
    data: List[ProjectResponse] = Field(..., description="项目列表")
    total: int = Field(..., description="总数")


class AddFileToProjectRequest(BaseModel):
    """添加文件到项目请求"""
    file_id: str = Field(..., min_length=1, description="文件ID")
    
    @validator('file_id')
    def validate_file_id(cls, v):
        if not v or not v.strip():
            raise ValueError("文件ID不能为空")
        return v.strip()


# ============= 代码生成相关模型 =============


class CodegenTemplateResponse(BaseModel):
    """代码模板响应"""
    template_id: str = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    version: str = Field(..., description="版本")
    user_requirement: str = Field(..., description="用户需求")
    input_file_id: str = Field(..., description="输入文件ID")
    input_file_description: Optional[str] = Field(None, description="输入文件描述")
    parameter_template: Dict[str, Any] = Field(default_factory=dict, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(None, description="参数schema")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出配置")
    generated_code: Optional[str] = Field(None, description="生成的代码")
    code_language: str = Field(..., description="代码语言")
    execution_environment: Optional[Dict[str, Any]] = Field(None, description="执行环境")
    status: str = Field(..., description="状态")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
    created_by: str = Field(..., description="创建者")
    service_id: Optional[str] = Field(None, description="关联的Service ID")
    execution_id: Optional[str] = Field(None, description="执行ID")
    execution_result: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    error_message: Optional[str] = Field(None, description="错误信息")


class CodegenTemplateListResponse(BaseModel):
    """代码模板列表响应"""
    templates: List[CodegenTemplateResponse] = Field(default_factory=list, description="模板列表")
    total: int = Field(default=0, description="总数")


class CodegenUpdateRequest(BaseModel):
    """更新代码模板请求"""
    generated_code: Optional[str] = Field(None, description="生成的代码")
    status: Optional[str] = Field(None, description="状态")
    parameters: Optional[Dict[str, Any]] = Field(None, description="参数")


class CodegenExecuteRequest(BaseModel):
    """执行代码模板请求"""
    parameters: Optional[Dict[str, Any]] = Field(None, description="执行参数（覆盖模板默认参数）")


class CodegenExecuteResponse(BaseModel):
    """执行代码模板响应"""
    execution_id: str = Field(..., description="执行ID")
    template_id: str = Field(..., description="模板ID")
    status: str = Field(..., description="状态")
    created_at: str = Field(..., description="创建时间")


class CodegenExecutionResponse(BaseModel):
    """代码执行记录响应"""
    execution_id: str = Field(..., description="执行ID")
    template_id: str = Field(..., description="模板ID")
    user_id: str = Field(..., description="用户ID")
    code: str = Field(..., description="执行的代码")
    language: str = Field(..., description="代码语言")
    environment: Optional[Dict[str, Any]] = Field(None, description="执行环境")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="执行参数")
    status: str = Field(..., description="执行状态")
    output_file_id: Optional[str] = Field(None, description="输出文件ID")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_log: Optional[str] = Field(None, description="执行日志")
    created_at: Optional[str] = Field(None, description="创建时间")
    started_at: Optional[str] = Field(None, description="开始时间")
    completed_at: Optional[str] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")


class CodegenExecutionListResponse(BaseModel):
    """代码执行记录列表响应"""
    executions: List[CodegenExecutionResponse] = Field(default_factory=list, description="执行记录列表")
    total: int = Field(default=0, description="总数")


# ============= 文件分析相关模型 =============

class FileAnalysisRequest(BaseModel):
    """文件分析请求"""
    file_id: str = Field(..., description="文件ID")
    query: str = Field(default="", description="分析查询/问题（可选）")


class FileAnalysisResponse(BaseModel):
    """文件分析响应"""
    file_id: str = Field(..., description="文件ID")
    query: str = Field(default="", description="用户查询/问题")
    result: str = Field(..., description="分析结果内容")
    success: bool = Field(..., description="是否成功")
    error_message: Optional[str] = Field(None, description="错误信息（如有）")
