"""
OneBot V11协议适配器

基于正向WebSocket连接
使用websocket-client库
"""

import asyncio
import json
import threading
import time
import uuid
from typing import Dict, Any, Optional

import websocket

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from .bot import OneBotBot
from .config import OneBotConfig
from .event import OneBotEvent, OneBotMessageEvent, OneBotNoticeEvent, OneBotRequestEvent, OneBotMetaEvent
from ...base.adapter import BaseAdapter
from ...base.bot import BaseBot


class OneBotAdapter(BaseAdapter):
    """OneBot V11协议适配器（正向WebSocket客户端）"""

    PROTOCOL = "onebot"
    DISPLAY_NAME = "OneBot V11"
    STARTUP_ERROR_HINT = "OneBot适配器启动失败，请检查WebSocket配置"
    SUPPORTED_MESSAGE_TYPES = {"text", "image", "video", "voice"}
    BOT_CONFIG_FIELDS = [
        {
            "name": "ws_host",
            "label": "OneBot地址",
            "type": "text",
            "required": True,
            "default": "127.0.0.1",
            "placeholder": "127.0.0.1",
            "help": "OneBot客户端的IP地址",
        },
        {
            "name": "ws_port",
            "label": "OneBot端口",
            "type": "number",
            "required": True,
            "default": 5700,
            "placeholder": "5700",
            "help": "OneBot客户端的WebSocket端口",
        },
        {
            "name": "access_token",
            "label": "Access Token",
            "type": "password",
            "required": False,
            "default": "",
            "placeholder": "可选",
            "help": "如果OneBot配置了Token，请填写",
        },
        {
            "name": "self_trigger",
            "label": "处理自发消息",
            "type": "checkbox",
            "required": False,
            "default": False,
            "help": "开启后会处理机器人自己发出的消息",
        },
    ]

    def __init__(self, bot_id: int, config: Dict[str, Any]):
        super().__init__(bot_id, config)

        # 解析配置
        self.onebot_config = OneBotConfig(**config)

        # WebSocket配置
        self.ws_host = self.onebot_config.ws_host
        self.ws_port = self.onebot_config.ws_port
        self.access_token = self.onebot_config.access_token
        self.self_trigger = self.onebot_config.self_trigger
        self.ws_url = f"ws://{self.ws_host}:{self.ws_port}/"

        # WebSocket相关
        self.ws_app = None
        self.ws_thread = None
        self.connected = False
        self._stop_flag = threading.Event()

        # 事件循环相关
        self.event_loop = None
        self.loop_thread = None

        # 统计信息
        self.start_time = None
        self.message_count = 0
        self.error_count = 0
        self.last_error = None

        # Bot实例（启动后创建）
        self.bot = None

        # API响应等待队列
        self.api_responses = {}  # {echo: response_data}

    def start(self) -> bool:
        """启动OneBot适配器"""
        try:
            log_info(self.bot_id, f"启动OneBot适配器", "ONEBOT_ADAPTER_START",
                     ws_url=self.ws_url)

            # 启动专用事件循环线程
            self._start_event_loop()

            # 创建WebSocketApp
            self._create_websocket_app()

            # 在独立线程中运行
            self.ws_thread = threading.Thread(
                target=self._run_websocket,
                name=f"OneBot-{self.bot_id}",
                daemon=True
            )
            self.ws_thread.start()

            # 等待连接建立（最多10秒）
            for _ in range(100):
                if self.connected:
                    break
                time.sleep(0.1)

            if self.connected:
                self.running = True
                self.start_time = time.time()
                log_info(self.bot_id, " OneBot适配器启动成功",
                         "ONEBOT_ADAPTER_STARTED", ws_url=self.ws_url)
                return True
            else:
                self.last_error = f"连接到 {self.ws_url} 超时"
                log_error(self.bot_id, "OneBot适配器启动失败: 连接超时",
                          "ONEBOT_ADAPTER_START_TIMEOUT")
                return False

        except Exception as e:
            self.last_error = str(e)
            log_error(self.bot_id, f"OneBot适配器启动失败: {e}",
                      "ONEBOT_ADAPTER_START_ERROR", error=str(e))
            return False

    def stop(self) -> bool:
        """停止OneBot适配器"""
        try:
            log_info(self.bot_id, "停止OneBot适配器", "ONEBOT_ADAPTER_STOP")

            # 设置停止标志
            self._stop_flag.set()
            self.running = False
            self.connected = False

            # 关闭WebSocket
            if self.ws_app:
                try:
                    self.ws_app.close()
                except Exception:
                    pass

            # 等待WebSocket线程结束
            if self.ws_thread and self.ws_thread.is_alive():
                self.ws_thread.join(timeout=5)

            # 停止事件循环
            self._stop_event_loop()

            # 统计信息
            if self.start_time:
                uptime = int(time.time() - self.start_time)
                log_info(self.bot_id, "OneBot运行统计", "ONEBOT_STATS",
                         uptime=f"{uptime}秒", messages=self.message_count)

            log_info(self.bot_id, " OneBot适配器已停止", "ONEBOT_ADAPTER_STOPPED")
            return True

        except Exception as e:
            log_error(self.bot_id, f"OneBot适配器停止失败: {e}",
                      "ONEBOT_ADAPTER_STOP_ERROR", error=str(e))
            return False

    def _create_websocket_app(self):
        """创建WebSocketApp实例"""
        headers = []
        if self.access_token:
            headers.append(f"Authorization: Bearer {self.access_token}")

        self.ws_app = websocket.WebSocketApp(
            self.ws_url,
            header=headers if headers else None,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )

    def _run_websocket(self):
        """在独立线程中运行WebSocket"""
        try:
            log_info(self.bot_id, f"正在连接到OneBot: {self.ws_url}", "ONEBOT_CONNECTING")

            self.ws_app.run_forever(
                ping_interval=30,
                ping_timeout=10,
                reconnect=5
            )

        except Exception as e:
            log_error(self.bot_id, f"WebSocket运行异常: {e}",
                      "ONEBOT_WS_RUN_ERROR", error=str(e))
            self.last_error = str(e)
        finally:
            self.connected = False
            if not self._stop_flag.is_set():
                self.running = False

    def _on_open(self, ws):
        """连接打开回调"""
        self.connected = True
        log_info(self.bot_id, f" 已连接到OneBot: {self.ws_url}", "ONEBOT_CONNECTED")

    def _on_message(self, ws, message):
        """收到消息回调"""
        try:
            data = json.loads(message)

            # 检查是否是API响应（包含 status/retcode 字段）
            if 'status' in data or 'retcode' in data:
                # 这是API调用的响应，不是事件
                echo = data.get('echo')
                if echo:
                    self.api_responses[echo] = data
                log_debug(self.bot_id, f" API响应: {data.get('status', 'ok')}", "ONEBOT_API_RESPONSE")
                return

            # 记录原始数据的基本信息
            post_type = data.get('post_type')
            message_type = data.get('message_type')

            # 根据配置决定是否过滤 message_sent 事件（自己发送的消息）
            if post_type == 'message_sent':
                if not self.self_trigger:
                    log_debug(self.bot_id,
                              f" 消息已发送",
                              "ONEBOT_MESSAGE_SENT",
                              message_id=data.get('message_id'))
                    return
                else:
                    log_info(self.bot_id,
                             f" 处理自己发送的消息（自触发已开启）",
                             "ONEBOT_MESSAGE_SENT_SELF_TRIGGER",
                             message_id=data.get('message_id'))

            log_debug(self.bot_id,
                      f" 收到OneBot事件: {post_type}",
                      "ONEBOT_EVENT_RECEIVED",
                      post_type=post_type,
                      message_type=message_type if post_type == 'message' else None,
                      time=data.get('time'),
                      self_id=data.get('self_id'))

            # 解析为Event对象
            event = self.json_to_event(data)
            if not event:
                return

            # 创建Bot实例（首次收到消息时）
            if not self.bot:
                self_id = str(data.get('self_id', 0))
                self.bot = OneBotBot(self, self_id)
                log_info(self.bot_id, f" OneBot实例创建: {self_id} (adapter={id(self)})", "ONEBOT_BOT_CREATED")
            elif self.bot and id(self.bot.adapter) != id(self):
                log_error(self.bot_id,
                          f" 检测到多个 adapter 实例！current={id(self)}, bot.adapter={id(self.bot.adapter)}",
                          "ONEBOT_DUPLICATE_ADAPTER")

            # 注入bot到event
            event.bot = self.bot

            # 记录消息详细信息
            if isinstance(event, OneBotMessageEvent):
                self.message_count += 1

                # 获取消息内容预览
                content_preview = event.get_plaintext()[:50]
                user_id = event.get_user_id()

                # 根据消息类型记录不同的日志
                if message_type == 'private':
                    log_info(self.bot_id,
                             f" 收到私聊消息",
                             "ONEBOT_PRIVATE_MESSAGE",
                             user_id=user_id,
                             message_id=data.get('message_id'),
                             content_preview=content_preview)
                elif message_type == 'group':
                    log_info(self.bot_id,
                             f" 收到群聊消息",
                             "ONEBOT_GROUP_MESSAGE",
                             user_id=user_id,
                             group_id=data.get('group_id'),
                             message_id=data.get('message_id'),
                             content_preview=content_preview)

                log_debug(self.bot_id,
                          "开始处理消息",
                          "ONEBOT_MESSAGE_START",
                          message_type=message_type,
                          content_preview=content_preview)

            # 提交任务到共享事件循环
            if self.bot and self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.bot.handle_event(event),
                    self.event_loop
                )

                if isinstance(event, OneBotMessageEvent):
                    log_debug(self.bot_id, " 消息处理完成", "ONEBOT_MESSAGE_DONE")

        except Exception as e:
            log_error(self.bot_id, f"处理消息异常: {e}",
                      "ONEBOT_MESSAGE_ERROR", error=str(e))

    def _on_error(self, ws, error):
        """错误回调"""
        self.error_count += 1
        self.last_error = str(error)
        log_error(self.bot_id, f"WebSocket错误: {error}",
                  "ONEBOT_WS_ERROR", error=str(error))

    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        self.connected = False

        if self._stop_flag.is_set():
            log_info(self.bot_id, "OneBot连接已关闭", "ONEBOT_CLOSED")
        else:
            log_warn(self.bot_id, f"OneBot连接意外关闭: {close_status_code}",
                     "ONEBOT_CONNECTION_LOST")

    def _start_event_loop(self):
        """启动专用事件循环线程"""
        self.event_loop = asyncio.new_event_loop()

        def run_loop():
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_forever()

        self.loop_thread = threading.Thread(
            target=run_loop,
            name=f"OneBot-Loop-{self.bot_id}",
            daemon=True
        )
        self.loop_thread.start()
        log_debug(self.bot_id, "事件循环线程已启动", "ONEBOT_LOOP_STARTED")

    def _stop_event_loop(self):
        """停止事件循环线程"""
        if self.event_loop and self.event_loop.is_running():
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)

            if self.loop_thread and self.loop_thread.is_alive():
                self.loop_thread.join(timeout=3)

            log_debug(self.bot_id, "事件循环线程已停止", "ONEBOT_LOOP_STOPPED")

    @classmethod
    def json_to_event(cls, json_data: Dict[str, Any]) -> Optional[OneBotEvent]:
        """
        将OneBot数据转换为Event对象
        
        Args:
            json_data: OneBot推送的原始数据
            
        Returns:
            OneBotEvent对象
        """
        try:
            post_type = json_data.get('post_type')

            # message 和 message_sent 都当作消息事件处理
            if post_type == 'message' or post_type == 'message_sent':
                return OneBotMessageEvent.from_raw(json_data)
            elif post_type == 'notice':
                return OneBotNoticeEvent.from_raw(json_data)
            elif post_type == 'request':
                return OneBotRequestEvent.from_raw(json_data)
            elif post_type == 'meta_event':
                return OneBotMetaEvent.from_raw(json_data)
            else:
                log_debug(0, f"未知OneBot事件类型: {post_type}", "ONEBOT_UNKNOWN_EVENT")
                return None

        except Exception as e:
            log_error(0, f"解析OneBot事件失败: {e}",
                      "ONEBOT_EVENT_PARSE_ERROR", error=str(e))
            return None

    async def _call_api(self, bot: BaseBot, api: str, **data: Any) -> Any:
        """
        调用OneBot API
        
        Args:
            bot: Bot实例
            api: API名称（如 "send_msg"）
            **data: API参数
            
        Returns:
            API返回结果
        """
        if not isinstance(bot, OneBotBot):
            raise ValueError("OneBotAdapter can only call API for OneBotBot")

        if not self.connected or not self.ws_app:
            log_error(self.bot_id, "WebSocket未连接", "ONEBOT_NOT_CONNECTED")
            return None

        try:
            # 生成唯一请求ID
            echo = str(uuid.uuid4())

            # 构建 API调用
            action = {
                "action": api,
                "params": data,
                "echo": echo
            }

            # 发送到WebSocket
            message_json = json.dumps(action)
            self.ws_app.send(message_json)

            log_debug(self.bot_id, f"发送OneBot API: {api}", "ONEBOT_API_SENT")

            # 等待响应（最多5秒）
            for _ in range(50):
                if echo in self.api_responses:
                    response = self.api_responses.pop(echo)

                    # 检查响应状态
                    status = response.get('status')
                    retcode = response.get('retcode', 0)

                    if status == 'ok' or retcode == 0:
                        log_debug(self.bot_id, f" API调用成功: {api}", "ONEBOT_API_SUCCESS")
                        return response.get('data')
                    else:
                        error_msg = response.get('message', '未知错误')
                        log_error(self.bot_id, f"API调用失败: {api} - {error_msg}",
                                  "ONEBOT_API_FAILED", error=error_msg)
                        return None

                await asyncio.sleep(0.1)

            # 超时
            log_error(self.bot_id, f"API调用超时: {api}", "ONEBOT_API_TIMEOUT")
            self.api_responses.pop(echo, None)
            return None

        except Exception as e:
            log_error(self.bot_id, f"调用OneBot API失败: {e}",
                      "ONEBOT_API_ERROR", error=str(e))
            return None

    @classmethod
    def get_name(cls) -> str:
        """适配器名称"""
        return "OneBot V11"

    def get_protocol_name(self) -> str:
        """协议名称"""
        return "onebot"

    @classmethod
    def get_cache_key_field(cls) -> Optional[str]:
        """OneBot不需要缓存键（不使用Webhook路由）"""
        return None

    def get_status(self) -> Dict[str, Any]:
        """获取适配器状态"""
        status = super().get_status()
        status.update({
            "adapter_name": self.get_name(),
            "ws_url": self.ws_url,
            "connected": self.connected,
            "message_count": self.message_count,
            "connection_type": "websocket"
        })
        return status

    @classmethod
    def parse_bot_config_from_form(cls, form, existing_config: Optional[dict] = None) -> dict:
        try:
            config = super().parse_bot_config_from_form(form, existing_config)
        except ValueError:
            raise ValueError("OneBot端口必须是数字")
        # OneBot 可选字段标准化
        if not config.get("access_token"):
            config["access_token"] = None
        if config.get("ws_port") is None:
            config["ws_port"] = 5700
        if not config.get("ws_host"):
            config["ws_host"] = "127.0.0.1"
        config["self_trigger"] = bool(config.get("self_trigger"))
        return config

    @classmethod
    def validate_bot_config(cls, config: dict) -> tuple[bool, str]:
        ok, err = super().validate_bot_config(config)
        if not ok:
            return ok, err
        try:
            int(config.get("ws_port"))
        except (TypeError, ValueError):
            return False, "OneBot协议配置项 ws_port 必须是数字"
        return True, ""

    @classmethod
    def get_config_summary(cls, config: dict) -> str:
        ws_host = config.get("ws_host", "")
        ws_port = config.get("ws_port", "")
        return f"ws://{ws_host}:{ws_port}"

    def build_text_message(self, content: str):
        from .message import OneBotMessage
        return OneBotMessage.text(content)

    def build_image_message(self, image_url_or_file_info: str = "", caption: str = "",
                            base64_data: str = None, auto_upload: bool = True):
        from .message import OneBotMessage
        return OneBotMessage.image(image_url_or_file_info or base64_data or "")

    def build_video_message(self, video_url: str, caption: str = ""):
        from .message import OneBotMessage
        return OneBotMessage.video(video_url)

    def build_voice_message(self, voice_url: str):
        from .message import OneBotMessage
        return OneBotMessage.record(voice_url)
