"""
消息基类

定义协议无关的消息接口
参考NoneBot2的设计，Message继承自list
"""

import inspect
from abc import ABC, abstractmethod
from collections.abc import Iterable as ABCIterable
from functools import lru_cache
from typing import Dict, Any, Union, TypeVar, Generic, Type

TMS = TypeVar("TMS", bound="BaseMessageSegment")


@lru_cache(maxsize=32)
def _method_has_param(method, param_name: str) -> bool:
    """缓存方法签名检查结果"""
    try:
        sig = inspect.signature(method)
        return param_name in sig.parameters
    except (ValueError, TypeError):
        return False


class BaseMessageSegment(ABC):
    """
    消息段基类
    
    表示消息的一个组成部分（文本、图片、表情等）
    """

    def __init__(self, type: str, data: Dict[str, Any]):
        """
        初始化消息段
        
        Args:
            type: 消息段类型（text, image, at等）
            data: 消息段数据
        """
        self.type = type
        self.data = data

    @abstractmethod
    def __str__(self) -> str:
        """
        返回消息段的字符串表示
        
        不同协议有不同的表示方式：
        - OneBot: CQ码格式 [CQ:image,file=xxx]
        - QQ: 简单描述 [图片]
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(type={self.type!r}, data={self.data!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseMessageSegment):
            return False
        return self.type == other.type and self.data == other.data

    @classmethod
    @abstractmethod
    def get_message_class(cls) -> Type["BaseMessage"]:
        """返回对应的Message类"""
        raise NotImplementedError

    def is_text(self) -> bool:
        """判断是否为文本消息段"""
        return self.type == "text"


class BaseMessage(list, Generic[TMS], ABC):
    """
    消息基类
    
    继承自list，可以当作MessageSegment的列表使用
    提供链式构造、序列化等功能
    """

    def __init__(self, *segments: Union[TMS, str, ABCIterable[TMS]]):
        """
        初始化消息
        
        Args:
            *segments: 消息段或字符串
        """
        super().__init__()
        for seg in segments:
            if isinstance(seg, str):
                # 字符串自动转换为text segment
                self.append(self.get_segment_class().text(seg))
            elif isinstance(seg, BaseMessageSegment):
                self.append(seg)
            elif isinstance(seg, ABCIterable):
                self.extend(seg)

    @classmethod
    @abstractmethod
    def get_segment_class(cls) -> Type[TMS]:
        """返回对应的MessageSegment类"""
        raise NotImplementedError

    def __str__(self) -> str:
        """返回消息的字符串表示"""
        return "".join(str(seg) for seg in self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __add__(self, other: Union[str, TMS, "BaseMessage"]) -> "BaseMessage":
        """支持加法操作"""
        result = self.__class__(*self)
        if isinstance(other, str):
            result.append(self.get_segment_class().text(other))
        elif isinstance(other, BaseMessageSegment):
            result.append(other)
        elif isinstance(other, BaseMessage):
            result.extend(other)
        return result

    def __radd__(self, other: Union[str, TMS]) -> "BaseMessage":
        """支持反向加法"""
        result = self.__class__()
        if isinstance(other, str):
            result.append(self.get_segment_class().text(other))
        elif isinstance(other, BaseMessageSegment):
            result.append(other)
        result.extend(self)
        return result

    def extract_plain_text(self) -> str:
        """
        提取纯文本内容
        
        Returns:
            所有文本消息段的内容拼接
        """
        return "".join(
            seg.data.get("text", "")
            for seg in self
            if seg.is_text()
        )

    # 便捷的类方法（子类可以重写）
    @classmethod
    def text(cls, text: str) -> "BaseMessage":
        """
        构造纯文本消息
        
        Args:
            text: 文本内容
            
        Returns:
            包含单个text segment的Message
        """
        seg_class = cls.get_segment_class()
        return cls(seg_class.text(text))

    @classmethod
    def image(cls, url: str) -> "BaseMessage":
        """
        构造图片消息
        
        Args:
            url: 图片URL
            
        Returns:
            包含单个image segment的Message
        """
        seg_class = cls.get_segment_class()
        return cls(seg_class.image(url))

    @classmethod
    def video(cls, url: str, caption: str = "") -> "BaseMessage":
        """
        构造视频消息
        
        Args:
            url: 视频URL
            caption: 视频说明
            
        Returns:
            包含单个video segment的Message
        """
        seg_class = cls.get_segment_class()
        if not hasattr(seg_class, 'video'):
            return cls(seg_class.text(f"[视频] {url}"))
        # 检查video方法是否支持caption参数（缓存结果）
        if _method_has_param(seg_class.video, 'caption'):
            return cls(seg_class.video(url, caption))
        else:
            return cls(seg_class.video(url))

    @classmethod
    def voice(cls, url: str) -> "BaseMessage":
        """
        构造语音消息
        
        Args:
            url: 语音URL
            
        Returns:
            包含单个voice segment的Message
        """
        seg_class = cls.get_segment_class()
        return cls(seg_class.voice(url) if hasattr(seg_class, 'voice') else seg_class.text(f"[语音] {url}"))

    @classmethod
    def file(cls, url: str, filename: str = "") -> "BaseMessage":
        """
        构造文件消息
        
        Args:
            url: 文件URL
            filename: 文件名
            
        Returns:
            包含单个file segment的Message
        """
        seg_class = cls.get_segment_class()
        return cls(seg_class.file(url, filename) if hasattr(seg_class, 'file') else seg_class.text(
            f"[文件] {filename or url}"))
