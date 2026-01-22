"""
QQ协议事件类

基于QQ官方Webhook事件格式
"""

from dataclasses import dataclass, field
from typing import Optional, Literal

from .message import QQMessage, QQMessageSegment
from ..base.event import BaseEvent


@dataclass
class QQEvent(BaseEvent):
    """QQ事件基类"""

    time: int = 0
    self_id: str = ""
    post_type: str = ""
    raw_data: dict = field(default_factory=dict)

    def get_type(self) -> str:
        return self.post_type

    def get_event_name(self) -> str:
        return self.post_type

    def get_user_id(self) -> str:
        raise ValueError("Event has no user context")

    def get_session_id(self) -> str:
        raise ValueError("Event has no session context")

    def get_message(self) -> Optional[QQMessage]:
        raise ValueError("Event has no message")

    def get_plaintext(self) -> str:
        return ""

    def is_tome(self) -> bool:
        return False


@dataclass
class QQMessageEvent(QQEvent):
    """QQ消息事件"""

    post_type: str = "message"
    message_type: Literal["private", "group", "channel", "direct"] = "private"
    user_id: str = ""
    group_id: Optional[str] = None
    channel_id: Optional[str] = None
    guild_id: Optional[str] = None
    message_id: str = ""
    message: QQMessage = field(default_factory=QQMessage)
    content: str = ""
    to_me: bool = False

    def get_event_name(self) -> str:
        return f"message.{self.message_type}"

    def get_user_id(self) -> str:
        return self.user_id

    def get_session_id(self) -> str:
        """
        获取会话ID
        
        Returns:
            group_xxx 或 channel_xxx 或 private_xxx
        """
        if self.group_id:
            return f"group_{self.group_id}"
        elif self.channel_id:
            return f"channel_{self.channel_id}"
        else:
            return f"private_{self.user_id}"

    def get_message(self) -> QQMessage:
        return self.message

    def get_plaintext(self) -> str:
        if self.content:
            return self.content
        return self.message.extract_plain_text()

    def is_tome(self) -> bool:
        return self.to_me

    @classmethod
    def from_raw(cls, raw_data: dict) -> "QQMessageEvent":
        """
        从原始数据构造事件对象
        
        Args:
            raw_data: QQ Webhook推送的原始数据
            
        Returns:
            QQMessageEvent对象
        """
        import time as time_module

        # 解析消息类型
        msg_type = raw_data.get("type", "")
        if msg_type == "group_at":
            message_type = "group"
        elif msg_type == "c2c":
            message_type = "private"
        elif msg_type in ["at_message", "channel"]:
            message_type = "channel"
        elif msg_type == "direct_message":
            message_type = "direct"
        else:
            message_type = "private"

        # 判断是否@机器人
        to_me = msg_type in ["group_at", "at_message", "c2c", "direct_message"]

        # 提取用户ID
        author = raw_data.get("author", {})
        user_id = (
                author.get("user_openid") or
                author.get("id") or
                raw_data.get("openid", "")
        )

        # 提取群组/频道ID
        group_id = raw_data.get("group_openid")
        channel_id = raw_data.get("channel_id")
        guild_id = raw_data.get("guild_id")

        # 构造消息对象
        content = raw_data.get("content", "").strip()
        message = QQMessage(QQMessageSegment.text(content))

        return cls(
            time=int(time_module.time()),
            self_id=raw_data.get("bot_id", ""),
            message_type=message_type,
            user_id=user_id,
            group_id=group_id,
            channel_id=channel_id,
            guild_id=guild_id,
            message_id=raw_data.get("id", ""),
            message=message,
            content=content,
            to_me=to_me,
            raw_data=raw_data
        )

    def get_target(self) -> str:
        """
        获取发送目标字符串
        
        Returns:
            目标字符串，格式为 "type:id"
        """
        if self.group_id:
            return f"group:{self.group_id}"
        elif self.channel_id:
            return f"channel:{self.channel_id}"
        elif self.guild_id:
            return f"dm:{self.guild_id}"
        else:
            return f"user:{self.user_id}"


@dataclass
class QQNoticeEvent(QQEvent):
    """QQ通知事件（待扩展）"""

    post_type: str = "notice"

    def get_event_name(self) -> str:
        return "notice"


@dataclass
class QQMetaEvent(QQEvent):
    """QQ元事件（待扩展）"""

    post_type: str = "meta"

    def get_event_name(self) -> str:
        return "meta"
