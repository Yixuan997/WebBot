"""
事件基类

定义所有协议事件必须实现的接口
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .bot import BaseBot
    from .message import BaseMessage


class BaseEvent(ABC):
    """
    事件基类
    
    所有协议的事件都必须继承此类并实现抽象方法
    """

    # Bot对象引用（由适配器注入）
    bot: Optional["BaseBot"] = None

    @abstractmethod
    def get_type(self) -> str:
        """
        获取事件类型
        
        Returns:
            事件类型字符串，如 "message", "notice", "request", "meta"
        """
        raise NotImplementedError

    @abstractmethod
    def get_event_name(self) -> str:
        """
        获取事件名称（用于日志和调试）
        
        Returns:
            事件名称，如 "message.private", "notice.group_increase"
        """
        raise NotImplementedError

    @abstractmethod
    def get_user_id(self) -> str:
        """
        获取触发事件的用户ID
        
        Returns:
            用户ID字符串
            
        Raises:
            ValueError: 如果事件没有用户上下文
        """
        raise NotImplementedError

    @abstractmethod
    def get_session_id(self) -> str:
        """
        获取会话ID（用于上下文管理）
        
        同一会话的多个事件应返回相同的session_id
        例如：同一群聊返回 "group_123456"，私聊返回 "private_789012"
        
        Returns:
            会话ID字符串
        """
        raise NotImplementedError

    @abstractmethod
    def get_message(self) -> Optional["BaseMessage"]:
        """
        获取消息内容
        
        Returns:
            消息对象，如果不是消息事件则返回None或抛出异常
            
        Raises:
            ValueError: 如果事件不包含消息
        """
        raise NotImplementedError

    @abstractmethod
    def get_plaintext(self) -> str:
        """
        获取纯文本内容
        
        从消息中提取所有文本内容（忽略图片、表情等）
        
        Returns:
            纯文本字符串
        """
        raise NotImplementedError

    @abstractmethod
    def is_tome(self) -> bool:
        """
        判断消息是否与机器人有关
        
        包括：@机器人、回复机器人消息、私聊等
        
        Returns:
            True表示消息与机器人相关
        """
        raise NotImplementedError

    # 便捷方法
    async def reply(self, message: "BaseMessage", **kwargs):
        """
        快捷回复此事件
        
        Args:
            message: 要发送的消息
            **kwargs: 其他参数传递给bot.send()
            
        Returns:
            发送结果
        """
        if self.bot:
            return await self.bot.send(self, message, **kwargs)
        raise RuntimeError("Event has no bot instance")
