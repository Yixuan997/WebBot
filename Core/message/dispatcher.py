"""
消息异步调度器

统一维护常驻 asyncio 事件循环，避免每条消息重复创建线程和事件循环。
"""

import asyncio
import threading
from concurrent.futures import Future

from Core.logging.file_logger import log_debug, log_error


class MessageAsyncDispatcher:
    """全局协程调度器（单例）"""

    def __init__(self):
        self._loop = None
        self._thread = None
        self._lock = threading.Lock()

    def _ensure_loop(self):
        with self._lock:
            if self._loop and self._loop.is_running():
                return

            self._loop = asyncio.new_event_loop()

            def _run_loop(loop):
                asyncio.set_event_loop(loop)
                loop.run_forever()

            self._thread = threading.Thread(
                target=_run_loop,
                args=(self._loop,),
                name="MessageAsyncDispatcher",
                daemon=True
            )
            self._thread.start()

    async def _guarded_coro(self, coro, bot_id: int, source: str):
        try:
            return await coro
        except Exception as e:
            log_error(
                bot_id,
                f"异步任务执行失败: {e}",
                "ASYNC_DISPATCH_TASK_ERROR",
                source=source,
                error=str(e)
            )
            return None

    def submit(self, coro, bot_id: int = 0, source: str = "unknown") -> Future:
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._guarded_coro(coro, bot_id=bot_id, source=source),
            self._loop
        )
        log_debug(
            bot_id,
            "异步任务已提交到消息调度器",
            "ASYNC_DISPATCH_SUBMITTED",
            source=source
        )
        return future


message_async_dispatcher = MessageAsyncDispatcher()

