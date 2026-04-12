"""
KOOK 消息类
"""

from typing import Union

from ..base.message import BaseMessage, BaseMessageSegment


class KookMessageSegment(BaseMessageSegment):
    """KOOK 消息段"""

    @classmethod
    def get_message_class(cls):
        return KookMessage

    def __str__(self) -> str:
        if self.type == "text":
            return self.data.get("text", "")
        if self.type == "image":
            return "[图片]"
        if self.type == "video":
            return "[视频]"
        if self.type == "voice":
            return "[语音]"
        if self.type == "file":
            return "[文件]"
        return f"[{self.type}]"

    @classmethod
    def text(cls, text: str) -> "KookMessageSegment":
        return cls("text", {"text": text})

    @classmethod
    def image(cls, url: str) -> "KookMessageSegment":
        return cls("image", {"url": url})

    @classmethod
    def video(cls, url: str) -> "KookMessageSegment":
        return cls("video", {"url": url})

    @classmethod
    def voice(cls, url: str) -> "KookMessageSegment":
        return cls("voice", {"url": url})

    @classmethod
    def file(cls, url: str, filename: str = "") -> "KookMessageSegment":
        return cls("file", {"url": url, "filename": filename})


class KookMessage(BaseMessage[KookMessageSegment]):
    """KOOK 消息"""

    @classmethod
    def get_segment_class(cls):
        return KookMessageSegment

    def __add__(self, other: Union[str, KookMessageSegment, "KookMessage"]) -> "KookMessage":
        result = self.__class__(*self)
        if isinstance(other, str):
            result.append(KookMessageSegment.text(other))
        elif isinstance(other, KookMessageSegment):
            result.append(other)
        elif isinstance(other, KookMessage):
            result.extend(other)
        return result

    def to_kook_payload(self) -> dict:
        """
        转为 KOOK API 消息体中的 type/content 字段
        """
        if not self:
            return {"type": 1, "content": ""}

        # 优先纯文本合并
        if all(seg.type == "text" for seg in self):
            return {"type": 1, "content": "".join(seg.data.get("text", "") for seg in self)}

        seg = self[0]
        if seg.type == "text":
            return {"type": 1, "content": seg.data.get("text", "")}
        if seg.type == "image":
            url = seg.data.get("url", "")
            if url.startswith("base64://"):
                # KOOK 不支持直接 base64 消息体，此处回退文本提示
                return {"type": 1, "content": "[图片发送失败] KOOK 不支持直接 base64，请先上传资源"}
            return {"type": 2, "content": url}
        if seg.type == "video":
            return {"type": 3, "content": seg.data.get("url", "")}
        if seg.type == "file":
            return {"type": 4, "content": seg.data.get("url", "")}
        if seg.type == "voice":
            return {"type": 8, "content": seg.data.get("url", "")}

        return {"type": 1, "content": str(self)}

