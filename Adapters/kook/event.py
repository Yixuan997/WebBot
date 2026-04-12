"""
KOOK 事件类
"""

from dataclasses import dataclass, field
from typing import Optional, Literal

from .message import KookMessage, KookMessageSegment
from ..base.event import BaseEvent


@dataclass
class KookEvent(BaseEvent):
    """KOOK 事件基类"""

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

    def get_message(self) -> Optional[KookMessage]:
        raise ValueError("Event has no message")

    def get_plaintext(self) -> str:
        return ""

    def is_tome(self) -> bool:
        return False


@dataclass
class KookMessageEvent(KookEvent):
    """KOOK 消息事件"""

    post_type: str = "message"
    message_type: Literal["group", "private"] = "group"
    channel_type: str = "GROUP"
    user_id: str = ""
    channel_id: str = ""
    guild_id: Optional[str] = None
    message_id: str = ""
    message: KookMessage = field(default_factory=KookMessage)
    content: str = ""
    to_me: bool = False

    def get_event_name(self) -> str:
        return f"message.{self.message_type}"

    def get_user_id(self) -> str:
        return self.user_id

    def get_session_id(self) -> str:
        if self.message_type == "private":
            return f"private_{self.user_id}"
        return f"group_{self.channel_id}"

    def get_message(self) -> KookMessage:
        return self.message

    def get_plaintext(self) -> str:
        if self.content:
            return self.content
        return self.message.extract_plain_text()

    def is_tome(self) -> bool:
        return self.to_me

    def get_target(self) -> str:
        if self.message_type == "private":
            return f"user:{self.user_id}"
        return f"channel:{self.channel_id}"

    @classmethod
    def from_raw(cls, raw_data: dict) -> "KookMessageEvent":
        import time as time_module

        # KOOK Webhook 常见结构为 {"d": {...}}
        payload = raw_data.get("d", raw_data)
        channel_type = str(payload.get("channel_type", "GROUP")).upper()
        message_type = "private" if channel_type in ("PERSON", "DIRECT", "PRIVATE") else "group"

        user_id = str(payload.get("author_id") or payload.get("user_id") or "")
        channel_id = str(payload.get("target_id") or payload.get("channel_id") or "")
        guild_id = payload.get("guild_id")
        msg_id = str(payload.get("msg_id") or payload.get("id") or "")
        content = str(payload.get("content") or "")

        # 粗略判断是否提及机器人（私聊默认 true）
        to_me = message_type == "private" or "(met)" in content

        message = KookMessage(KookMessageSegment.text(content))

        return cls(
            time=int(payload.get("msg_timestamp") or payload.get("timestamp") or time_module.time()),
            self_id=str(raw_data.get("bot_id", "")),
            message_type=message_type,
            channel_type=channel_type,
            user_id=user_id,
            channel_id=channel_id,
            guild_id=guild_id,
            message_id=msg_id,
            message=message,
            content=content,
            to_me=to_me,
            raw_data=raw_data,
        )


@dataclass
class KookNoticeEvent(KookEvent):
    post_type: str = "notice"

    def get_event_name(self) -> str:
        return "notice"


@dataclass
class KookRequestEvent(KookEvent):
    post_type: str = "request"

    def get_event_name(self) -> str:
        return "request"

