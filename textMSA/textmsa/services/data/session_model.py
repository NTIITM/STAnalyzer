"""
Session Model - MongoDB 数据模型
"""
from datetime import datetime, timezone
from typing import Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class Session(BaseModel):
    """Session 模型。"""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    session_id: str = Field(..., description="Session ID（主键）")
    user_id: str = Field(..., description="用户ID")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="创建时间",
    )
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=12),
        description="过期时间",
    )


    @field_validator("session_id", mode="before")
    @classmethod
    def _validate_session_id(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("session_id 不能为空")
        return str(value).strip()

    @field_validator("user_id", mode="before")
    @classmethod
    def _validate_user_id(cls, value: Any) -> str:
        if not value or not str(value).strip():
            raise ValueError("user_id 不能为空")
        return str(value).strip()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，用于 MongoDB 存储。"""
        return self.model_dump(exclude_none=False)


def session_from_dict(data: Dict[str, Any]) -> Session:
    """从字典创建 Session 模型。"""
    payload = {k: v for k, v in data.items() if k != "_id"}

    # 处理时间字段
    for ts_key in ("created_at", "expires_at"):
        value = payload.get(ts_key)
        if isinstance(value, str):
            payload[ts_key] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif isinstance(value, float):
            payload[ts_key] = datetime.fromtimestamp(value, timezone.utc)

    return Session(**payload)