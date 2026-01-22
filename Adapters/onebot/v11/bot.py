"""
OneBot Bot类
"""

from typing import Any, TYPE_CHECKING

from .event import OneBotMessageEvent
from .message import OneBotMessage
from ...base.bot import BaseBot

if TYPE_CHECKING:
    from .adapter import OneBotAdapter
    from ...base.event import BaseEvent


class OneBotBot(BaseBot):
    """OneBot机器人"""

    def __init__(self, adapter: "OneBotAdapter", self_id: str):
        super().__init__(adapter, self_id)
        self.bot_qq = int(self_id) if self_id.isdigit() else 0

    async def send(
            self,
            event: "BaseEvent",
            message: OneBotMessage,
            **kwargs: Any
    ) -> Any:
        """发送消息"""
        if not isinstance(event, OneBotMessageEvent):
            raise ValueError("OneBotBot can only handle OneBotMessageEvent")

        # 转换消息为OneBot格式
        onebot_array = message.to_onebot_array()

        # 构建API参数
        params = {
            "message": onebot_array,
            "message_type": event.message_type
        }

        if event.message_type == "group":
            params["group_id"] = event.group_id
        else:
            params["user_id"] = event.user_id

        # 调用API
        return await self.call_api("send_msg", **params)

    async def call_api(self, api: str, **data: Any) -> Any:
        """调用OneBot API"""
        return await self.adapter._call_api(self, api, **data)
