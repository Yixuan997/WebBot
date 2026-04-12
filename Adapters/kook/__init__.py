"""
KOOK 协议适配器

支持 KOOK 机器人 Webhook 收消息 + HTTP API 发消息。
"""

from .adapter import KookAdapter
from .bot import KookBot
from .config import KookConfig
from .event import KookEvent, KookMessageEvent, KookNoticeEvent, KookRequestEvent
from .message import KookMessage, KookMessageSegment


def setup(registry: dict):
    """协议注册入口"""
    registry[KookAdapter.get_protocol_id()] = KookAdapter


__all__ = [
    "setup",
    "KookAdapter",
    "KookBot",
    "KookConfig",
    "KookEvent",
    "KookMessageEvent",
    "KookNoticeEvent",
    "KookRequestEvent",
    "KookMessage",
    "KookMessageSegment",
]
