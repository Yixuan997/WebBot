"""
适配器基础抽象层

提供所有适配器必须实现的基类和接口
"""

from .adapter import BaseAdapter
from .bot import BaseBot
from .event import BaseEvent
from .message import BaseMessage, BaseMessageSegment

__all__ = [
    "BaseAdapter",
    "BaseBot",
    "BaseEvent",
    "BaseMessage",
    "BaseMessageSegment",
]
