"""
KOOK Bot 类
"""

from typing import Any, TYPE_CHECKING

import aiohttp
import requests

from Core.logging.file_logger import log_error, log_debug
from .event import KookMessageEvent
from .message import KookMessage
from ..base.bot import BaseBot

if TYPE_CHECKING:
    from .adapter import KookAdapter
    from ..base.event import BaseEvent


class KookBot(BaseBot):
    """KOOK 机器人实例"""

    def __init__(self, adapter: "KookAdapter", self_id: str):
        super().__init__(adapter, self_id)
        self.bot_token = adapter.kook_config.bot_token
        self.api_base = adapter.kook_config.api_base.rstrip("/")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json",
        }

    async def send(
        self,
        event: "BaseEvent",
        message: KookMessage,
        **kwargs: Any
    ) -> Any:
        if not isinstance(event, KookMessageEvent):
            raise ValueError("KookBot can only handle KookMessageEvent")

        payload = message.to_kook_payload()
        if kwargs.get("reply", True) and event.message_id:
            payload["quote"] = event.message_id

        if event.message_type == "private":
            api = "/direct-message/create"
            payload["target_id"] = event.user_id
        else:
            api = "/message/create"
            payload["target_id"] = event.channel_id

        result = await self._request("POST", api, json_data=payload)
        return bool(result)

    async def call_api(self, api: str, **data: Any) -> Any:
        api_path = api if api.startswith("/") else f"/{api}"
        return await self._request("POST", api_path, json_data=data)

    async def _request(self, method: str, api: str, json_data: dict | None = None) -> Any:
        return await self._request_async_aiohttp(method, api, json_data)

    async def _request_async_aiohttp(self, method: str, api: str, json_data: dict | None = None) -> Any:
        url = f"{self.api_base}{api}"
        timeout = aiohttp.ClientTimeout(total=20)

        try:
            async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=self._headers(),
                    json=json_data or {},
                ) as resp:
                    try:
                        payload = await resp.json(content_type=None)
                    except Exception:
                        text = await resp.text()
                        log_error(self.adapter.bot_id, f"KOOK API 返回非JSON: {text[:200]}",
                                  "KOOK_API_NON_JSON", status=resp.status, api=api)
                        return None

            if payload.get("code") != 0:
                log_error(
                    self.adapter.bot_id,
                    f"KOOK API 调用失败: {payload.get('message', 'unknown')}",
                    "KOOK_API_CALL_FAILED",
                    api=api,
                    response_code=payload.get("code"),
                )
                return None

            return payload.get("data")
        except Exception as e:
            log_error(self.adapter.bot_id, f"KOOK API 请求异常: {e}",
                      "KOOK_API_REQUEST_ERROR", api=api, error=str(e))
            return None

    def test_connection_sync(self) -> tuple[bool, str]:
        """
        同步连接测试（供适配器 start 使用）
        """
        url = f"{self.api_base}/user/me"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                log_debug(self.adapter.bot_id, "KOOK 连接测试成功", "KOOK_TEST_OK")
                return True, ""
            return False, data.get("message", "KOOK API 连接失败")
        except Exception as e:
            return False, str(e)
