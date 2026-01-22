"""
OneBot V11协议适配器

兼容go-cqhttp、OpenShamrock等OneBot V11实现
"""

from .adapter import OneBotAdapter
from .bot import OneBotBot
from .config import OneBotConfig
from .event import OneBotEvent, OneBotMessageEvent
from .message import OneBotMessage, OneBotMessageSegment

__all__ = [
    "OneBotAdapter",
    "OneBotBot",
    "OneBotEvent",
    "OneBotMessageEvent",
    "OneBotMessage",
    "OneBotMessageSegment",
    "OneBotConfig",
]
