"""
KOOK 协议 Webhook 处理器
"""

import json
import gzip
import zlib

from flask import jsonify, request, Response

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from Core.message.dispatcher import message_async_dispatcher
from ..base import BaseWebhookHandler


class KookWebhookHandler(BaseWebhookHandler):
    """KOOK Webhook 处理器"""

    def __init__(self):
        super().__init__("KOOK")


    def validate_request(self, raw_data: bytes, headers: dict) -> tuple[bool, str]:
        if not raw_data:
            return False, "Empty request body"
        return True, ""

    def process_webhook(self):
        """
        KOOK 回调验证优先短路：
        challenge 请求不依赖 bot 标识和签名校验，直接回显 challenge。
        其余事件走基类通用流程。
        """
        try:
            raw_data = request.get_data()
            headers = dict(request.headers)

            is_valid, error_msg = self.validate_request(raw_data, headers)
            if not is_valid:
                return jsonify({"error": error_msg}), 400

            event_data = self.parse_event(raw_data)
            if self.is_verification_request(event_data):
                return self.handle_verification_request(event_data, headers)
        except Exception as e:
            log_error(0, f"KOOK Webhook预处理异常: {e}", "KOOK_WEBHOOK_PRECHECK_ERROR", error=str(e))
            return jsonify({"error": "Invalid webhook request"}), 400

        return super().process_webhook()

    def parse_event(self, raw_data: bytes) -> dict:
        candidates: list[tuple[str, bytes]] = [("raw", raw_data)]

        # gzip
        try:
            decompressed = gzip.decompress(raw_data)
            candidates.append(("gzip", decompressed))
        except Exception:
            pass

        # zlib / deflate
        try:
            decompressed = zlib.decompress(raw_data)
            candidates.append(("zlib", decompressed))
        except Exception:
            pass
        try:
            decompressed = zlib.decompress(raw_data, -zlib.MAX_WBITS)
            candidates.append(("deflate_raw", decompressed))
        except Exception:
            pass

        for source, payload in candidates:
            try:
                text = payload.decode("utf-8")
                event = json.loads(text)
                return event
            except Exception:
                continue

        raise ValueError("Invalid KOOK payload: cannot decode JSON with utf-8/gzip/deflate")

    def get_bot_identifier(self, headers: dict, event_data: dict) -> str:
        # KOOK 常见字段：verify_token
        top_token = event_data.get("verify_token")
        d_token = event_data.get("d", {}).get("verify_token")
        header_token = headers.get("X-Verify-Token")

        identifier = top_token or d_token or header_token or ""
        normalized = str(identifier).strip()
        return normalized

    def verify_signature(self, raw_data: bytes, headers: dict, secret: str) -> bool:
        # KOOK 当前最小实现仅校验 verify_token；无独立签名要求时直接通过
        return True

    def is_verification_request(self, event_data: dict) -> bool:
        # KOOK 文档中的 challenge 常见位置：
        # 1) 顶层 challenge
        # 2) d.challenge，且 d.type=255 / d.channel_type=WEBHOOK_CHALLENGE
        if "challenge" in event_data:
            return True

        data = event_data.get("d")
        if isinstance(data, dict):
            if "challenge" in data:
                return True
            if data.get("type") == 255:
                return True
            if data.get("channel_type") == "WEBHOOK_CHALLENGE":
                return True

        return False

    def handle_verification_request(self, event_data: dict, headers: dict):
        challenge = event_data.get("challenge") or event_data.get("d", {}).get("challenge")
        if not challenge:
            return jsonify({"error": "Missing challenge"}), 400

        # 严格按文档返回 challenge，避免框架/代理导致格式偏差
        response_body = json.dumps({"challenge": challenge}, ensure_ascii=False, separators=(",", ":"))
        log_info(0, "KOOK 回调验证成功", "KOOK_WEBHOOK_CHALLENGE_OK")
        return Response(response_body, status=200, mimetype="application/json")

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
                    conf_verify_token = str(conf.get("verify_token") or "").strip()
                    if conf_verify_token == identifier:
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
            message_async_dispatcher.submit(
                adapter.bot.handle_event(event),
                bot_id=bot_id,
                source="kook_webhook_event"
            )

            payload = event_data.get("d", event_data)
            log_debug(bot_id, "KOOK 事件已投递处理", "KOOK_EVENT_DISPATCHED",
                      kook_event_type=payload.get("type"), msg_id=payload.get("msg_id"))
            return {"status": "success"}
        except Exception as e:
            log_error(bot_id, f"KOOK 事件处理异常: {e}", "KOOK_EVENT_HANDLE_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}
