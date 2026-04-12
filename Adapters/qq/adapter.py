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
            log_info(self.bot_id, "QQ适配器启动成功", "QQ_ADAPTER_STARTED")
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
            log_info(self.bot_id, "QQ适配器已停止", "QQ_ADAPTER_STOPPED")
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
        return "QQ"

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

    @classmethod
    def get_config_summary(cls, config: dict) -> str:
        app_id = str(config.get("app_id", "") or "")
        safe_app_id = app_id[:8] + "****" if len(app_id) > 8 else app_id
        return f"app_id={safe_app_id}"

    def build_text_message(self, content: str):
        from .message import QQMessage
        return QQMessage.text(content)

    def build_image_message(self, image_url_or_file_info: str = "", caption: str = "",
                            base64_data: str = None, auto_upload: bool = True):
        from .message import QQMessage, QQMessageSegment
        return QQMessage([QQMessageSegment.image(
            url=image_url_or_file_info,
            caption=caption,
            base64_data=base64_data
        )])

    def build_video_message(self, video_url: str, caption: str = ""):
        from .message import QQMessage
        return QQMessage.video(video_url, caption)

    def build_voice_message(self, voice_url: str):
        from .message import QQMessage
        return QQMessage.voice(voice_url)

    def build_file_message(self, file_url: str, filename: str = ""):
        from .message import QQMessage
        return QQMessage.file(file_url, filename)

    def build_markdown_message(self, content: str, template_id: str = "", keyboard_id: str = ""):
        from .message import QQMessage, QQMessageSegment
        if template_id:
            return QQMessage([QQMessageSegment.markdown_template(template_id, content, keyboard_id)])
        return QQMessage([QQMessageSegment.markdown(content)])

    def build_keyboard_message(self, content: str, keyboard_id: str):
        from .message import QQMessage, QQMessageSegment
        return QQMessage([QQMessageSegment.keyboard(content, keyboard_id)])

    def build_ark_message(self, content: str, template_id: int = 24):
        import json
        from .message import QQMessage, QQMessageSegment
        try:
            kv = json.loads(content)
            if not isinstance(kv, list):
                raise ValueError("ARK内容必须是JSON数组格式")
        except json.JSONDecodeError as e:
            raise ValueError(f"ARK内容JSON解析失败: {e}")
        return QQMessage([QQMessageSegment.ark(template_id, kv)])
    PROTOCOL = "qq"
    DISPLAY_NAME = "QQ"
    WEBHOOK_PATH = "qq"
    WEBHOOK_HANDLER = "BluePrints.webhook.qq.handle_qq_webhook"
    STARTUP_ERROR_HINT = "QQ API连接验证失败，请检查AppID/AppSecret和IP白名单设置"
    SUPPORTED_MESSAGE_TYPES = {"text", "image", "video", "voice", "file", "markdown", "ark"}
    UNIQUE_CONFIG_FIELDS = ["app_id"]
    BOT_CONFIG_FIELDS = [
        {
            "name": "app_id",
            "label": "App ID",
            "type": "text",
            "required": True,
            "placeholder": "请输入QQ机器人App ID",
            "help": "在QQ开放平台获取",
        },
        {
            "name": "app_secret",
            "label": "App Secret",
            "type": "password",
            "required": True,
            "placeholder": "请输入QQ机器人App Secret",
            "help": "用于Webhook签名验证和API鉴权",
        },
    ]
