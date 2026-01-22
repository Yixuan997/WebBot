"""
QQ官方协议适配器

支持QQ官方Bot API（Webhook模式）
"""

from .adapter import QQAdapter
from .bot import QQBot
from .config import QQConfig
from .event import QQMessageEvent, QQEvent, QQNoticeEvent, QQMetaEvent
from .message import QQMessage, QQMessageSegment

__all__ = [
    "QQAdapter",
    "QQBot",
    "QQEvent",
    "QQMessageEvent",
    "QQNoticeEvent",
    "QQMetaEvent",
    "QQMessage",
    "QQMessageSegment",
    "QQConfig",
]
