"""
KOOK 协议配置
"""

from typing import Optional

from pydantic import BaseModel, Field


class KookConfig(BaseModel):
    """KOOK 协议配置模型"""

    bot_token: str = Field(..., description="KOOK Bot Token")
    verify_token: Optional[str] = Field(None, description="KOOK 回调 Verify Token")
    encrypt_key: Optional[str] = Field(None, description="KOOK 回调 Encrypt Key（可选）")
    api_base: str = Field("https://www.kookapp.cn/api/v3", description="KOOK API 基础地址")
    event_mode: str = Field("webhook", description="事件模式：webhook 或 websocket")

    class Config:
        extra = "allow"

