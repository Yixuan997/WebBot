"""
OneBot 协议适配器模块
支持 OneBot V11 标准
"""

from .v11.adapter import OneBotAdapter


def setup(registry: dict):
    """协议注册入口"""
    registry[OneBotAdapter.get_protocol_id()] = OneBotAdapter


__all__ = ['setup', 'OneBotAdapter']
