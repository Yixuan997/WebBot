"""
QQ协议配置

使用Pydantic进行配置验证
"""

from typing import Optional

from pydantic import BaseModel, Field


class QQConfig(BaseModel):
    """QQ官方协议配置"""

    app_id: str = Field(..., description="QQ开放平台AppID")
    app_secret: str = Field(..., description="QQ开放平台AppSecret")
    token: Optional[str] = Field(None, description="Bot Token（可选）")

    class Config:
        extra = "allow"  # 允许额外字段
