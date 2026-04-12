"""
KOOK 协议 Webhook 处理器
"""

import json
import threading
import asyncio
import gzip
import zlib

from flask import jsonify, request, Response

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from ..base import BaseWebhookHandler


class KookWebhookHandler(BaseWebhookHandler):
    """KOOK Webhook 处理器"""

    def __init__(self):
        super().__init__("KOOK")

    @staticmethod
    def _debug_print(stage: str, **kwargs):
        return None

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
            self._debug_print(
                "request_received",
                method=request.method,
                path=request.path,
                content_type=headers.get("Content-Type"),
                content_encoding=headers.get("Content-Encoding"),
                content_length=len(raw_data),
                header_keys=list(headers.keys()),
                raw_hex_head=raw_data[:32].hex(),
                raw_utf8_head=raw_data[:120].decode("utf-8", errors="replace"),
            )

            is_valid, error_msg = self.validate_request(raw_data, headers)
            if not is_valid:
                self._debug_print("request_invalid", error_msg=error_msg)
                return jsonify({"error": error_msg}), 400

            event_data = self.parse_event(raw_data)
            self._debug_print(
                "event_parsed",
                root_keys=list(event_data.keys()) if isinstance(event_data, dict) else type(event_data).__name__,
                data_keys=list(event_data.get("d", {}).keys()) if isinstance(event_data, dict) and isinstance(event_data.get("d"), dict) else [],
                type_value=event_data.get("type") if isinstance(event_data, dict) else None,
                d_type=event_data.get("d", {}).get("type") if isinstance(event_data, dict) and isinstance(event_data.get("d"), dict) else None,
                d_channel_type=event_data.get("d", {}).get("channel_type") if isinstance(event_data, dict) and isinstance(event_data.get("d"), dict) else None,
                has_challenge=("challenge" in event_data) if isinstance(event_data, dict) else False,
                has_d_challenge=("challenge" in event_data.get("d", {})) if isinstance(event_data, dict) and isinstance(event_data.get("d"), dict) else False,
            )
            if self.is_verification_request(event_data):
                self._debug_print("verification_detected")
                return self.handle_verification_request(event_data, headers)
            self._debug_print("verification_not_detected")
        except Exception as e:
            self._debug_print("precheck_exception", error=str(e))
            log_error(0, f"KOOK Webhook预处理异常: {e}", "KOOK_WEBHOOK_PRECHECK_ERROR", error=str(e))
            return jsonify({"error": "Invalid webhook request"}), 400

        return super().process_webhook()

    def parse_event(self, raw_data: bytes) -> dict:
        candidates: list[tuple[str, bytes]] = [("raw", raw_data)]

        # gzip
        try:
            decompressed = gzip.decompress(raw_data)
            candidates.append(("gzip", decompressed))
            self._debug_print("decompress_ok", method="gzip", out_len=len(decompressed))
        except Exception as e:
            self._debug_print("decompress_fail", method="gzip", error=str(e))

        # zlib / deflate
        try:
            decompressed = zlib.decompress(raw_data)
            candidates.append(("zlib", decompressed))
            self._debug_print("decompress_ok", method="zlib", out_len=len(decompressed))
        except Exception as e:
            self._debug_print("decompress_fail", method="zlib", error=str(e))
        try:
            decompressed = zlib.decompress(raw_data, -zlib.MAX_WBITS)
            candidates.append(("deflate_raw", decompressed))
            self._debug_print("decompress_ok", method="deflate_raw", out_len=len(decompressed))
        except Exception as e:
            self._debug_print("decompress_fail", method="deflate_raw", error=str(e))

        for source, payload in candidates:
            try:
                text = payload.decode("utf-8")
                event = json.loads(text)
                self._debug_print("json_parse_ok", source=source, text_head=text[:160])
                return event
            except Exception as e:
                self._debug_print(
                    "json_parse_fail",
                    source=source,
                    error=str(e),
                    payload_len=len(payload),
                    payload_hex_head=payload[:32].hex(),
                )
                continue

        raise ValueError("Invalid KOOK payload: cannot decode JSON with utf-8/gzip/deflate")

    def get_bot_identifier(self, headers: dict, event_data: dict) -> str:
        # KOOK 常见字段：verify_token
        top_token = event_data.get("verify_token")
        d_token = event_data.get("d", {}).get("verify_token")
        header_token = headers.get("X-Verify-Token")

        identifier = top_token or d_token or header_token or ""
        normalized = str(identifier).strip()
        self._debug_print(
            "identifier_resolved",
            top_verify_token=top_token,
            d_verify_token=d_token,
            header_verify_token=header_token,
            normalized_identifier=normalized,
        )
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
        self._debug_print(
            "verification_handle",
            challenge=challenge,
            verify_token=event_data.get("verify_token") or event_data.get("d", {}).get("verify_token"),
            d_type=event_data.get("d", {}).get("type") if isinstance(event_data.get("d"), dict) else None,
            d_channel_type=event_data.get("d", {}).get("channel_type") if isinstance(event_data.get("d"), dict) else None,
        )
        if not challenge:
            self._debug_print("verification_missing_challenge")
            return jsonify({"error": "Missing challenge"}), 400

        # 严格按文档返回 challenge，避免框架/代理导致格式偏差
        response_body = json.dumps({"challenge": challenge}, ensure_ascii=False, separators=(",", ":"))
        self._debug_print("verification_response", status=200, body=response_body)
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
                self._debug_print("bot_lookup_start", identifier=identifier, bots_count=len(bots))
                for bot in bots:
                    conf = bot.get_config()
                    conf_verify_token = str(conf.get("verify_token") or "").strip()
                    self._debug_print(
                        "bot_lookup_compare",
                        bot_id=bot.id,
                        bot_name=getattr(bot, "name", ""),
                        conf_verify_token=conf_verify_token,
                        matched=(conf_verify_token == identifier),
                    )
                    if conf_verify_token == identifier:
                        self._debug_print("bot_lookup_matched", bot_id=bot.id)
                        return bot.id
            self._debug_print("bot_lookup_not_found", identifier=identifier)
            return None
        except Exception as e:
            self._debug_print("bot_lookup_exception", error=str(e))
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
            self._debug_print("dispatch_prepare", bot_id=bot_id, adapter_exists=adapter is not None)
            if not adapter:
                log_warn(bot_id, "KOOK 适配器未运行，忽略事件", "KOOK_ADAPTER_NOT_RUNNING")
                return {"status": "ignored", "reason": "adapter_not_running"}

            event = KookAdapter.json_to_event(event_data)
            self._debug_print("dispatch_event_parsed", event_class=event.__class__.__name__ if event else None)
            if not event:
                self._debug_print(
                    "dispatch_unsupported_event",
                    payload_keys=list(event_data.get("d", {}).keys()) if isinstance(event_data.get("d"), dict) else [],
                )
                return {"status": "ignored", "reason": "unsupported_event"}

            event.bot = adapter.bot

            def run_handler():
                try:
                    self._debug_print(
                        "dispatch_handler_enter",
                        bot_id=bot_id,
                        event_name=event.get_event_name() if hasattr(event, "get_event_name") else type(event).__name__,
                        message_type=getattr(event, "message_type", None),
                        user_id=getattr(event, "user_id", None),
                        channel_id=getattr(event, "channel_id", None),
                        content_preview=(event.get_plaintext()[:80] if hasattr(event, "get_plaintext") else ""),
                    )
                    asyncio.run(adapter.bot.handle_event(event))
                    self._debug_print(
                        "dispatch_handler_exit",
                        bot_id=bot_id,
                        event_name=event.get_event_name() if hasattr(event, "get_event_name") else type(event).__name__,
                    )
                except Exception as e:
                    self._debug_print("dispatch_handler_error", bot_id=bot_id, error=str(e))
                    log_error(bot_id, f"KOOK 异步事件处理失败: {e}",
                              "KOOK_EVENT_ASYNC_ERROR", error=str(e))

            thread = threading.Thread(target=run_handler, daemon=True, name=f"KOOKEvent-{bot_id}")
            self._debug_print("dispatch_thread_create", bot_id=bot_id, thread_name=thread.name)
            thread.start()
            self._debug_print("dispatch_thread_started", bot_id=bot_id, thread_name=thread.name, is_alive=thread.is_alive())

            payload = event_data.get("d", event_data)
            log_debug(bot_id, "KOOK 事件已投递处理", "KOOK_EVENT_DISPATCHED",
                      kook_event_type=payload.get("type"), msg_id=payload.get("msg_id"))
            return {"status": "success"}
        except Exception as e:
            log_error(bot_id, f"KOOK 事件处理异常: {e}", "KOOK_EVENT_HANDLE_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}
