"""
QQ Bot类

代表一个QQ机器人实例
"""

from typing import Any, TYPE_CHECKING

from .event import QQMessageEvent
from .message import QQMessage
from ..base.bot import BaseBot

if TYPE_CHECKING:
    from .adapter import QQAdapter
    from ..base.event import BaseEvent


class QQBot(BaseBot):
    """
    QQ机器人
    
    存储QQ特定信息，提供发送消息等方法
    """

    def __init__(self, adapter: "QQAdapter", self_id: str):
        super().__init__(adapter, self_id)
        self.app_id = self_id
        self.app_secret = ""
        self._api_client = None

    def _get_api_client(self):
        """获取API客户端（延迟加载）"""
        if self._api_client is None:
            from .api_client import get_qq_api_client
            try:
                from flask import current_app
                with current_app.app_context():
                    self._api_client = get_qq_api_client(self.app_id, self.app_secret)
            except RuntimeError:
                # 没有应用上下文，尝试直接导入
                from app import app
                with app.app_context():
                    self._api_client = get_qq_api_client(self.app_id, self.app_secret)

        return self._api_client

    async def send(
            self,
            event: "BaseEvent",
            message: QQMessage,
            **kwargs: Any
    ) -> Any:
        """
        发送消息
        
        Args:
            event: 事件对象
            message: QQ消息对象
            **kwargs: 额外参数（如 reply=True）
            
        Returns:
            发送结果
        """
        if not isinstance(event, QQMessageEvent):
            raise ValueError("QQBot can only handle QQMessageEvent")

        # 转换消息为QQ API格式
        qq_format = message.to_api_format()

        # 获取目标
        target = event.get_target()

        # 获取reply_to_msg_id
        reply_to_msg_id = event.message_id if kwargs.get("reply", True) else None

        # 发送
        return await self._send_to_target(
            target,
            qq_format,
            reply_to_msg_id,
            event.message_id
        )

    async def _send_to_target(
            self,
            target: str,
            message: dict,
            reply_to_msg_id: str = None,
            original_msg_id: str = None
    ):
        """
        发送消息到指定目标
        
        Args:
            target: 目标字符串（如 "group:xxx", "user:xxx"）
            message: QQ API格式的消息
            reply_to_msg_id: 回复的消息ID
            original_msg_id: 原始消息ID
            
        Returns:
            发送结果
        """
        from Core.logging.file_logger import log_error

        try:
            # 解析目标
            target_type, target_id = target.split(":", 1) if ":" in target else ("user", target)

            # 获取API客户端
            api_client = self._get_api_client()

            # 确保认证
            api_client.ensure_authenticated()

            # 检查是否需要上传富媒体
            if message.get('_needs_upload'):
                file_type = message.get('_file_type', 1)  # 默认1=图片
                media_url = message.get('media', {}).get('file_info', '')
                base64_data = message.get('_base64_data')  # 获取 base64 数据

                # 上传富媒体（支持 URL 或 base64）
                upload_result = api_client.upload_media(
                    file_type=file_type,
                    url=media_url if not base64_data else "",
                    target_type=target_type,
                    target_id=target_id,
                    file_data=base64_data  # 传递 base64 数据
                )

                if not upload_result:
                    log_error(self.adapter.bot_id, "富媒体上传失败", "QQ_MEDIA_UPLOAD_FAILED",
                              has_base64=bool(base64_data), has_url=bool(media_url))
                    return False

                # 更新消息中的media信息
                message = message.copy()
                message['media'] = {'file_info': upload_result.get('file_info', '')}
                # 移除内部标记
                message.pop('_needs_upload', None)
                message.pop('_file_type', None)
                message.pop('_base64_data', None)

            # 根据目标类型调用API
            if target_type == "group":
                return api_client.send_group_message_with_type(
                    target_id, message, reply_to_msg_id, original_msg_id
                )
            elif target_type == "user":
                return api_client.send_user_message_with_type(
                    target_id, message, reply_to_msg_id, original_msg_id
                )
            elif target_type == "channel":
                return api_client.send_channel_message_with_type(
                    target_id, message, reply_to_msg_id, original_msg_id
                )
            elif target_type == "dm":
                return api_client.send_dm_message_with_type(
                    target_id, message, reply_to_msg_id, original_msg_id
                )
            else:
                log_error(self.adapter.bot_id, f"不支持的目标类型: {target_type}",
                          "QQ_UNSUPPORTED_TARGET")
                return False

        except Exception as e:
            log_error(self.adapter.bot_id, f"发送消息失败: {e}",
                      "QQ_SEND_ERROR", error=str(e))
            return False

    async def call_api(self, api: str, **data: Any) -> Any:
        """
        调用QQ API
        
        Args:
            api: API名称
            **data: API参数
            
        Returns:
            API返回结果
        """
        api_client = self._get_api_client()
        # 这里可以封装更多QQ API调用
        return None
