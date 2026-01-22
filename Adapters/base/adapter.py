"""
Adapter基类

适配器是协议的核心，负责接收事件和调用API
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable

from .bot import BaseBot
from .event import BaseEvent


class BaseAdapter(ABC):
    """
    适配器基类
    
    职责：
    1. 接收原始数据并转换为Event对象
    2. 管理Bot实例（创建、注册、断开）
    3. 提供调用平台API的接口
    4. 维护连接状态（WebSocket/HTTP）
    """

    def __init__(self, bot_id: int, config: Dict[str, Any]):
        """
        初始化适配器
        
        Args:
            bot_id: 机器人在本系统中的ID（数据库ID）
            config: 配置字典（包含协议特定的配置）
        """
        self.bot_id = bot_id
        self.config = config
        self.bot: Optional[BaseBot] = None
        self.running = False
        self.message_handler: Optional[Callable] = None

    @abstractmethod
    def start(self) -> bool:
        """
        启动适配器
        
        建立连接（WebSocket/启动HTTP服务器）
        创建Bot实例
        
        Returns:
            True表示启动成功
        """
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> bool:
        """
        停止适配器
        
        关闭连接，清理资源
        
        Returns:
            True表示停止成功
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def json_to_event(cls, json_data: Dict[str, Any]) -> Optional[BaseEvent]:
        """
        将原始JSON数据转换为Event对象
        
        这是适配器的核心功能之一：接收事件
        
        Args:
            json_data: 平台推送的原始JSON数据
            
        Returns:
            Event对象，如果解析失败返回None
        """
        raise NotImplementedError

    @abstractmethod
    async def _call_api(self, bot: BaseBot, api: str, **data: Any) -> Any:
        """
        调用平台API
        
        这是适配器的核心功能之一：调用接口
        
        Args:
            bot: Bot实例
            api: API名称
            **data: API参数
            
        Returns:
            API返回结果
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def get_name(cls) -> str:
        """
        获取适配器名称
        
        Returns:
            适配器名称，如 "OneBot V11", "QQ Official"
        """
        raise NotImplementedError

    def set_message_handler(self, handler: Callable):
        """
        设置消息处理器
        
        适配器收到事件后会调用此handler
        
        Args:
            handler: 消息处理函数，签名为 async def(event: BaseEvent)
        """
        self.message_handler = handler

    def handle_raw_event(self, raw_data: Dict[str, Any]):
        """
        处理原始事件数据
        
        内部流程：
        1. 解析为Event对象
        2. 注入Bot实例
        3. 调用Bot.handle_event()
        
        Args:
            raw_data: 原始事件数据
        """
        try:
            # 解析事件
            event = self.json_to_event(raw_data)
            if not event:
                return

            # 注入bot
            event.bot = self.bot

            # 处理事件（在新线程中运行异步函数）
            if self.bot:
                import asyncio
                import threading

                def run_handler():
                    asyncio.run(self.bot.handle_event(event))

                threading.Thread(target=run_handler, daemon=True).start()

        except Exception as e:
            from Core.logging.file_logger import log_error
            log_error(self.bot_id, f"处理事件失败: {e}", "ADAPTER_EVENT_ERROR", error=str(e))

    @classmethod
    def get_cache_key_field(cls) -> Optional[str]:
        """
        返回配置中用作缓存键的字段名
        
        用于Webhook路由查找（QQ协议需要，OneBot不需要）
        
        Returns:
            字段名，如 "app_id"，不需要则返回None
        """
        return None

    @abstractmethod
    def get_protocol_name(self) -> str:
        """
        获取协议名称（用于日志）
        
        Returns:
            协议名称，如 "qq", "onebot"
        """
        raise NotImplementedError

    def get_status(self) -> Dict[str, Any]:
        """
        获取适配器状态
        
        Returns:
            状态字典
        """
        return {
            "protocol": self.get_protocol_name(),
            "running": self.running,
            "bot_id": self.bot_id,
            "self_id": self.bot.self_id if self.bot else None
        }
