"""
QQ协议消息类

基于QQ官方API的消息格式
"""

import json
from typing import Union

from ..base.message import BaseMessage, BaseMessageSegment


class QQMessageSegment(BaseMessageSegment):
    """QQ消息段"""

    @classmethod
    def get_message_class(cls):
        return QQMessage

    def __str__(self) -> str:
        """返回可读的字符串表示"""
        if self.type == "text":
            return self.data.get("text", "")
        elif self.type == "image":
            return "[图片]"
        elif self.type == "video":
            return "[视频]"
        elif self.type == "voice":
            return "[语音]"
        elif self.type == "file":
            return "[文件]"
        elif self.type == "markdown":
            return "[Markdown]"
        elif self.type == "ark":
            return "[Ark卡片]"
        else:
            return f"[{self.type}]"

    @classmethod
    def text(cls, text: str) -> "QQMessageSegment":
        """构造文本消息段"""
        return cls("text", {"text": text})

    @classmethod
    def image(cls, url: str = "", caption: str = "", base64_data: str = None) -> "QQMessageSegment":
        """构造图片消息段
        
        Args:
            url: 图片URL
            caption: 图片说明
            base64_data: base64编码的图片数据
        """
        return cls("image", {"url": url, "caption": caption, "base64_data": base64_data})

    @classmethod
    def video(cls, url: str, caption: str = "") -> "QQMessageSegment":
        """构造视频消息段"""
        return cls("video", {"url": url, "caption": caption})

    @classmethod
    def voice(cls, url: str) -> "QQMessageSegment":
        """构造语音消息段"""
        return cls("voice", {"url": url})

    @classmethod
    def file(cls, url: str, filename: str = "") -> "QQMessageSegment":
        """构造文件消息段"""
        return cls("file", {"url": url, "filename": filename})

    @classmethod
    def markdown(cls, content: str) -> "QQMessageSegment":
        """构造原生Markdown消息段（仅频道支持）"""
        return cls("markdown", {"content": content})

    @classmethod
    def markdown_template(cls, template_id: str, content: str, keyboard_id: str = "") -> "QQMessageSegment":
        """
        构造模板Markdown消息段（群/私聊支持）
        
        Args:
            template_id: 在QQ开放平台申请的模板ID
            content: Markdown内容，JSON格式的参数
            keyboard_id: 按钮模板ID（可选，不为空则发送按钮）
        """
        return cls("markdown_template", {
            "template_id": template_id,
            "content": content,
            "keyboard_id": keyboard_id
        })

    @classmethod
    def keyboard(cls, content: str, keyboard_id: str) -> "QQMessageSegment":
        """
        构造按钮卡片消息段（文本 + 按钮）
        
        Args:
            content: 按钮上方的文本内容
            keyboard_id: 在QQ开放平台申请的按钮模板ID
        """
        return cls("keyboard", {"content": content, "keyboard_id": keyboard_id})

    @classmethod
    def ark(cls, template_id: int, kv: list) -> "QQMessageSegment":
        """构造Ark卡片消息段"""
        return cls("ark", {"template_id": template_id, "kv": kv})

    @classmethod
    def large_image(cls, title: str, subtitle: str, image_url: str,
                    prompt: str = "愿为西南风,长逝入君怀") -> "QQMessageSegment":
        """构造大图消息（Ark模板37）"""
        return cls("ark", {
            "template_id": 37,
            "kv": [
                {"key": "#METATITLE#", "value": title},
                {"key": "#METASUBTITLE#", "value": subtitle},
                {"key": "#PROMPT#", "value": prompt},
                {"key": "#METACOVER#", "value": image_url}
            ]
        })

    # 媒体类型映射：type -> (file_type, content_key)
    _MEDIA_TYPE_MAP = {
        "image": (1, "caption"),  # 1=图片
        "video": (2, "caption"),  # 2=视频
        "voice": (3, None),  # 3=语音，无描述
        "file": (4, "filename"),  # 4=文件
    }

    def to_qq_dict(self) -> dict:
        """
        转换为QQ API格式
        
        Returns:
            QQ API需要的消息格式
        """
        if self.type == "text":
            return {
                "msg_type": 0,
                "content": self.data["text"]
            }

        # 处理媒体类型（图片/视频/语音/文件）
        if self.type in self._MEDIA_TYPE_MAP:
            file_type, content_key = self._MEDIA_TYPE_MAP[self.type]
            base64_data = self.data.get("base64_data")
            result = {
                "msg_type": 7,
                "content": self.data.get(content_key, "") if content_key else "",
                "media": {"file_info": self.data.get("url", "")},
                "_needs_upload": True,
                "_file_type": file_type
            }
            # 如果有 base64 数据，添加到结果中
            if base64_data:
                result["_base64_data"] = base64_data
            return result

        if self.type == "markdown":
            # 原生Markdown（仅频道）
            return {
                "msg_type": 2,
                "markdown": {"content": self.data["content"]}
            }
        elif self.type == "markdown_template":
            # 模板Markdown（群/私聊）
            # content 支持两种格式：
            # 1. JSON格式: {"size": "100x100", "title": "标题"}
            # 2. 纯文本: 作为 text 参数传递
            content = self.data["content"]
            template_id = self.data["template_id"]
            keyboard_id = self.data.get("keyboard_id", "")

            params = []

            # QQ MD模板参数不支持 \n，需用 \r 代替
            # JSON 解析时 \r 是无效字符，先转义后解析，再还原
            escaped = content.replace('\r', '\\r')
            try:
                data = json.loads(escaped)
                if isinstance(data, dict):
                    for key, value in data.items():
                        # 还原 \r，同时把 \n 也转成 \r
                        val = str(value).replace('\\r', '\r').replace('\n', '\r')
                        params.append({"key": key, "values": [val]})
                else:
                    params = [{"key": "text", "values": [content.replace('\n', '\r')]}]
            except (json.JSONDecodeError, TypeError):
                params = [{"key": "text", "values": [content.replace('\n', '\r')]}]

            result = {
                "msg_type": 2,
                "markdown": {
                    "custom_template_id": template_id,
                    "params": params
                }
            }

            # 如果有按钮ID，添加keyboard字段
            if keyboard_id:
                result["keyboard"] = {"id": keyboard_id}

            return result
        elif self.type == "keyboard":
            # 文本 + 按钮卡片
            return {
                "msg_type": 0,
                "content": self.data["content"],
                "keyboard": {"id": self.data["keyboard_id"]}
            }
        elif self.type == "ark":
            return {
                "msg_type": 3,
                "ark": {
                    "template_id": self.data["template_id"],
                    "kv": self.data["kv"]
                }
            }
        else:
            # 未知类型，返回基本格式
            return {"msg_type": 0, "content": str(self)}


class QQMessage(BaseMessage[QQMessageSegment]):
    """QQ消息（继承自list）"""

    @classmethod
    def get_segment_class(cls):
        return QQMessageSegment

    def __add__(self, other: Union[str, QQMessageSegment, "QQMessage"]) -> "QQMessage":
        """支持加法"""
        result = self.__class__(*self)
        if isinstance(other, str):
            result.append(QQMessageSegment.text(other))
        elif isinstance(other, QQMessageSegment):
            result.append(other)
        elif isinstance(other, QQMessage):
            result.extend(other)
        return result

    def to_api_format(self) -> dict:
        """
        转换为QQ API格式
        
        QQ API通常只支持单个消息段，如果有多个，取第一个
        
        Returns:
            QQ API格式的消息字典
        """
        if not self:
            return {"msg_type": 0, "content": ""}

        # 如果只有一个segment，直接转换
        if len(self) == 1:
            return self[0].to_qq_dict()

        # 如果有多个segment，尝试合并文本
        text_parts = []
        for seg in self:
            if seg.type == "text":
                text_parts.append(seg.data["text"])
            else:
                # 遇到非文本segment，返回该segment（QQ不支持混合）
                return seg.to_qq_dict()

        # 返回合并的文本
        return {
            "msg_type": 0,
            "content": "".join(text_parts)
        }

    def to_qq_dict(self) -> dict:
        """to_api_format的别名，为了兼容性"""
        return self.to_api_format()
