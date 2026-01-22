"""
QQ协议适配器

基于QQ官方Webhook API
"""

from typing import Dict, Any, Optional

from Core.logging.file_logger import log_info, log_error, log_debug
from .bot import QQBot
from .config import QQConfig
from .event import QQMessageEvent, QQEvent
from ..base.adapter import BaseAdapter
from ..base.bot import BaseBot


class QQAdapter(BaseAdapter):
    """
    QQ官方协议适配器
    
    接收方式：Webhook（由BluePrints/webhook/qq处理）
    发送方式：HTTP API
    """

    def __init__(self, bot_id: int, config: Dict[str, Any]):
        super().__init__(bot_id, config)

        # 解析配置
        self.qq_config = QQConfig(**config)

        # 创建Bot实例
        self.bot = QQBot(self, self.qq_config.app_id)
        self.bot.app_secret = self.qq_config.app_secret

    def start(self) -> bool:
        """
        启动QQ适配器
        
        QQ使用Webhook模式，启动时只需验证API连接
        """
        self.last_error = None  # 重置错误信息
        try:
            log_info(self.bot_id, f"启动QQ适配器: {self.bot.app_id}", "QQ_ADAPTER_START")

            # 验证API连接
            api_client = self.bot._get_api_client()
            connection_result = api_client.test_connection()

            if not connection_result:
                api_error = getattr(api_client, 'last_error_message', None) or "QQ API连接失败"
                self.last_error = api_error  # 保存到适配器
                self.bot.last_error = api_error
                log_error(self.bot_id, f"QQ API连接测试失败: {api_error}",
                          "QQ_ADAPTER_CONNECTION_FAILED")
                return False

            # 获取机器人信息
            bot_info = api_client.get_bot_info()
            if bot_info:
                log_info(self.bot_id, f"QQ机器人信息: {bot_info.get('username')}",
                         "QQ_BOT_INFO")

            self.running = True
            log_info(self.bot_id, "✅ QQ适配器启动成功", "QQ_ADAPTER_STARTED")
            return True

        except Exception as e:
            self.last_error = str(e)
            log_error(self.bot_id, f"QQ适配器启动失败: {e}",
                      "QQ_ADAPTER_START_ERROR", error=str(e))
            return False

    def stop(self) -> bool:
        """停止QQ适配器"""
        try:
            log_info(self.bot_id, "停止QQ适配器", "QQ_ADAPTER_STOP")
            self.running = False
            log_info(self.bot_id, "✅ QQ适配器已停止", "QQ_ADAPTER_STOPPED")
            return True
        except Exception as e:
            log_error(self.bot_id, f"QQ适配器停止失败: {e}",
                      "QQ_ADAPTER_STOP_ERROR", error=str(e))
            return False

    @classmethod
    def json_to_event(cls, json_data: Dict[str, Any]) -> Optional[QQEvent]:
        """
        将QQ Webhook数据转换为Event对象
        
        Args:
            json_data: QQ Webhook推送的原始JSON
            
        Returns:
            QQEvent对象，如果解析失败返回None
        """
        try:
            # 判断事件类型（QQ目前主要是消息事件）
            if "content" in json_data or "type" in json_data:
                # 消息事件
                return QQMessageEvent.from_raw(json_data)
            else:
                # 其他事件类型（暂不支持）
                log_debug(0, f"未知的QQ事件类型", "QQ_UNKNOWN_EVENT",
                          event_keys=list(json_data.keys()))
                return None

        except Exception as e:
            log_error(0, f"解析QQ事件失败: {e}", "QQ_EVENT_PARSE_ERROR",
                      error=str(e))
            return None

    async def _call_api(self, bot: BaseBot, api: str, **data: Any) -> Any:
        """
        调用QQ API
        
        Args:
            bot: Bot实例
            api: API名称
            **data: API参数
            
        Returns:
            API返回结果
        """
        if not isinstance(bot, QQBot):
            raise ValueError("QQAdapter can only call API for QQBot")

        return await bot.call_api(api, **data)

    @classmethod
    def get_name(cls) -> str:
        """适配器名称"""
        return "QQ Official"

    def get_protocol_name(self) -> str:
        """协议名称"""
        return "qq"

    @classmethod
    def get_cache_key_field(cls) -> str:
        """
        返回缓存键字段
        
        QQ协议使用app_id作为Webhook路由的唯一标识
        """
        return "app_id"

    def get_status(self) -> Dict[str, Any]:
        """获取适配器状态"""
        status = super().get_status()
        status.update({
            "adapter_name": self.get_name(),
            "app_id": self.qq_config.app_id,
            "connection_type": "webhook"
        })
        return status
