"""
MongoDB 数据模型 - 使用 Pydantic 规范数据结构
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union, Tuple, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict, EmailStr, model_validator
from enum import Enum


# ============= 用户相关模型 =============

class User(BaseModel):
    """用户模型"""
    model_config = ConfigDict(extra="allow")  # 允许额外字段（如MongoDB的_id）
    
    user_id: str = Field(..., description="用户唯一标识（UUID格式）", min_length=1)
    username: str = Field(..., description="用户名", min_length=1, max_length=50)
    password: str = Field(..., description="密码（加密存储）", min_length=6, max_length=100)
    email: str = Field(..., description="邮箱地址")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    @field_validator('user_id', mode='before')
    def validate_user_id_not_empty(cls, v):
        """验证user_id非空"""
        if not v or not v.strip():
            raise ValueError("用户ID不能为空")
        return v.strip()
    
    @field_validator('username', mode='before')
    def validate_username_not_empty(cls, v):
        """验证用户名非空并trim"""
        if not v or not v.strip():
            raise ValueError("用户名不能为空")
        return v.strip()
    
    @field_validator('password', mode='before')
    def validate_password(cls, v):
        """验证密码长度"""
        if not v or not v.strip():
            raise ValueError("密码长度至少6位")
        v = v.strip()
        if len(v) < 6:
            raise ValueError("密码长度至少6位")
        if len(v) > 100:
            raise ValueError("密码长度不能超过100位")
        return v
    
    @field_validator('email', mode='before')
    def validate_email(cls, v):
        """验证邮箱格式，允许 .local 域名（用于系统内部默认邮箱）"""
        if not v or not v.strip():
            raise ValueError("邮箱不能为空")
        v = v.strip().lower()
        
        # 允许 .local 域名（系统内部使用的默认邮箱格式）
        if v.endswith('@default.local'):
            return v
        
        # 对于其他邮箱，使用 EmailStr 验证
        try:
            # 尝试使用 EmailStr 验证
            from pydantic import EmailStr
            # 这里我们只是验证格式，不实际转换类型
            # 使用正则表达式进行基本验证
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v):
                raise ValueError("邮箱格式无效")
        except Exception:
            # 如果验证失败，抛出错误
            raise ValueError("邮箱格式无效")
        
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


def user_from_dict(data: Dict[str, Any]) -> User:
    """从字典创建 User 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    
    return User(**data)


# ============= 文件相关模型 =============

class AnalysisStatus(str, Enum):
    """分析状态枚举"""
    PENDING = "pending"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class FileType(BaseModel):
    """文件类型模型"""
    model_config = ConfigDict(extra="allow")

    file_type_id: str = Field(..., description="文件类型ID（唯一标识）", min_length=1)
    name: str = Field(..., description="唯一名称/slug", min_length=1, max_length=100)
    display_name: str = Field(..., description="对用户展示的名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="类型描述", max_length=1000)
    category: Optional[str] = Field(None, description="类型分类", max_length=200)
    extensions: List[str] = Field(..., description="允许的扩展名（含点）", min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")

    @field_validator("file_type_id", "name", "display_name", mode="before")
    @classmethod
    def _validate_not_empty(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("字段不能为空")
        return str(value).strip()

    @field_validator("extensions", mode="before")
    @classmethod
    def _validate_extensions(cls, value: Any) -> List[str]:
        if not value:
            raise ValueError("extensions 不能为空")
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("extensions 必须是字符串列表")
        normalized = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                continue
            normalized.append(item.strip())
        if not normalized:
            raise ValueError("extensions 不能为空")
        return normalized

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class FileInfo(BaseModel):
    """文件信息模型"""
    model_config = ConfigDict(
        extra="allow",  # 允许额外字段（如MongoDB的_id）
        populate_by_name=True  # 允许同时使用字段名和alias
    )
    
    user_id: str = Field(..., description="用户ID", min_length=1, max_length=100)
    file_id: str = Field(..., description="文件ID（UUID格式）", min_length=1)
    filename: str = Field(..., description="文件名", min_length=1)
    file_type_id: str = Field(..., description="文件类型ID", min_length=1)
    file_type_name: str = Field(..., description="文件类型名称（唯一）", min_length=1)
    file_type_display_name: str = Field(..., description="文件类型展示名称", min_length=1)
    file_path: Optional[str] = Field(None, description="文件路径", min_length=1)
    upload_time: datetime = Field(default_factory=datetime.now, description="上传时间")
    last_viewed_time: datetime = Field(default_factory=datetime.now, description="最后查看时间")
    analysis_status: AnalysisStatus = Field(default=AnalysisStatus.UPLOADED, description="分析状态")
    description: Optional[str] = Field(None, description="文件描述")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文件元数据（动态结构）")
    generated_by: Optional[Dict[str, Any]] = Field(None, description="生成信息（如果是生成的文件）")
    
    @field_validator('user_id', 'file_id', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    @field_validator('filename', mode='before')
    def validate_filename(cls, v):
        """验证文件名：不能为空"""
        if not v or not v.strip():
            raise ValueError("文件名不能为空")
        return v.strip()
    
    @field_validator('file_type_id', 'file_type_name', 'file_type_display_name', mode='before')
    def validate_file_type_fields(cls, v):
        """验证文件类型相关字段非空"""
        if not v or not str(v).strip():
            raise ValueError("file_type字段不能为空")
        return str(v).strip()
    
    @field_validator('file_path', mode='before')
    def validate_path(cls, v):
        """验证路径格式"""
        if not v or not v.strip():
            raise ValueError("文件路径不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


class FileRelation(BaseModel):
    """文件关系模型"""
    model_config = ConfigDict(extra="allow")
    
    parent_file_id: str = Field(..., description="父文件ID", min_length=1)
    child_file_id: str = Field(..., description="子文件ID", min_length=1)
    project_id: str = Field(..., description="项目ID", min_length=1)
    description: Optional[str] = Field(None, description="关系描述")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    
    @field_validator('parent_file_id', 'child_file_id', 'project_id', mode='before')
    def validate_not_empty(cls, v):
        """验证字段非空"""
        if not v or not v.strip():
            raise ValueError("字段不能为空")
        return v.strip()
    
    @model_validator(mode='after')
    def validate_parent_child_different(self):
        """验证父文件ID和子文件ID不能相同"""
        if self.parent_file_id == self.child_file_id:
            raise ValueError("父文件ID和子文件ID不能相同")
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，排除 None 值"""
        return self.model_dump(exclude_none=True)


# ============= Project Agent 模型 =============

class AgentMessageRole(str, Enum):
    """Agent 对话角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentMessage(BaseModel):
    """Agent 对话消息（统一字段：role/message/time/extra）"""
    model_config = ConfigDict(extra="allow")
    
    message_id: str = Field(..., description="消息唯一标识", min_length=1)
    role: AgentMessageRole = Field(..., description="角色")
    message: str = Field(..., description="消息内容")
    time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="时间戳"
    )
    extra: Dict[str, Any] = Field(default_factory=dict, description="消息附加信息")
    
    @model_validator(mode="after")
    def _validate_message(cls, values: "AgentMessage") -> "AgentMessage":
        message = (values.message or "").strip()
        allow_empty = (values.extra or {}).get("status") == "streaming"
        if not message and not allow_empty:
            raise ValueError("消息内容不能为空")
        values.message = message
        return values


def agent_message_from_dict(data: Dict[str, Any]) -> AgentMessage:
    """从字典创建 AgentMessage 模型"""
    data = {k: v for k, v in data.items() if k != "_id"}
    if isinstance(data.get("time"), str):
        data["time"] = datetime.fromisoformat(data["time"])
    return AgentMessage(**data)


class AgentConversation(BaseModel):
    """项目级别对话"""
    model_config = ConfigDict(extra="allow")
    
    conversation_id: str = Field(..., description="对话ID", min_length=1)
    project_id: str = Field(..., description="项目ID", min_length=1)
    messages: List[AgentMessage] = Field(default_factory=list, description="消息列表")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")
    context_summary: Optional[str] = Field(None, description="上下文摘要")
    
    def trim_messages(self, limit: int) -> None:
        """裁剪消息数量，保留最新 limit 条"""
        if limit > 0 and len(self.messages) > limit:
            self.messages = self.messages[-limit:]
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


def agent_conversation_from_dict(data: Dict[str, Any]) -> AgentConversation:
    """从字典创建 AgentConversation"""
    data = {k: v for k, v in data.items() if k != "_id"}
    if isinstance(data.get("created_at"), str):
        data["created_at"] = datetime.fromisoformat(data["created_at"])
    if isinstance(data.get("updated_at"), str):
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
    messages = data.get("messages")
    if messages:
        data["messages"] = [agent_message_from_dict(msg).model_dump() for msg in messages]
    return AgentConversation(**data)


# ============= Agent Job 模型 =============


class AgentJobStatus(str, Enum):
    """Agent job 状态"""

    PENDING = "pending"
    RUNNING = "running"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentJobStepStatus(str, Enum):
    """Agent job step 状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentJobStep(BaseModel):
    """单个工作流步骤"""

    name: str = Field(..., description="步骤名称", min_length=1)
    status: AgentJobStepStatus = Field(
        default=AgentJobStepStatus.PENDING, description="步骤状态"
    )
    started_at: Optional[datetime] = Field(default=None, description="开始时间")
    finished_at: Optional[datetime] = Field(default=None, description="结束时间")
    output: Optional[str] = Field(default=None, description="步骤产出或摘要")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="步骤元数据")
    message: Optional[str] = Field(default=None, description="步骤备注信息")


class AgentJob(BaseModel):
    """Agent workflow job"""

    model_config = ConfigDict(extra="allow")

    job_id: str = Field(..., description="job ID", min_length=1)
    user_id: str = Field(..., description="用户ID", min_length=1)
    conversation_id: Optional[str] = Field(
        default=None, description="会话ID（可选，用于关联对话）"
    )
    project_id: str = Field(..., description="项目ID", min_length=1)
    status: AgentJobStatus = Field(default=AgentJobStatus.PENDING, description="状态")
    payload: Dict[str, Any] = Field(default_factory=dict, description="输入负载")
    steps: List[AgentJobStep] = Field(default_factory=list, description="步骤轨迹")
    result: Optional[Dict[str, Any]] = Field(default=None, description="最终结果")
    cancel_requested: bool = Field(default=False, description="是否已请求取消")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="更新时间"
    )
    finished_at: Optional[datetime] = Field(default=None, description="完成时间")

    def to_dict(self) -> Dict[str, Any]:
        payload = self.model_dump(exclude_none=True)
        if payload.get("steps"):
            payload["steps"] = [
                step.model_dump(exclude_none=True)
                if isinstance(step, AgentJobStep)
                else step
                for step in payload["steps"]
            ]
        return payload


def agent_job_from_dict(data: Dict[str, Any]) -> AgentJob:
    """将 Mongo 文档转换成 AgentJob"""
    payload = {k: v for k, v in data.items() if k != "_id"}
    for key in ("created_at", "updated_at", "finished_at"):
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = datetime.fromisoformat(value)
    steps = payload.get("steps")
    if steps:
        payload["steps"] = [
            AgentJobStep(**step) if not isinstance(step, AgentJobStep) else step
            for step in steps
        ]
    return AgentJob(**payload)


# ============= Task相关模型 =============

class HttpMethod(str, Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class ServiceStatus(str, Enum):
    """Service状态枚举"""
    PENDING = "pending"  # 待审核
    ACTIVE = "active"  # 激活状态，可以执行
    INACTIVE = "inactive"  # 停用状态，不可执行
    DEPRECATED = "deprecated"  # 已废弃
    REJECTED = "rejected"  # 审核被拒绝


class ServiceVisibility(str, Enum):
    """Service可见性/权限枚举"""
    PRIVATE = "private"  # 私有，仅创建者可以访问
    PUBLIC = "public"  # 公开，所有人可以访问
    SYSTEM = "system"  # 系统内置，所有人可访问


class TaskRequestConfig(BaseModel):
    """Task请求配置"""
    http_method: HttpMethod = Field(default=HttpMethod.POST, description="HTTP方法")
    headers: Dict[str, str] = Field(default_factory=dict, description="自定义请求头")
    timeout_seconds: int = Field(default=7200, description="请求超时时间（秒）", ge=1, le=7200)
    retry_count: int = Field(default=0, description="重试次数", ge=0, le=5)
    retry_delay_seconds: int = Field(default=1, description="重试延迟（秒）", ge=0, le=60)


class ParameterType(str, Enum):
    """参数类型枚举"""
    DISCRETE = "discrete"  # 离散值（整数）
    CONTINUOUS = "continuous"  # 连续值（浮点数）
    ENUM = "enum"  # 枚举值（固定选项）
    STRING = "string"  # 字符串
    BOOLEAN = "boolean"  # 布尔值


class ParameterDefinition(BaseModel):
    """参数定义模型
    
    定义单个参数的类型、约束和默认值
    """
    type: ParameterType = Field(..., description="参数类型")
    default_value: Any = Field(None, description="默认值")
    description: Optional[str] = Field(None, description="参数描述")
    
    # 连续值约束
    min_value: Optional[Union[int, float]] = Field(None, description="最小值（用于continuous/discrete）")
    max_value: Optional[Union[int, float]] = Field(None, description="最大值（用于continuous/discrete）")
    
    # 枚举值约束
    enum_values: Optional[List[Any]] = Field(None, description="枚举值列表（用于enum类型）")
    
    # 字符串约束
    min_length: Optional[int] = Field(None, description="最小长度（用于string）")
    max_length: Optional[int] = Field(None, description="最大长度（用于string）")
    pattern: Optional[str] = Field(None, description="正则表达式模式（用于string）")
    
    # 是否必填
    required: bool = Field(default=False, description="是否必填")
    
    @field_validator('min_value', 'max_value')
    def validate_range(cls, v, info):
        """验证范围"""
        param_type = info.data.get('type')
        if param_type in [ParameterType.CONTINUOUS, ParameterType.DISCRETE]:
            if v is not None and not isinstance(v, (int, float)):
                raise ValueError(f"{param_type.value}类型的min_value/max_value必须是数字")
        return v
    
    @field_validator('enum_values')
    def validate_enum_values(cls, v, info):
        """验证枚举值"""
        param_type = info.data.get('type')
        if param_type == ParameterType.ENUM:
            if not v or not isinstance(v, list) or len(v) == 0:
                raise ValueError("enum类型必须提供enum_values列表")
        return v
    
    def validate_value(self, value: Any) -> Tuple[bool, Optional[str]]:
        """
        验证参数值是否符合定义
        
        Args:
            value: 要验证的值
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查必填
        if self.required and value is None:
            return False, f"参数为必填项，不能为空"
        
        # 如果值为None且不是必填，允许通过
        if value is None:
            return True, None
        
        # 类型检查
        if self.type == ParameterType.DISCRETE:
            if not isinstance(value, int):
                return False, f"参数应为整数类型，当前值: {value}"
            if self.min_value is not None and value < self.min_value:
                return False, f"参数值 {value} 小于最小值 {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"参数值 {value} 大于最大值 {self.max_value}"
        
        elif self.type == ParameterType.CONTINUOUS:
            if not isinstance(value, (int, float)):
                return False, f"参数应为数值类型，当前值: {value}"
            if self.min_value is not None and value < self.min_value:
                return False, f"参数值 {value} 小于最小值 {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"参数值 {value} 大于最大值 {self.max_value}"
        
        elif self.type == ParameterType.ENUM:
            if value not in self.enum_values:
                return False, f"参数值 {value} 不在允许的枚举值中: {self.enum_values}"
        
        elif self.type == ParameterType.BOOLEAN:
            if not isinstance(value, bool):
                return False, f"参数应为布尔类型，当前值: {value}"
        
        elif self.type == ParameterType.STRING:
            if not isinstance(value, str):
                return False, f"参数应为字符串类型，当前值: {value}"
            if self.min_length is not None and len(value) < self.min_length:
                return False, f"字符串长度 {len(value)} 小于最小长度 {self.min_length}"
            if self.max_length is not None and len(value) > self.max_length:
                return False, f"字符串长度 {len(value)} 大于最大长度 {self.max_length}"
            if self.pattern is not None:
                import re
                if not re.match(self.pattern, value):
                    return False, f"字符串不匹配模式: {self.pattern}"
        
        return True, None


class TaskParameterTemplate(BaseModel):
    """Task参数模板基类
    
    允许任意字段，不同Task可以定义不同的参数结构
    使用Pydantic提供类型验证和文档支持
    """
    model_config = ConfigDict(extra="allow")  # 允许额外字段
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于HTTP请求"""
        return self.model_dump(exclude_none=True)
    
    def merge_with(self, other: Dict[str, Any]) -> Dict[str, Any]:
        """合并其他参数字典（覆盖当前值）"""
        current = self.to_dict()
        return {**current, **other}
    
    def validate_against_schema(self, parameter_schema: Optional[Dict[str, Any]] = None) -> Tuple[bool, Optional[str], Dict[str, str]]:
        """
        根据参数schema验证参数值
        
        Args:
            parameter_schema: 参数定义字典，key为参数名，value为ParameterDefinition或字典
            
        Returns:
            (是否有效, 错误信息, 详细错误字典)
        """
        if not parameter_schema:
            return True, None, {}
        
        errors = {}
        param_dict = self.to_dict()
        
        # 检查所有schema中定义的参数
        for param_name, param_def_raw in parameter_schema.items():
            # 如果param_def_raw是字典，转换为ParameterDefinition
            if isinstance(param_def_raw, dict):
                try:
                    param_def = ParameterDefinition(**param_def_raw)
                except Exception as e:
                    errors[param_name] = f"参数定义无效: {str(e)}"
                    continue
            elif isinstance(param_def_raw, ParameterDefinition):
                param_def = param_def_raw
            else:
                errors[param_name] = f"参数定义格式错误: {type(param_def_raw)}"
                continue
            
            value = param_dict.get(param_name)
            is_valid, error_msg = param_def.validate_value(value)
            if not is_valid:
                errors[param_name] = error_msg
        
        # 检查是否有未定义的参数
        schema_keys = set(parameter_schema.keys())
        param_keys = set(param_dict.keys())
        extra_keys = param_keys - schema_keys
        if extra_keys:
            errors["_extra"] = f"存在未定义的参数: {', '.join(extra_keys)}"
        
        if errors:
            error_msg = "; ".join([f"{k}: {v}" for k, v in errors.items()])
            return False, error_msg, errors
        
        return True, None, {}


class ServiceOutputItemType(str, Enum):
    """Service输出结果项类型枚举"""
    FILE = "file"  # 文件类型输出
    TEXT = "text"  # 文本信息类型输出


class FileOutputItem(BaseModel):
    """文件输出项模型"""
    model_config = ConfigDict(extra="ignore")
    
    type: ServiceOutputItemType = Field(default=ServiceOutputItemType.FILE, description="输出项类型")
    filename: str = Field(..., description="文件名", min_length=1, max_length=500)
    description: str = Field(..., description="文件描述信息", max_length=2000)
    file_type_id: str = Field(..., description="文件类型ID（必需）", min_length=1)
    
    @model_validator(mode='before')
    @classmethod
    def normalize_legacy_fields(cls, data: Any):
        """兼容旧版字段，移除多余属性"""
        if not isinstance(data, dict):
            return data
        normalized = data.copy()
        normalized.setdefault('type', ServiceOutputItemType.FILE)
        if not normalized.get('filename'):
            legacy_value = normalized.get('text') or normalized.get('name')
            if isinstance(legacy_value, str) and legacy_value.strip():
                normalized['filename'] = legacy_value.strip()
        normalized.pop('text', None)  # 旧版字段
        normalized.pop('file_extension', None)
        normalized.pop('mime_type', None)
        return normalized


class TextOutputItem(BaseModel):
    """文本信息输出项模型"""
    model_config = ConfigDict(extra="ignore")
    
    type: ServiceOutputItemType = Field(default=ServiceOutputItemType.TEXT, description="输出项类型")
    filename: str = Field(..., description="文本名", max_length=10000)
    description: str = Field(..., description="文本描述信息", max_length=2000)
    
    @model_validator(mode='before')
    @classmethod
    def normalize_legacy_fields(cls, data: Any):
        """兼容旧版字段（text、file_extension 等）"""
        if not isinstance(data, dict):
            return data
        normalized = data.copy()
        normalized.setdefault('type', ServiceOutputItemType.TEXT)
        if not normalized.get('filename'):
            legacy_value = normalized.get('text') or normalized.get('name')
            if isinstance(legacy_value, str) and legacy_value.strip():
                normalized['filename'] = legacy_value.strip()
        normalized.pop('text', None)
        normalized.pop('file_extension', None)
        normalized.pop('mime_type', None)
        return normalized


class ServiceOutputConfig(BaseModel):
    """Service输出结果配置"""
    items: List[Union[FileOutputItem, TextOutputItem, Dict[str, Any]]] = Field(
        ..., 
        description="输出结果项列表，每个项可以是文件或文本信息",
        min_length=1
    )
    collection_description: Optional[str] = Field(None, description="集合整体描述", max_length=2000)
    
    @field_validator('items', mode='before')
    def validate_items(cls, v):
        """验证输出项列表"""
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("输出结果项列表不能为空")
        
        validated_items = []
        for idx, item in enumerate(v):
            if isinstance(item, (FileOutputItem, TextOutputItem)):
                # 如果是 FileOutputItem，验证 file_type_id
                if isinstance(item, FileOutputItem):
                    if not item.file_type_id or not item.file_type_id.strip():
                        raise ValueError(
                            f"'output_config.items[{idx}].file_type_id' 必须是非空字符串"
                        )
                validated_items.append(item)
            elif isinstance(item, dict):
                item_type = item.get('type')
                if item_type == ServiceOutputItemType.FILE or item_type == 'file':
                    # 验证 file_type_id
                    if 'file_type_id' not in item:
                        raise ValueError(
                            f"'output_config.items[{idx}]' 缺少必需字段 'file_type_id'"
                        )
                    if not isinstance(item['file_type_id'], str) or not item['file_type_id'].strip():
                        raise ValueError(
                            f"'output_config.items[{idx}].file_type_id' 必须是非空字符串"
                        )
                    try:
                        validated_items.append(FileOutputItem(**item))
                    except Exception as e:
                        # 如果转换失败，抛出更详细的错误
                        raise ValueError(
                            f"'output_config.items[{idx}]' 转换为 FileOutputItem 失败: {str(e)}"
                        )
                elif item_type == ServiceOutputItemType.TEXT or item_type == 'text':
                    try:
                        validated_items.append(TextOutputItem(**item))
                    except Exception as e:
                        # 如果转换失败，抛出更详细的错误
                        raise ValueError(
                            f"'output_config.items[{idx}]' 转换为 TextOutputItem 失败: {str(e)}"
                        )
                else:
                    # 如果没有 type 字段或类型未知，检查是否是文件类型（通过其他特征判断）
                    # 如果看起来像文件类型但没有 file_type_id，给出警告
                    if 'filename' in item and 'file_type_id' not in item:
                        raise ValueError(
                            f"'output_config.items[{idx}]' 缺少 'type' 字段，且未指定 'file_type_id'。"
                            f"如果是文件类型，必须包含 'type': 'file' 和 'file_type_id' 字段"
                        )
                    validated_items.append(item)
            else:
                raise ValueError(f"输出项类型不支持: {type(item)}")
        
        return validated_items


class OutputTemplate(BaseModel):
    """Service输出模板模型
    
    定义Service的输出结构、文件类型、元数据字段和验证规则
    """
    structure: Dict[str, Any] = Field(default_factory=dict, description="预期输出结构定义")
    file_types: List[str] = Field(default_factory=list, description="预期的输出文件类型列表")
    metadata_fields: List[str] = Field(default_factory=list, description="预期的元数据字段列表")
    validation_rules: Dict[str, Any] = Field(default_factory=dict, description="输出验证规则")
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储"""
        return self.model_dump(exclude_none=True)


class ServiceInfo(BaseModel):
    """Service信息模型"""
    model_config = ConfigDict(extra="allow")  # 允许额外字段（如MongoDB的_id）
    
    service_id: str = Field(..., description="Service ID（唯一标识）", min_length=1, max_length=100)
    name: str = Field(..., description="Service名称", min_length=1, max_length=200)
    description: Optional[str] = Field(None, description="Service描述", max_length=1000)
    version: str = Field(default="1.0.0", description="Service版本", max_length=50)
    
    # 远程服务器配置
    baseurl: str = Field(..., description="基础URL（IP和端口号，如 http://192.168.1.1:8080）", min_length=1)
    service_suffix: str = Field(..., description="Service后缀（与baseurl拼接后访问对应的service，如 /api/service）", min_length=1)
    download_suffix: Optional[str] = Field(None, description="Download后缀（如果输出存在文件则需要配置，用于下载生成文件，如 /api/download）")
    
    # 请求配置
    request_config: TaskRequestConfig = Field(default_factory=TaskRequestConfig, description="请求配置")
    
    # 参数模板（使用Pydantic模型，允许任意字段）
    parameter_template: TaskParameterTemplate = Field(default_factory=TaskParameterTemplate, description="参数模板，定义参数的默认值和类型")
    
    # 参数定义schema（定义参数的约束和类型）
    parameter_schema: Optional[Dict[str, ParameterDefinition]] = Field(default=None, description="参数定义schema，定义每个参数的类型、范围和约束")
    
    # 接受的文件类型配置
    accepted_files: Optional[Dict[str, Any]] = Field(
        None, 
        description="接受的文件类型配置，格式：{filename: {file_type_ids: [...], description: ...}}"
    )
    
    # 输出结果配置
    output_config: Optional[ServiceOutputConfig] = Field(None, description="输出结果配置，定义输出结果项集合（文件或文本信息）")
    
    # 权限
    visibility: ServiceVisibility = Field(default=ServiceVisibility.PRIVATE, description="Service可见性（private/public/system）")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    created_by: str = Field(..., description="创建者用户ID（必填）")
    
    @field_validator('service_id', 'name', 'created_by', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    @field_validator('baseurl', mode='before')
    def validate_baseurl(cls, v):
        """验证baseurl格式"""
        if not v or not v.strip():
            raise ValueError("baseurl不能为空")
        v = v.strip()
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("baseurl必须以http://或https://开头")
        # 确保baseurl不以/结尾
        if v.endswith('/'):
            v = v.rstrip('/')
        return v
    
    @field_validator('service_suffix', mode='before')
    def validate_service_suffix(cls, v):
        """验证service后缀格式"""
        if not v or not v.strip():
            raise ValueError("service_suffix不能为空")
        v = v.strip()
        # 确保service以/开头
        if not v.startswith('/'):
            v = '/' + v
        return v
    
    def get_service_url(self) -> str:
        """获取完整的service URL（baseurl + service）"""
        return f"{self.baseurl}{self.service_suffix}"
    
    def get_download_url(self) -> Optional[str]:
        """获取完整的download URL（baseurl + download），如果download未配置则返回None"""
        if self.download_suffix:
            return f"{self.baseurl}{self.download_suffix}"
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储"""
        data = self.model_dump()
        # 处理嵌套模型
        if isinstance(data.get('request_config'), TaskRequestConfig):
            data['request_config'] = data['request_config'].model_dump()
        if isinstance(data.get('parameter_template'), TaskParameterTemplate):
            data['parameter_template'] = data['parameter_template'].model_dump()
        # parameter_schema需要特殊处理
        if isinstance(data.get('parameter_schema'), dict):
            schema_dict = {}
            for key, value in data['parameter_schema'].items():
                if isinstance(value, ParameterDefinition):
                    schema_dict[key] = value.model_dump()
                else:
                    schema_dict[key] = value
            data['parameter_schema'] = schema_dict
        # 处理output_config
        if isinstance(data.get('output_config'), ServiceOutputConfig):
            output_config_dict = data['output_config'].model_dump()
            # 处理items中的模型对象
            if 'items' in output_config_dict:
                items_list = []
                for item in output_config_dict['items']:
                    if isinstance(item, (FileOutputItem, TextOutputItem)):
                        items_list.append(item.model_dump())
                    else:
                        items_list.append(item)
                output_config_dict['items'] = items_list
            data['output_config'] = output_config_dict
        return data


class ServiceExecutionStatus(str, Enum):
    """Service执行状态枚举"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


class ServiceExecution(BaseModel):
    """Service执行记录模型
    
    注意：此模型设计为支持多文件输入/输出（input_file_ids/output_file_ids）。
    当前原型实现可能仅支持单文件，但数据模型已为多文件场景做好准备。
    """
    model_config = ConfigDict(extra="allow")  # 允许额外字段（如MongoDB的_id）
    
    execution_id: str = Field(..., description="执行ID（唯一标识）", min_length=1)
    service_id: str = Field(..., description="Service ID", min_length=1)
    service_name: Optional[str] = Field(None, description="Service 名称")
    user_id: str = Field(..., description="用户ID", min_length=1)
    input_file_ids: List[str] = Field(..., description="输入文件ID列表（UUID格式），支持多文件输入", min_length=1)
    output_file_ids: Optional[List[str]] = Field(None, description="输出文件ID列表（UUID格式），支持多文件输出")
    project_id: Optional[str] = Field(None, description="项目ID")
    
    # 执行状态
    status: ServiceExecutionStatus = Field(default=ServiceExecutionStatus.PENDING, description="执行状态")
    
    # 执行参数
    parameters: Dict[str, Any] = Field(default_factory=dict, description="执行参数")
    
    # 执行结果
    response_data: Optional[Dict[str, Any]] = Field(None, description="远程服务器响应数据")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")
    
    @field_validator('execution_id', 'service_id', 'user_id', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    @field_validator('input_file_ids', mode='before')
    def validate_input_file_ids(cls, v):
        """验证输入文件ID列表"""
        if isinstance(v, str):
            # 向后兼容：单个字符串转换为列表
            v = [v]
        if not isinstance(v, list):
            raise ValueError("input_file_ids必须是字符串列表")
        if len(v) == 0:
            raise ValueError("input_file_ids不能为空列表")
        # 验证列表中的每个元素都是非空字符串
        validated_list = []
        for file_id in v:
            if not file_id or not str(file_id).strip():
                raise ValueError("input_file_ids中的文件ID不能为空")
            validated_list.append(str(file_id).strip())
        return validated_list
    
    @field_validator('output_file_ids', mode='before')
    def validate_output_file_ids(cls, v):
        """验证输出文件ID列表"""
        if v is None:
            return None
        if isinstance(v, str):
            # 向后兼容：单个字符串转换为列表
            v = [v]
        if not isinstance(v, list):
            raise ValueError("output_file_ids必须是字符串列表或None")
        # 验证列表中的每个元素都是非空字符串
        validated_list = []
        for file_id in v:
            if not file_id or not str(file_id).strip():
                raise ValueError("output_file_ids中的文件ID不能为空")
            validated_list.append(str(file_id).strip())
        return validated_list if len(validated_list) > 0 else None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


# 辅助函数：从 MongoDB 文档创建模型实例
def file_info_from_dict(data: Dict[str, Any]) -> FileInfo:
    """从字典创建 FileInfo 模型（仅支持蛇形命名）"""
    # 移除MongoDB的_id字段（如果存在）
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('upload_time'), str):
        data['upload_time'] = datetime.fromisoformat(data['upload_time'])
    if isinstance(data.get('last_viewed_time'), str):
        data['last_viewed_time'] = datetime.fromisoformat(data['last_viewed_time'])
    
    # 处理analysis_status枚举
    if 'analysis_status' in data and isinstance(data['analysis_status'], str):
        data['analysis_status'] = AnalysisStatus(data['analysis_status'])
    
    # 确保metadata是字典
    if 'metadata' not in data:
        data['metadata'] = {}
    elif not isinstance(data['metadata'], dict):
        # 如果不是字典，尝试转换为字典
        if hasattr(data['metadata'], 'model_dump'):
            data['metadata'] = data['metadata'].model_dump()
        else:
            data['metadata'] = {}
    
    return FileInfo(**data)


def file_type_from_dict(data: Dict[str, Any]) -> FileType:
    """从字典创建 FileType 模型"""
    payload = {k: v for k, v in data.items() if k != "_id"}
    for key in ("created_at", "updated_at"):
        value = payload.get(key)
        if isinstance(value, str):
            payload[key] = datetime.fromisoformat(value)
    return FileType(**payload)


def service_info_from_dict(data: Dict[str, Any]) -> ServiceInfo:
    """从字典创建 ServiceInfo 模型"""
    # 移除MongoDB的_id字段（如果存在）
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 检查必需字段（向后兼容性检查）
    if 'baseurl' not in data or not data.get('baseurl'):
        raise ValueError(f"Service文档缺少必需字段 'baseurl' (service_id: {data.get('service_id', 'unknown')})")
    if 'service_suffix' not in data or not data.get('service_suffix'):
        raise ValueError(f"Service文档缺少必需字段 'service_suffix' (service_id: {data.get('service_id', 'unknown')})")
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    
    # 处理嵌套模型
    if isinstance(data.get('request_config'), dict):
        data['request_config'] = TaskRequestConfig(**data['request_config'])
    if isinstance(data.get('parameter_template'), dict):
        data['parameter_template'] = TaskParameterTemplate(**data['parameter_template'])
    # 处理parameter_schema
    if isinstance(data.get('parameter_schema'), dict):
        schema_dict = {}
        for key, value in data['parameter_schema'].items():
            if isinstance(value, dict):
                schema_dict[key] = ParameterDefinition(**value)
            elif isinstance(value, ParameterDefinition):
                schema_dict[key] = value
            else:
                schema_dict[key] = value
        data['parameter_schema'] = schema_dict
    
    # 处理output_config
    if isinstance(data.get('output_config'), dict):
        try:
            output_config_dict = data['output_config']
            # 处理items列表
            if 'items' in output_config_dict and isinstance(output_config_dict['items'], list):
                items_list = []
                for item in output_config_dict['items']:
                    if isinstance(item, dict):
                        item_type = item.get('type')
                        if item_type == ServiceOutputItemType.FILE:
                            try:
                                items_list.append(FileOutputItem(**item))
                            except Exception:
                                # 如果转换失败，保持字典格式（向后兼容）
                                items_list.append(item)
                        elif item_type == ServiceOutputItemType.TEXT:
                            try:
                                items_list.append(TextOutputItem(**item))
                            except Exception:
                                # 如果转换失败，保持字典格式（向后兼容）
                                items_list.append(item)
                        else:
                            # 如果没有 type 字段或类型未知，保持字典格式
                            items_list.append(item)
                    elif isinstance(item, (FileOutputItem, TextOutputItem)):
                        items_list.append(item)
                    else:
                        items_list.append(item)
                output_config_dict['items'] = items_list
            data['output_config'] = ServiceOutputConfig(**output_config_dict)
        except Exception:
            # 如果转换失败，保持字典格式（向后兼容）
            pass
    
    # 确保 accepted_files 字段存在（即使为 None，用于向后兼容）
    if 'accepted_files' not in data:
        data['accepted_files'] = None
    
    return ServiceInfo(**data)


def service_execution_from_dict(data: Dict[str, Any]) -> ServiceExecution:
    """从字典创建 ServiceExecution 模型（仅支持蛇形命名）
    
    支持向后兼容：如果数据中包含旧的单文件字段（input_file_id/output_file_id），
    会自动转换为新的列表格式（input_file_ids/output_file_ids）。
    """
    # 移除MongoDB的_id字段（如果存在）
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('started_at'), str):
        data['started_at'] = datetime.fromisoformat(data['started_at'])
    if isinstance(data.get('completed_at'), str):
        data['completed_at'] = datetime.fromisoformat(data['completed_at'])
    
    # 向后兼容：将旧的单文件字段转换为新的列表格式
    if 'input_file_ids' not in data and 'input_file_id' in data:
        # 如果存在旧的单文件字段，转换为列表
        old_input_file_id = data.pop('input_file_id')
        if old_input_file_id:
            data['input_file_ids'] = [old_input_file_id] if isinstance(old_input_file_id, str) else old_input_file_id
        else:
            data['input_file_ids'] = []
    
    if 'output_file_ids' not in data and 'output_file_id' in data:
        # 如果存在旧的单文件字段，转换为列表
        old_output_file_id = data.pop('output_file_id')
        if old_output_file_id:
            data['output_file_ids'] = [old_output_file_id] if isinstance(old_output_file_id, str) else old_output_file_id
        else:
            data['output_file_ids'] = None
    
    return ServiceExecution(**data)


# ============= 知识图谱相关模型 =============

class KnowledgeScope(str, Enum):
    """知识范围"""
    PRIVATE = "private"
    PUBLIC = "public"
    SYSTEM = "system"


class KnowledgeRelationSummary(BaseModel):
    """知识关系摘要（三元组）"""
    model_config = ConfigDict(extra="allow")
    
    from_entity: str = Field(..., description="头实体", min_length=1)
    relation: str = Field(..., description="关系类型", min_length=1)
    end_entity: str = Field(..., description="尾实体", min_length=1)
    
    @field_validator('from_entity', 'relation', 'end_entity', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()


class Knowledge(BaseModel):
    """知识模型"""
    model_config = ConfigDict(extra="allow")
    
    knowledge_id: str = Field(..., description="知识ID（唯一标识）", min_length=1)
    user_id: Optional[str] = Field(None, description="所属用户（系统/公共知识为空）")
    title: str = Field(..., description="标题", min_length=1)
    description: str = Field(..., description="描述", min_length=1)
    relation_summary: KnowledgeRelationSummary = Field(..., description="关系摘要（三元组）")
    scope: KnowledgeScope = Field(default=KnowledgeScope.PRIVATE, description="知识范围（private/public/system）")
    source: Optional[str] = Field(None, description="来源说明")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="自定义元数据")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")
    shared_at: Optional[datetime] = Field(None, description="分享时间")
    share_note: Optional[str] = Field(None, description="分享说明")
    
    @field_validator('knowledge_id', 'title', 'description', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


class KnowledgePromptConfig(BaseModel):
    """Prompt配置（支持多模板）"""
    model_config = ConfigDict(extra="allow")

    user_id: str = Field(..., description="用户ID")
    template_id: str = Field(..., description="模板ID（必填，唯一标识）")
    name: Optional[str] = Field(None, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    entity_prompt: Dict[str, str] = Field(..., description="实体抽取描述（字典格式：{实体名: 描述, ...}）")
    relation_prompt: Dict[str, str] = Field(..., description="关系抽取描述（字典格式：{关系名: 描述, ...}）")
    constraints: Optional[str] = Field(None, description="输出约束")
    is_default: bool = Field(False, description="是否为默认模板")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")


def knowledge_prompt_config_from_dict(data: Dict[str, Any]) -> KnowledgePromptConfig:
    """从字典创建 KnowledgePromptConfig 模型"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理时间字段
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    
    # 兼容旧数据：如果 template_id 为 None，生成一个
    if data.get('template_id') is None:
        import uuid
        data['template_id'] = str(uuid.uuid4())
    
    # 验证 entity_prompt 和 relation_prompt 必须是字典格式
    if 'entity_prompt' in data and not isinstance(data['entity_prompt'], dict):
        raise ValueError("entity_prompt必须是字典格式：{实体名: 描述, ...}")
    if 'relation_prompt' in data and not isinstance(data['relation_prompt'], dict):
        raise ValueError("relation_prompt必须是字典格式：{关系名: 描述, ...}")
    
    return KnowledgePromptConfig(**data)


def knowledge_from_dict(data: Dict[str, Any]) -> Knowledge:
    """从字典创建 Knowledge 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 向后兼容：如果存在 owner_id 但没有 user_id，则使用 owner_id
    if 'user_id' not in data and 'owner_id' in data:
        data['user_id'] = data.pop('owner_id')
    
    # 向后兼容：如果缺少 title 字段，使用 description 的前50个字符作为默认标题
    if 'title' not in data or not data.get('title'):
        if 'description' in data and data['description']:
            # 使用描述的前50个字符作为默认标题
            desc = str(data['description'])
            data['title'] = desc[:50] + ('...' if len(desc) > 50 else '')
        else:
            # 如果连描述都没有，使用默认标题
            data['title'] = 'Untitled Knowledge'
    
    # 处理 relation_summary 字段
    relation_summary = data.get('relation_summary')
    if relation_summary:
        if isinstance(relation_summary, dict):
            # 如果已经是字典，检查字段名格式
            if 'from_entity' in relation_summary:
                # 蛇形命名格式
                data['relation_summary'] = KnowledgeRelationSummary(**relation_summary)
            elif 'from' in relation_summary:
                # 兼容旧格式：from, relation, end
                data['relation_summary'] = KnowledgeRelationSummary(
                    from_entity=relation_summary.get('from', ''),
                    relation=relation_summary.get('relation', ''),
                    end_entity=relation_summary.get('end', '')
                )
            else:
                # 尝试直接创建
                data['relation_summary'] = KnowledgeRelationSummary(**relation_summary)
        else:
            # 如果不是字典，可能需要特殊处理
            raise ValueError(f"relation_summary 必须是字典类型，得到: {type(relation_summary)}")
    
    # 处理 scope 字段（如果存在）
    if 'scope' in data:
        scope_value = data.get('scope')
        if isinstance(scope_value, str):
            try:
                data['scope'] = KnowledgeScope(scope_value)
            except ValueError:
                # 如果值无效，使用默认值
                data['scope'] = KnowledgeScope.PRIVATE
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    if isinstance(data.get('shared_at'), str):
        data['shared_at'] = datetime.fromisoformat(data['shared_at'])
    
    return Knowledge(**data)


# ==================== Project 相关模型 ====================

class ProjectKnowledgeConfig(BaseModel):
    """项目知识配置"""
    mode: Literal["whitelist", "blacklist", "all"] = Field(default="all", description="配置模式：whitelist=白名单模式，blacklist=黑名单模式，all=全部可见")
    whitelist: List[str] = Field(default_factory=list, description="知识ID白名单（mode=whitelist时生效）")
    blacklist: List[str] = Field(default_factory=list, description="知识ID黑名单（mode=blacklist时生效）")


class ProjectServiceConfig(BaseModel):
    """项目服务配置"""
    mode: Literal["whitelist", "blacklist", "all"] = Field(default="all", description="配置模式：whitelist=白名单模式，blacklist=黑名单模式，all=全部可见")
    whitelist: List[str] = Field(default_factory=list, description="服务ID白名单（mode=whitelist时生效）")
    blacklist: List[str] = Field(default_factory=list, description="服务ID黑名单（mode=blacklist时生效）")


class Project(BaseModel):
    """项目模型"""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    project_id: str = Field(..., description="项目ID", min_length=1)
    user_id: str = Field(..., description="所属用户ID", min_length=1)
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(None, max_length=1000, description="项目描述")
    konwledge_ids: List[str] = Field(default_factory=list, description="项目关联的知识ID列表")
    service_ids: List[str] = Field(default_factory=list, description="项目关联的服务ID列表")
    # knowledge_config: ProjectKnowledgeConfig = Field(default_factory=ProjectKnowledgeConfig, description="知识配置")
    # service_config: ProjectServiceConfig = Field(default_factory=ProjectServiceConfig, description="服务配置")
    knowledge_prompt_config_id: Optional[str] = Field(None, description="知识提示配置ID")
    conversation_id: Optional[str] = Field(None, description="会话ID")
    file_ids: List[str] = Field(default_factory=list, description="项目包含的文件ID列表（UUID格式）")
    knowledge_ids: List[str] = Field(default_factory=list, description="项目关联的知识ID列表")
    execution_ids: List[str] = Field(default_factory=list, description="项目关联的执行ID列表（execution_id）")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")
    
    @field_validator('project_id', 'user_id', 'name', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        data = self.model_dump(exclude_none=False)
        # 处理嵌套配置对象
        if isinstance(data.get("knowledge_config"), dict):
            data["knowledge_config"] = data["knowledge_config"]
        elif hasattr(data.get("knowledge_config"), "model_dump"):
            data["knowledge_config"] = data["knowledge_config"].model_dump()
        if isinstance(data.get("service_config"), dict):
            data["service_config"] = data["service_config"]
        elif hasattr(data.get("service_config"), "model_dump"):
            data["service_config"] = data["service_config"].model_dump()
        return data


def project_from_dict(data: Dict[str, Any]) -> Project:
    """从字典创建 Project 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    
    # 处理嵌套的配置对象
    if isinstance(data.get('knowledge_config'), dict):
        data['knowledge_config'] = ProjectKnowledgeConfig(**data['knowledge_config'])
    
    if isinstance(data.get('service_config'), dict):
        data['service_config'] = ProjectServiceConfig(**data['service_config'])
    
    return Project(**data)


# ============= 代码生成相关模型 =============

class CodegenLanguage(str, Enum):
    """代码语言枚举"""
    PYTHON = "python"
    R = "r"
    JULIA = "julia"
    BASH = "bash"


class CodegenStatus(str, Enum):
    """代码生成模板状态枚举"""
    TEMPLATE_GENERATED = "template_generated"  # 模板已生成
    TEMPLATE_CONFIRMED = "template_confirmed"  # 模板已确认
    CODE_GENERATED = "code_generated"  # 代码已生成
    EXECUTING = "executing"  # 执行中
    EXECUTION_COMPLETED = "execution_completed"  # 执行完成
    FINALIZED = "finalized"  # 最终确认并保存
    FAILED = "failed"  # 执行失败



class CodegenTemplate(BaseModel):
    """代码生成模板模型"""
    model_config = ConfigDict(extra="allow")  # 允许额外字段（如MongoDB的_id）
    
    template_id: str = Field(..., description="模板ID（唯一标识）", min_length=1)
    user_id: str = Field(..., description="用户ID", min_length=1)
    user_requirement: str = Field(..., description="用户需求描述", min_length=1)
    code_language: CodegenLanguage = Field(default=CodegenLanguage.PYTHON, description="代码语言（python/r/julia/bash）")
    generated_code: Optional[str] = Field(None, description="生成的代码")
    # 暂时参考service的parameter_template和parameter_schema和output_config结构
    parameter_template: TaskParameterTemplate = Field(default_factory=TaskParameterTemplate, description="参数模板")
    parameter_schema: Optional[Dict[str, Any]] = Field(None, description="参数schema")
    output_config: ServiceOutputConfig = Field(default_factory=ServiceOutputConfig, description="输出配置")
    status: CodegenStatus = Field(..., description="状态（template_generated/template_confirmed/code_generated/finalized）")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据（动态结构），储存关于代码执行相关的信息，如依赖位置等")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    
    @field_validator('template_id', 'user_id', 'user_requirement', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)
        


class CodegenExecutionStatus(str, Enum):
    """代码执行状态枚举"""
    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 执行中
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消


class CodegenExecution(BaseModel):
    """代码执行记录模型"""
    model_config = ConfigDict(extra="allow")  # 允许额外字段（如MongoDB的_id）
    
    execution_id: str = Field(..., description="执行ID（唯一标识）", min_length=1)
    template_id: str = Field(..., description="模板ID", min_length=1)
    user_id: str = Field(..., description="用户ID", min_length=1)
    parameters: Dict[str, Any] = Field(default_factory=dict, description="执行参数")
    status: CodegenExecutionStatus = Field(default=CodegenExecutionStatus.PENDING, description="执行状态")
    output_file_id: Optional[str] = Field(None, description="输出文件ID")
    error_message: Optional[str] = Field(None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    started_at: Optional[datetime] = Field(None, description="开始执行时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")
    
    @field_validator('execution_id', 'template_id', 'user_id', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


def codegen_template_from_dict(data: Dict[str, Any]) -> CodegenTemplate:
    """从字典创建 CodegenTemplate 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    
    return CodegenTemplate(**data)


def codegen_execution_from_dict(data: Dict[str, Any]) -> CodegenExecution:
    """从字典创建 CodegenExecution 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('started_at'), str):
        data['started_at'] = datetime.fromisoformat(data['started_at'])
    if isinstance(data.get('completed_at'), str):
        data['completed_at'] = datetime.fromisoformat(data['completed_at'])
    
    return CodegenExecution(**data)


# ============= KnowledgeDocumentDict 相关模型 =============

class KnowledgeDocumentDict(BaseModel):
    """知识文档字典模型（用于存储 KnowledgeDocument + query）"""
    model_config = ConfigDict(extra="allow")
    
    title: str = Field(..., description="文献标题（主键，唯一标识）", min_length=1)
    project_id: str = Field(..., description="项目ID", min_length=1)
    query: str = Field(..., description="用户查询字符串", min_length=1)
    source: str = Field(..., description="数据源标识，如 pubmed/arxiv/crossref")
    snippet: str = Field("", description="摘要或内容片段")
    url: Optional[str] = Field(None, description="文献链接")
    doi: Optional[str] = Field(None, description="DOI，如有")
    published_at: Optional[str] = Field(None, description="发表时间（ISO字符串或年份）")
    authors: List[str] = Field(default_factory=list, description="作者列表")
    journal: Optional[str] = Field(None, description="期刊或会议")
    source_type: Optional[str] = Field(None, description="文献类型")
    score: Optional[float] = Field(None, description="相关性评分")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="更新时间")
    
    @field_validator('title', 'project_id', 'query', 'source', mode='before')
    def validate_not_empty(cls, v):
        """验证非空字符串"""
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储（使用蛇形命名）"""
        return self.model_dump(exclude_none=True)


def knowledge_document_dict_from_dict(data: Dict[str, Any]) -> KnowledgeDocumentDict:
    """从字典创建 KnowledgeDocumentDict 模型（仅支持蛇形命名）"""
    data = {k: v for k, v in data.items() if k != "_id"}
    
    # 处理 datetime 字段
    if isinstance(data.get('created_at'), str):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
    if isinstance(data.get('updated_at'), str):
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
    
    return KnowledgeDocumentDict(**data)


def file_relation_from_dict(data: Dict[str, Any]) -> FileRelation:
    """
    从字典创建 FileRelation 对象
    
    Args:
        data: 包含文件关系数据的字典
    
    Returns:
        FileRelation 对象
    
    Raises:
        ValueError: 如果数据验证失败
    """
    try:
        # 处理 MongoDB 的 _id 字段
        if "_id" in data:
            data = {k: v for k, v in data.items() if k != "_id"}
        
        # 处理 datetime 字段
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        elif "created_at" not in data:
            data["created_at"] = datetime.now()
        
        return FileRelation(**data)
    except Exception as e:
        from pydantic import ValidationError
        if isinstance(e, ValidationError):
            raise ValueError(f"文件关系数据验证失败: {e}")
        raise


# ============= Memory 相关模型 =============


class Memory(BaseModel):
    """单个记忆模型。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    memory_id: str = Field(..., description="记忆ID（UUID格式）")
    content: str = Field(..., min_length=1, max_length=2000, description="记忆内容")
    importance: float = Field(..., ge=0.0, le=1.0, description="重要性评分 [0.0, 1.0]")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="更新时间",
    )

    @field_validator("memory_id", mode="before")
    @classmethod
    def _validate_memory_id(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("memory_id 不能为空")
        return str(value).strip()

    @field_validator("content", mode="before")
    @classmethod
    def _validate_content(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("记忆内容不能为空")
        text = str(value).strip()
        if len(text) > 2000:
            # 统一在模型层截断，避免异常内容撑爆存储
            text = text[:2000]
        return text

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储。"""
        return self.model_dump(exclude_none=False)


class MemoryCollection(BaseModel):
    """项目记忆集合模型。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    project_id: str = Field(..., description="项目ID（主键）")
    memory_list: List["Memory"] = Field(default_factory=list, description="记忆列表")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="更新时间",
    )

    @field_validator("project_id", mode="before")
    @classmethod
    def _validate_project_id(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("project_id 不能为空")
        return str(value).strip()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储。"""
        return self.model_dump(exclude_none=False)


def memory_collection_from_dict(data: Dict[str, Any]) -> MemoryCollection:
    """从字典创建 MemoryCollection 模型。"""
    payload = {k: v for k, v in data.items() if k != "_id"}

    # 处理 memory_list
    memory_items: List[Memory] = []
    for mem in payload.get("memory_list", []) or []:
        if isinstance(mem, Memory):
            memory_items.append(mem)
        elif isinstance(mem, dict):
            memory_items.append(Memory(**mem))
    payload["memory_list"] = memory_items

    # 处理时间字段
    for ts_key in ("created_at", "updated_at"):
        value = payload.get(ts_key)
        if isinstance(value, str):
            # 兼容 ISO8601 / 带 Z 的时间格式
            payload[ts_key] = datetime.fromisoformat(value.replace("Z", "+00:00"))

    return MemoryCollection(**payload)

