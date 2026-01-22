"""
OneBot V11事件类
"""

from dataclasses import dataclass, field
from typing import Optional, Literal

from .message import OneBotMessage, OneBotMessageSegment
from ...base.event import BaseEvent


@dataclass
class OneBotEvent(BaseEvent):
    """OneBot事件基类"""

    time: int = 0
    self_id: int = 0
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

    def get_message(self) -> Optional[OneBotMessage]:
        raise ValueError("Event has no message")

    def get_plaintext(self) -> str:
        return ""

    def is_tome(self) -> bool:
        return False


@dataclass
class OneBotMessageEvent(OneBotEvent):
    """OneBot消息事件"""

    post_type: str = "message"
    message_type: Literal["private", "group"] = "private"
    user_id: int = 0
    group_id: Optional[int] = None
    message_id: int = 0
    message: OneBotMessage = field(default_factory=OneBotMessage)
    raw_message: str = ""
    to_me: bool = False

    def get_event_name(self) -> str:
        return f"message.{self.message_type}"

    def get_user_id(self) -> str:
        return str(self.user_id)

    def get_session_id(self) -> str:
        if self.group_id:
            return f"group_{self.group_id}"
        return f"private_{self.user_id}"

    def get_message(self) -> OneBotMessage:
        return self.message

    def get_plaintext(self) -> str:
        if self.raw_message:
            return self.raw_message
        return self.message.extract_plain_text()

    def is_tome(self) -> bool:
        return self.to_me

    @classmethod
    def from_raw(cls, raw_data: dict) -> "OneBotMessageEvent":
        """从原始数据构造事件"""
        import time as time_module

        message_type = raw_data.get("message_type", "private")
        user_id = raw_data.get("user_id", 0)
        group_id = raw_data.get("group_id")

        # 构造消息对象
        raw_message = raw_data.get("raw_message", "")
        message_data = raw_data.get("message", [])

        message = OneBotMessage()
        if isinstance(message_data, str):
            # CQ码格式
            message.extend(OneBotMessage._construct(message_data))
        elif isinstance(message_data, list):
            # 消息段数组
            for seg in message_data:
                message.append(OneBotMessageSegment(seg["type"], seg.get("data", {})))

        # 检查是否 @ 了机器人
        to_me = False
        if message_type == "private":
            # 私聊默认 to_me
            to_me = True
        else:
            # 群聊检查是否有 @ 机器人的消息段
            self_id = raw_data.get("self_id", 0)
            for seg in message:
                if seg.type == "at":
                    qq_value = seg.data.get("qq")
                    # 统一转换为字符串比较
                    if str(qq_value) == str(self_id):
                        to_me = True
                        break

        return cls(
            time=raw_data.get("time", int(time_module.time())),
            self_id=raw_data.get("self_id", 0),
            message_type=message_type,
            user_id=user_id,
            group_id=group_id,
            message_id=raw_data.get("message_id", 0),
            message=message,
            raw_message=raw_message,
            to_me=to_me,
            raw_data=raw_data
        )


@dataclass
class OneBotNoticeEvent(OneBotEvent):
    """通知事件"""

    post_type: str = "notice"
    notice_type: str = ""
    sub_type: str = ""
    user_id: int = 0
    group_id: Optional[int] = None

    def get_event_name(self) -> str:
        if self.sub_type:
            return f"notice.{self.notice_type}.{self.sub_type}"
        return f"notice.{self.notice_type}"

    def get_user_id(self) -> str:
        return str(self.user_id)

    @classmethod
    def from_raw(cls, raw_data: dict) -> "OneBotNoticeEvent":
        import time as time_module
        return cls(
            time=raw_data.get("time", int(time_module.time())),
            self_id=raw_data.get("self_id", 0),
            notice_type=raw_data.get("notice_type", ""),
            sub_type=raw_data.get("sub_type", ""),
            user_id=raw_data.get("user_id", 0),
            group_id=raw_data.get("group_id"),
            raw_data=raw_data
        )


@dataclass
class OneBotRequestEvent(OneBotEvent):
    """请求事件"""

    post_type: str = "request"
    request_type: str = ""
    sub_type: str = ""
    user_id: int = 0
    group_id: Optional[int] = None
    comment: str = ""
    flag: str = ""

    def get_event_name(self) -> str:
        if self.sub_type:
            return f"request.{self.request_type}.{self.sub_type}"
        return f"request.{self.request_type}"

    def get_user_id(self) -> str:
        return str(self.user_id)

    @classmethod
    def from_raw(cls, raw_data: dict) -> "OneBotRequestEvent":
        import time as time_module
        return cls(
            time=raw_data.get("time", int(time_module.time())),
            self_id=raw_data.get("self_id", 0),
            request_type=raw_data.get("request_type", ""),
            sub_type=raw_data.get("sub_type", ""),
            user_id=raw_data.get("user_id", 0),
            group_id=raw_data.get("group_id"),
            comment=raw_data.get("comment", ""),
            flag=raw_data.get("flag", ""),
            raw_data=raw_data
        )


@dataclass
class OneBotMetaEvent(OneBotEvent):
    """元事件（心跳、生命周期等）"""

    post_type: str = "meta_event"
    meta_event_type: str = ""
    sub_type: str = ""

    def get_event_name(self) -> str:
        if self.sub_type:
            return f"meta_event.{self.meta_event_type}.{self.sub_type}"
        return f"meta_event.{self.meta_event_type}"

    @classmethod
    def from_raw(cls, raw_data: dict) -> "OneBotMetaEvent":
        import time as time_module
        return cls(
            time=raw_data.get("time", int(time_module.time())),
            self_id=raw_data.get("self_id", 0),
            meta_event_type=raw_data.get("meta_event_type", ""),
            sub_type=raw_data.get("sub_type", ""),
            raw_data=raw_data
        )
