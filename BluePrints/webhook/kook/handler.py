"""
KOOK 协议 Webhook 处理器
"""

import json
import threading
import asyncio

from flask import jsonify

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from ..base import BaseWebhookHandler


class KookWebhookHandler(BaseWebhookHandler):
    """KOOK Webhook 处理器"""

    def __init__(self):
        super().__init__("KOOK")

    def validate_request(self, raw_data: bytes, headers: dict) -> tuple[bool, str]:
        if not raw_data:
            return False, "Empty request body"
        return True, ""

    def parse_event(self, raw_data: bytes) -> dict:
        try:
            return json.loads(raw_data.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

    def get_bot_identifier(self, headers: dict, event_data: dict) -> str:
        # KOOK 常见字段：verify_token
        identifier = (
            event_data.get("verify_token")
            or event_data.get("d", {}).get("verify_token")
            or headers.get("X-Verify-Token")
        )
        return identifier or ""

    def verify_signature(self, raw_data: bytes, headers: dict, secret: str) -> bool:
        # KOOK 当前最小实现仅校验 verify_token；无独立签名要求时直接通过
        return True

    def is_verification_request(self, event_data: dict) -> bool:
        # KOOK 回调验证常见 challenge 字段
        return "challenge" in event_data

    def handle_verification_request(self, event_data: dict, headers: dict):
        challenge = event_data.get("challenge")
        if not challenge:
            return jsonify({"error": "Missing challenge"}), 400
        log_info(0, "KOOK 回调验证成功", "KOOK_WEBHOOK_CHALLENGE_OK")
        return jsonify({"challenge": challenge}), 200

    def find_bot_by_identifier(self, identifier: str, bot_manager) -> int:
        """
        通过 verify_token 查找 KOOK 机器人
        """
        try:
            from flask import current_app
            with current_app.app_context():
                from Models import Bot
                bots = Bot.query.filter_by(protocol='kook').all()
                for bot in bots:
                    conf = bot.get_config()
                    if conf.get("verify_token") == identifier:
                        return bot.id
            return None
        except Exception as e:
            log_error(0, f"查找 KOOK 机器人失败: {e}", "KOOK_FIND_BOT_ERROR", error=str(e))
            return None

    def get_bot_secret(self, bot_id: int, bot_manager) -> str:
        # KOOK 最小实现不依赖该字段
        return None

    def handle_event(self, bot_id: int, event_data: dict, bot_manager) -> dict:
        try:
            from Adapters import get_adapter_manager
            from Adapters.kook.adapter import KookAdapter

            adapter_manager = get_adapter_manager()
            adapter = adapter_manager.running_adapters.get(bot_id)
            if not adapter:
                log_warn(bot_id, "KOOK 适配器未运行，忽略事件", "KOOK_ADAPTER_NOT_RUNNING")
                return {"status": "ignored", "reason": "adapter_not_running"}

            event = KookAdapter.json_to_event(event_data)
            if not event:
                return {"status": "ignored", "reason": "unsupported_event"}

            event.bot = adapter.bot

            def run_handler():
                try:
                    asyncio.run(adapter.bot.handle_event(event))
                except Exception as e:
                    log_error(bot_id, f"KOOK 异步事件处理失败: {e}",
                              "KOOK_EVENT_ASYNC_ERROR", error=str(e))

            threading.Thread(target=run_handler, daemon=True).start()

            payload = event_data.get("d", event_data)
            log_debug(bot_id, "KOOK 事件已投递处理", "KOOK_EVENT_DISPATCHED",
                      event_type=payload.get("type"), msg_id=payload.get("msg_id"))
            return {"status": "success"}
        except Exception as e:
            log_error(bot_id, f"KOOK 事件处理异常: {e}", "KOOK_EVENT_HANDLE_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}
