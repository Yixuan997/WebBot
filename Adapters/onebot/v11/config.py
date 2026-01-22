"""
OneBot V11配置

使用Pydantic进行配置验证
"""

from typing import Optional

from pydantic import BaseModel, Field


class OneBotConfig(BaseModel):
    """OneBot V11协议配置"""

    ws_host: str = Field(..., description="OneBot WebSocket地址")
    ws_port: int = Field(..., description="OneBot WebSocket端口")
    access_token: Optional[str] = Field(None, description="访问令牌（可选）")
    self_trigger: bool = Field(False, description="是否启用自触发（默认关闭）")

    class Config:
        extra = "allow"  # 允许额外字段
