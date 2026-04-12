"""
KOOK 协议适配器

接收方式：Webhook（由 BluePrints/webhook/kook 处理）
发送方式：KOOK HTTP API
"""

from typing import Dict, Any, Optional

from Core.logging.file_logger import log_info, log_error, log_debug
from .bot import KookBot
from .config import KookConfig
from .event import KookEvent, KookMessageEvent
from ..base.adapter import BaseAdapter
from ..base.bot import BaseBot


class KookAdapter(BaseAdapter):
    """KOOK 适配器"""

    PROTOCOL = "kook"
    DISPLAY_NAME = "KOOK"
    WEBHOOK_PATH = "kook"
    WEBHOOK_HANDLER = "BluePrints.webhook.kook.handle_kook_webhook"
    STARTUP_ERROR_HINT = "KOOK适配器启动失败，请检查Bot Token与网络连通性"
    SUPPORTED_MESSAGE_TYPES = {"text", "image", "video", "voice", "file"}
    BOT_CONFIG_FIELDS = [
        {
            "name": "bot_token",
            "label": "Bot Token",
            "type": "password",
            "required": True,
            "placeholder": "请输入 KOOK Bot Token",
            "help": "在 KOOK 开发者中心获取",
        },
        {
            "name": "verify_token",
            "label": "Verify Token",
            "type": "text",
            "required": True,
            "placeholder": "请输入 KOOK Verify Token",
            "help": "用于Webhook回调验证",
        },
        {
            "name": "encrypt_key",
            "label": "Encrypt Key",
            "type": "text",
            "required": False,
            "default": "",
            "placeholder": "可选",
            "help": "如启用加密回调可填写",
        },
    ]

    def __init__(self, bot_id: int, config: Dict[str, Any]):
        super().__init__(bot_id, config)

        self.kook_config = KookConfig(**config)
        self.bot = KookBot(self, str(bot_id))

    def start(self) -> bool:
        self.last_error = None
        try:
            log_info(self.bot_id, "启动 KOOK 适配器", "KOOK_ADAPTER_START",
                     api_base=self.kook_config.api_base)

            ok, err = self.bot.test_connection_sync()
            if not ok:
                self.last_error = err or "KOOK 连接测试失败"
                log_error(self.bot_id, f"KOOK 连接测试失败: {self.last_error}",
                          "KOOK_ADAPTER_CONNECTION_FAILED")
                return False

            self.running = True
            log_info(self.bot_id, " KOOK 适配器启动成功", "KOOK_ADAPTER_STARTED")
            return True
        except Exception as e:
            self.last_error = str(e)
            log_error(self.bot_id, f"KOOK 适配器启动失败: {e}",
                      "KOOK_ADAPTER_START_ERROR", error=str(e))
            return False

    def stop(self) -> bool:
        try:
            log_info(self.bot_id, "停止 KOOK 适配器", "KOOK_ADAPTER_STOP")
            self.running = False
            log_info(self.bot_id, " KOOK 适配器已停止", "KOOK_ADAPTER_STOPPED")
            return True
        except Exception as e:
            log_error(self.bot_id, f"KOOK 适配器停止失败: {e}",
                      "KOOK_ADAPTER_STOP_ERROR", error=str(e))
            return False

    @classmethod
    def json_to_event(cls, json_data: Dict[str, Any]) -> Optional[KookEvent]:
        """
        将 KOOK Webhook 原始数据转为事件对象
        """
        try:
            payload = json_data.get("d", json_data)
            # KOOK 消息事件：包含 msg_id/target_id/author_id/content
            if any(k in payload for k in ("msg_id", "target_id", "author_id", "content")):
                return KookMessageEvent.from_raw(json_data)

            log_debug(0, "未识别的 KOOK 事件类型", "KOOK_UNKNOWN_EVENT",
                      payload_keys=list(payload.keys()) if isinstance(payload, dict) else [])
            return None
        except Exception as e:
            log_error(0, f"解析 KOOK 事件失败: {e}",
                      "KOOK_EVENT_PARSE_ERROR", error=str(e))
            return None

    async def _call_api(self, bot: BaseBot, api: str, **data: Any) -> Any:
        if not isinstance(bot, KookBot):
            raise ValueError("KookAdapter can only call API for KookBot")
        return await bot.call_api(api, **data)

    @classmethod
    def get_name(cls) -> str:
        return "KOOK"

    def get_protocol_name(self) -> str:
        return "kook"

    @classmethod
    def get_cache_key_field(cls) -> Optional[str]:
        # KOOK 暂不使用专用缓存映射
        return None

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "adapter_name": self.get_name(),
            "api_base": self.kook_config.api_base,
            "connection_type": self.kook_config.event_mode,
        })
        return status

    @classmethod
    def parse_bot_config_from_form(cls, form, existing_config: Optional[dict] = None) -> dict:
        config = super().parse_bot_config_from_form(form, existing_config)
        config["api_base"] = "https://www.kookapp.cn/api/v3"
        config["event_mode"] = "webhook"
        if not config.get("encrypt_key"):
            config["encrypt_key"] = None
        return config

    @classmethod
    def get_config_summary(cls, config: dict) -> str:
        token = str(config.get("bot_token", "") or "")
        verify_token = str(config.get("verify_token", "") or "")
        token_safe = f"{token[:6]}****" if token else "none"
        verify_safe = f"{verify_token[:6]}****" if verify_token else "none"
        return f"bot_token={token_safe} verify_token={verify_safe}"

    def build_text_message(self, content: str):
        from .message import KookMessage
        return KookMessage.text(content)

    def build_image_message(self, image_url_or_file_info: str = "", caption: str = "",
                            base64_data: str = None, auto_upload: bool = True):
        from .message import KookMessage
        return KookMessage.image(image_url_or_file_info or (f"base64://{base64_data}" if base64_data else ""))

    def build_video_message(self, video_url: str, caption: str = ""):
        from .message import KookMessage
        return KookMessage.video(video_url)

    def build_voice_message(self, voice_url: str):
        from .message import KookMessage
        return KookMessage.voice(voice_url)

    def build_file_message(self, file_url: str, filename: str = ""):
        from .message import KookMessage
        return KookMessage.file(file_url, filename)
