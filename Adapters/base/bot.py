"""
Bot基类

Bot实例代表一个机器人账号
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .adapter import BaseAdapter
    from .event import BaseEvent
    from .message import BaseMessage


class BaseBot(ABC):
    """
    Bot基类
    
    职责：
    1. 存储机器人身份信息（self_id等）
    2. 提供发送消息的便捷方法
    3. 提供调用平台API的方法
    """

    def __init__(self, adapter: "BaseAdapter", self_id: str):
        """
        初始化Bot
        
        Args:
            adapter: 所属的适配器实例
            self_id: 机器人唯一标识（QQ号、app_id、bot_token等）
        """
        self.adapter = adapter
        self.self_id = self_id

    @abstractmethod
    async def send(
            self,
            event: "BaseEvent",
            message: "BaseMessage",
            **kwargs: Any
    ) -> Any:
        """
        发送消息
        
        根据event自动判断目标，发送message
        
        Args:
            event: 事件对象（用于获取上下文信息）
            message: 要发送的消息
            **kwargs: 协议特定的额外参数
            
        Returns:
            发送结果（协议相关）
            
        Raises:
            NetworkError: 网络错误
            ApiNotAvailable: API不可用
        """
        raise NotImplementedError

    @abstractmethod
    async def call_api(self, api: str, **data: Any) -> Any:
        """
        调用平台API
        
        Args:
            api: API名称（如 "send_msg", "get_group_info"）
            **data: API参数
            
        Returns:
            API返回结果
            
        Raises:
            NetworkError: 网络错误
            ApiNotAvailable: API不可用
        """
        raise NotImplementedError

    async def handle_event(self, event: "BaseEvent") -> None:
        """
        处理事件
        
        适配器收到事件后会调用此方法
        子类可以重写此方法进行协议特定的预处理
        
        Args:
            event: 事件对象（已经注入了 bot）
        """
        from Core.logging.file_logger import log_debug, log_warn

        # 注意：bot 已经在 adapter 中注入，这里不再重复注入

        # 记录事件接收
        log_debug(self.adapter.bot_id,
                  f"收到{self.adapter.get_protocol_name()}事件: {event.__class__.__name__}",
                  "BOT_EVENT_RECEIVED")

        # 调用全局事件处理器（由框架提供）
        if self.adapter.message_handler:
            # message_handler 可能是 sync 或 async
            import inspect
            if inspect.iscoroutinefunction(self.adapter.message_handler):
                await self.adapter.message_handler(event)
            else:
                self.adapter.message_handler(event)
        else:
            log_warn(self.adapter.bot_id,
                     "没有设置 message_handler，事件被忽略",
                     "BOT_NO_MESSAGE_HANDLER")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(adapter={self.adapter.get_name()}, self_id={self.self_id})"
