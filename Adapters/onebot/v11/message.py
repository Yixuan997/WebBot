"""
OneBot V11消息类

基于OneBot V11标准的消息格式
支持CQ码和消息段数组
"""

import re
from typing import Union

from ...base.message import BaseMessage, BaseMessageSegment


def escape(s: str, *, escape_comma: bool = True) -> str:
    """转义特殊字符"""
    s = s.replace("&", "&amp;").replace("[", "&#91;").replace("]", "&#93;")
    if escape_comma:
        s = s.replace(",", "&#44;")
    return s


def unescape(s: str) -> str:
    """反转义特殊字符"""
    return (
        s.replace("&#44;", ",")
        .replace("&#91;", "[")
        .replace("&#93;", "]")
        .replace("&amp;", "&")
    )


class OneBotMessageSegment(BaseMessageSegment):
    """OneBot消息段"""

    @classmethod
    def get_message_class(cls):
        return OneBotMessage

    def __str__(self) -> str:
        """返回CQ码格式"""
        if self.type == "text":
            return escape(self.data.get("text", ""), escape_comma=False)

        params = ",".join(
            f"{k}={escape(str(v))}"
            for k, v in self.data.items()
            if v is not None
        )
        return f"[CQ:{self.type}{',' if params else ''}{params}]"

    @classmethod
    def text(cls, text: str) -> "OneBotMessageSegment":
        """构造文本消息段"""
        return cls("text", {"text": text})

    @classmethod
    def image(cls, file: str) -> "OneBotMessageSegment":
        """构造图片消息段"""
        return cls("image", {"file": file})

    @classmethod
    def at(cls, user_id: Union[int, str]) -> "OneBotMessageSegment":
        """构造@消息段"""
        return cls("at", {"qq": str(user_id)})

    @classmethod
    def face(cls, id_: int) -> "OneBotMessageSegment":
        """构造表情消息段"""
        return cls("face", {"id": str(id_)})

    @classmethod
    def reply(cls, id_: int) -> "OneBotMessageSegment":
        """构造回复消息段"""
        return cls("reply", {"id": str(id_)})

    @classmethod
    def record(cls, file: str) -> "OneBotMessageSegment":
        """构造语音消息段"""
        return cls("record", {"file": file})

    @classmethod
    def video(cls, file: str) -> "OneBotMessageSegment":
        """构造视频消息段"""
        return cls("video", {"file": file})

    def to_dict(self) -> dict:
        """转换为OneBot消息段格式"""
        return {"type": self.type, "data": self.data}


class OneBotMessage(BaseMessage[OneBotMessageSegment]):
    """OneBot消息（继承自list）"""

    @classmethod
    def get_segment_class(cls):
        return OneBotMessageSegment

    def __add__(self, other: Union[str, OneBotMessageSegment, "OneBotMessage"]) -> "OneBotMessage":
        """支持加法"""
        result = self.__class__(*self)
        if isinstance(other, str):
            result.append(OneBotMessageSegment.text(other))
        elif isinstance(other, OneBotMessageSegment):
            result.append(other)
        elif isinstance(other, OneBotMessage):
            result.extend(other)
        return result

    @staticmethod
    def _construct(msg: str) -> list:
        """
        从CQ码字符串构造消息段列表
        
        Args:
            msg: CQ码格式的字符串
            
        Returns:
            消息段列表
        """

        def _iter_message(msg: str):
            text_begin = 0
            for cqcode in re.finditer(
                    r"\[CQ:(?P<type>[a-zA-Z0-9-_.]+)"
                    r"(?P<params>"
                    r"(?:,[a-zA-Z0-9-_.]+=[^,\]]*)*"
                    r"),?\]",
                    msg,
            ):
                yield "text", msg[text_begin: cqcode.pos + cqcode.start()]
                text_begin = cqcode.pos + cqcode.end()
                yield cqcode.group("type"), cqcode.group("params").lstrip(",")
            yield "text", msg[text_begin:]

        segments = []
        for type_, data in _iter_message(msg):
            if type_ == "text":
                if data:
                    segments.append(OneBotMessageSegment(type_, {"text": unescape(data)}))
            else:
                data_dict = {}
                if data:
                    for item in data.split(","):
                        if "=" in item:
                            k, v = item.split("=", 1)
                            data_dict[k.strip()] = unescape(v)
                segments.append(OneBotMessageSegment(type_, data_dict))

        return segments

    def to_onebot_array(self) -> list:
        """
        转换为OneBot消息段数组格式
        
        Returns:
            消息段数组，格式为 [{"type": "text", "data": {...}}, ...]
        """
        return [seg.to_dict() for seg in self]
