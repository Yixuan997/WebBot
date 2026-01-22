"""
QQ官方API客户端 - 使用requests实现，解决aiohttp事件循环问题
"""
import time
from typing import Dict, Optional

import requests

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug


def get_qq_api_client(app_id: str, client_secret: str):
    """获取QQ API客户端单例 - 使用Flask应用上下文"""
    from flask import current_app

    # 使用app_id和secret的组合作为唯一标识
    key = f"_qq_api_client_{app_id}_{hash(client_secret)}"

    if not hasattr(current_app, key):
        log_info(0, f"创建新的QQAPIClient实例", "QQ_CLIENT_CREATE", app_id=app_id)
        client = QQAPIClient(app_id, client_secret)
        setattr(current_app, key, client)

    return getattr(current_app, key)


def clear_qq_api_client(app_id: str, client_secret: str):
    """清理特定的QQ API客户端实例（用于重新认证失败时）"""
    from flask import current_app

    key = f"_qq_api_client_{app_id}_{hash(client_secret)}"

    if hasattr(current_app, key):
        log_info(0, f"清理QQAPIClient实例", "QQ_CLIENT_CLEAR", app_id=app_id)
        delattr(current_app, key)


class QQAPIClient:
    """QQ官方API客户端 - 使用requests实现"""

    def __init__(self, app_id: str, client_secret: str):
        self.app_id = app_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expires_at = 0
        self.session = requests.Session()  # 使用requests.Session()
        self.last_error_message = None  # 保存最后的错误信息
        self._token_refreshing = False  # 标记是否正在刷新token
        self._refresh_thread = None  # 后台刷新线程引用

        # QQ官方API地址 - 严格按照官方文档
        self.api_base = "https://api.sgroup.qq.com"
        self.auth_url = "https://bots.qq.com/app/getAppAccessToken"
        self.bot_info_url = f"{self.api_base}/users/@me"

        # 消息发送API - 按照官方文档格式
        self.send_user_message_url = f"{self.api_base}/v2/users/{{}}/messages"  # 单聊
        self.send_group_message_url = f"{self.api_base}/v2/groups/{{}}/messages"  # 群聊
        self.send_channel_message_url = f"{self.api_base}/channels/{{}}/messages"  # 频道
        self.send_dm_message_url = f"{self.api_base}/dms/{{}}/messages"  # 频道私信

        # 富媒体上传API - 根据官方文档
        self.upload_group_media_url = f"{self.api_base}/v2/groups/{{}}/files"  # 群聊富媒体
        self.upload_user_media_url = f"{self.api_base}/v2/users/{{}}/files"  # 单聊富媒体

        # 消息序列号计数器 - 用于生成唯一的msg_seq
        self._msgseq_counter = 0

    def cleanup(self):
        """清理HTTP会话"""
        if self.session:
            try:
                self.session.close()
                log_debug(0, f"QQ API客户端会话已清理", "QQ_CLIENT_CLEANUP")
            except Exception as e:
                log_debug(0, f"清理会话时出现异常: {e}", "QQ_CLIENT_CLEANUP_ERROR")
        # 尝试等待刷新线程结束（短超时）
        try:
            if self._refresh_thread and self._refresh_thread.is_alive():
                self._refresh_thread.join(timeout=1)
        except Exception:
            pass

    def _generate_msgseq(self, original_message_id: str = None) -> int:
        """
        生成消息序列号

        Args:
            original_message_id: QQ官方的原始消息ID，用于回复消息时关联

        Returns:
            int: 消息序列号（数字类型）

        说明:
            - 基于msg_id生成递增序号，符合QQ官方API要求
            - 相同msg_id的多次回复会有不同的msg_seq（1, 2, 3...）
            - 避免相同 msg_id + msg_seq 组合重复发送
        """
        from Core.message.msgseq import get_msg_seq
        return get_msg_seq(original_message_id)

    def authenticate(self) -> bool:
        """获取访问令牌 - 使用requests实现"""
        try:
            log_info(0, "正在获取QQ API访问令牌...", "QQ_AUTH_START", app_id=self.app_id)

            # 确保session存在
            if not self.session:
                self.session = requests.Session()

            # 按照官方文档的请求参数格式
            auth_data = {
                "appId": self.app_id,
                "clientSecret": self.client_secret
            }

            headers = {
                "Content-Type": "application/json"
            }

            response = self.session.post(
                self.auth_url,
                json=auth_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # QQ API 特殊处理：先检查是否有错误码
                if "code" in data and data["code"] != 0:
                    # QQ API 返回了错误码
                    error_code = data["code"]
                    error_message = data.get("message", f"错误码: {error_code}")
                    self.last_error_message = f"QQ API错误 {error_code}: {error_message}"
                    log_error(0, f"QQ API认证失败: {self.last_error_message}", "QQ_AUTH_API_ERROR",
                              error_code=error_code, error_message=error_message)
                    return False
                elif "access_token" in data:
                    # 成功获取访问令牌
                    self.access_token = data["access_token"]
                    expires_in = int(data.get("expires_in", 7200))
                    self.token_expires_at = time.time() + expires_in

                    log_info(0, "QQ API认证成功", "QQ_AUTH_SUCCESS",
                             expires_in=expires_in, token_length=len(self.access_token))
                    return True
                else:
                    # 既没有错误码也没有access_token，这是异常情况
                    self.last_error_message = "响应格式异常：缺少access_token和错误码"
                    log_error(0, f"认证响应格式异常: {data}", "QQ_AUTH_FORMAT_ERROR")
                    return False
            else:
                error_text = response.text

                # 解析错误信息
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        self.last_error_message = error_data['message']
                    else:
                        self.last_error_message = f"HTTP {response.status_code}"
                except Exception:
                    self.last_error_message = f"HTTP {response.status_code}"

                log_error(0, f"QQ API认证失败: {self.last_error_message}", "QQ_AUTH_FAILED",
                          status=response.status_code, error=error_text)

                return False

        except Exception as e:
            self.last_error_message = str(e)
            log_error(0, f"QQ API认证异常: {e}", "QQ_AUTH_EXCEPTION", error=str(e))
            return False

    def is_token_valid(self) -> bool:
        """检查令牌是否有效"""
        if not self.access_token:
            return False

        current_time = time.time()

        # 按照QQ官方建议：在过期前60秒内需要刷新
        # 但在刷新期间，老token仍然有效
        return current_time < self.token_expires_at

    def should_refresh_token(self) -> bool:
        """检查是否应该刷新token（过期前60秒内）"""
        if not self.access_token:
            return True

        current_time = time.time()
        # 在过期前60秒内应该刷新
        return current_time >= (self.token_expires_at - 60)

    def ensure_authenticated(self) -> bool:
        """确保已认证 - 智能token刷新策略"""
        # 如果token完全无效，必须同步刷新
        if not self.is_token_valid():
            log_info(0, "Token无效，同步刷新", "QQ_TOKEN_SYNC_REFRESH")
            return self.authenticate()

        # 如果在刷新窗口期内，异步刷新
        if self.should_refresh_token():
            if not self._token_refreshing:
                log_info(0, "Token即将过期，后台刷新", "QQ_TOKEN_BACKGROUND_REFRESH")
                self._async_refresh_token()

        return True

    def _async_refresh_token(self):
        """异步刷新token"""
        import threading

        # 防止重复启动刷新线程
        if self._token_refreshing:
            return
        if self._refresh_thread and self._refresh_thread.is_alive():
            return

        def refresh_task():
            try:
                self._token_refreshing = True
                success = self.authenticate()
                if success:
                    log_info(0, "Token后台刷新成功", "QQ_TOKEN_BACKGROUND_REFRESH_SUCCESS")
                else:
                    log_warn(0, "Token后台刷新失败", "QQ_TOKEN_BACKGROUND_REFRESH_FAILED")
            except Exception as e:
                log_error(0, f"Token后台刷新异常: {e}", "QQ_TOKEN_BACKGROUND_REFRESH_ERROR")
            finally:
                self._token_refreshing = False

        self._refresh_thread = threading.Thread(target=refresh_task, daemon=True, name="QQTokenRefresh")
        self._refresh_thread.start()

    def get_token_status(self) -> dict:
        """获取token状态信息"""
        if not self.access_token:
            return {
                "has_token": False,
                "is_valid": False,
                "should_refresh": True,
                "expires_in": 0,
                "time_to_refresh": 0
            }

        current_time = time.time()
        expires_in = max(0, self.token_expires_at - current_time)
        time_to_refresh = max(0, (self.token_expires_at - 60) - current_time)

        return {
            "has_token": True,
            "is_valid": current_time < self.token_expires_at,
            "should_refresh": self.should_refresh_token(),
            "expires_in": int(expires_in),
            "time_to_refresh": int(time_to_refresh),
            "expires_at": self.token_expires_at
        }

    def get_bot_info(self) -> Optional[Dict]:
        """获取机器人信息"""
        try:
            if not self.ensure_authenticated():
                self.last_error_message = "认证失败"
                return None

            log_info(0, "正在获取机器人信息...", "QQ_BOT_INFO_REQUEST")

            # 确保session存在
            if not self.session:
                self.session = requests.Session()

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json",
                "User-Agent": "QQBot/1.0"
            }

            response = self.session.get(
                self.bot_info_url,
                headers=headers,
                timeout=15
            )

            if response.status_code == 200:
                bot_info = response.json()

                # QQ API 特殊处理：检查是否有错误码
                if "code" in bot_info and bot_info["code"] != 0:
                    # QQ API 返回了错误码
                    error_code = bot_info["code"]
                    error_message = bot_info.get("message", f"错误码: {error_code}")
                    self.last_error_message = f"QQ API错误 {error_code}: {error_message}"
                    log_error(0, f"获取机器人信息失败: {self.last_error_message}", "QQ_BOT_INFO_API_ERROR",
                              error_code=error_code, error_message=error_message)
                    return None
                elif "id" in bot_info:
                    # 成功获取机器人信息
                    log_info(0, "机器人信息获取成功", "QQ_BOT_INFO_SUCCESS",
                             qq_bot_id=bot_info.get("id"), username=bot_info.get("username"))
                    return bot_info
                else:
                    # 响应格式异常
                    self.last_error_message = "响应格式异常：缺少机器人信息"
                    log_error(0, f"机器人信息响应格式异常: {bot_info}", "QQ_BOT_INFO_FORMAT_ERROR")
                    return None
            else:
                error_text = response.text

                # 直接解析JSON中的message字段
                try:
                    error_data = response.json()
                    if 'message' in error_data:
                        self.last_error_message = error_data['message']
                    else:
                        self.last_error_message = f"HTTP {response.status_code}"
                except:
                    # 如果不是JSON，使用HTTP状态码
                    self.last_error_message = f"HTTP {response.status_code}"

                log_error(0, f"获取机器人信息失败: {self.last_error_message}", "QQ_BOT_INFO_FAILED",
                          status=response.status_code, error=error_text)

                return None

        except Exception as e:
            self.last_error_message = str(e)
            log_error(0, f"获取机器人信息异常: {e}", "QQ_BOT_INFO_EXCEPTION", error=str(e))
            return None

    def send_user_message(self, openid: str, content: str, msg_id: str = None) -> bool:
        """发送单聊消息 - 按照官方文档实现"""
        try:
            if not self.ensure_authenticated():
                return False

            log_info(0, f"正在发送单聊消息到用户 {openid}", "QQ_SEND_USER_START",
                     openid=openid, content_length=len(content))

            # 按照官方文档的鉴权格式
            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 按照官方文档的消息格式
            message_data = {
                "content": content,
                "msg_type": 0,  # 0 是文本消息
                "msg_seq": self._generate_msgseq(msg_id)  # 基于msg_id生成序列号
            }

            # 如果是回复消息，添加msg_id
            if msg_id:
                message_data["msg_id"] = msg_id

            url = self.send_user_message_url.format(openid)

            response = self.session.post(
                url,
                json=message_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                log_info(0, "单聊消息发送成功", "QQ_SEND_USER_SUCCESS",
                         openid=openid, message_id=result.get("id"))
                return True
            else:
                error_text = response.text
                log_error(0, f"发送单聊消息失败: HTTP {response.status_code}", "QQ_SEND_USER_FAILED",
                          openid=openid, status=response.status_code, error=error_text)
                return False

        except Exception as e:
            log_error(0, f"发送单聊消息异常: {e}", "QQ_SEND_USER_EXCEPTION",
                      openid=openid, error=str(e))
            return False

    def send_user_message_with_type(self, openid: str, message_data: dict, msg_id: str = None,
                                    original_msg_id: str = None) -> bool:
        """发送多类型用户消息"""
        try:
            if not self.ensure_authenticated():
                return False

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 使用传入的完整消息数据
            payload = message_data.copy()
            # 确保每条消息都有唯一的msg_seq（QQ官方使用msg_seq而不是msgseq）
            if "msg_seq" not in payload:
                payload["msg_seq"] = self._generate_msgseq(original_msg_id)
            if msg_id:
                payload["msg_id"] = msg_id

            url = self.send_user_message_url.format(openid)

            response = self.session.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                result = response.json()
                msg_type = message_data.get('msg_type', 0)
                log_info(0, f"多类型用户消息发送成功 (类型: {msg_type})", "QQ_SEND_USER_TYPE_SUCCESS",
                         message_type=msg_type)
                return True
            else:
                error_text = response.text
                log_error(0, f"多类型用户消息发送失败: HTTP {response.status_code}", "QQ_SEND_USER_TYPE_FAILED",
                          error=error_text)
                return False

        except Exception as e:
            log_error(0, f"发送多类型用户消息异常: {e}", "QQ_SEND_USER_TYPE_EXCEPTION", error=str(e))
            return False

    def send_group_message(self, group_openid: str, content: str, msg_id: str = None) -> bool:
        """发送群聊消息 - 按照官方文档实现"""
        try:
            if not self.ensure_authenticated():
                return False

            log_info(0, f"正在发送群聊消息到群组 {group_openid}", "QQ_SEND_GROUP_START",
                     group_openid=group_openid, content_length=len(content))

            # 按照官方文档的鉴权格式
            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 按照官方文档的消息格式
            message_data = {
                "content": content,
                "msg_type": 0,  # 0 文本消息
                "msg_seq": self._generate_msgseq(msg_id)  # 基于msg_id生成序列号
            }

            # 如果是回复消息，添加msg_id
            if msg_id:
                message_data["msg_id"] = msg_id

            url = self.send_group_message_url.format(group_openid)

            response = self.session.post(
                url,
                json=message_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                log_info(0, "群聊消息发送成功", "QQ_SEND_GROUP_SUCCESS",
                         group_openid=group_openid, message_id=result.get("id"))
                return True
            else:
                error_text = response.text
                log_error(0, f"发送群聊消息失败: HTTP {response.status_code}", "QQ_SEND_GROUP_FAILED",
                          group_openid=group_openid, status=response.status_code, error=error_text)
                return False

        except Exception as e:
            log_error(0, f"发送群聊消息异常: {e}", "QQ_SEND_GROUP_EXCEPTION",
                      group_openid=group_openid, error=str(e))
            return False

    def send_group_message_with_type(self, group_openid: str, message_data: dict, msg_id: str = None,
                                     original_msg_id: str = None) -> bool:
        """发送多类型群聊消息"""
        try:
            if not self.ensure_authenticated():
                return False

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            payload = message_data.copy()
            # 确保每条消息都有唯一的msg_seq（QQ官方使用msg_seq而不是msgseq）
            if "msg_seq" not in payload:
                payload["msg_seq"] = self._generate_msgseq(original_msg_id)
            if msg_id:
                payload["msg_id"] = msg_id

            url = self.send_group_message_url.format(group_openid)

            response = self.session.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                msg_type = message_data.get('msg_type', 0)
                log_info(0, f"多类型群聊消息发送成功 (类型: {msg_type})", "QQ_SEND_GROUP_TYPE_SUCCESS",
                         message_type=msg_type)
                return True
            else:
                error_text = response.text
                log_error(0, f"多类型群聊消息发送失败: HTTP {response.status_code}", "QQ_SEND_GROUP_TYPE_FAILED",
                          error=error_text)
                return False

        except Exception as e:
            log_error(0, f"发送多类型群聊消息异常: {e}", "QQ_SEND_GROUP_TYPE_EXCEPTION", error=str(e))
            return False

    def recall_message(self, message_id: str) -> bool:
        """撤回消息 - QQ官方API"""
        try:
            if not self.ensure_authenticated():
                return False

            # 使用消息ID构建撤回URL
            url = f"https://api.sgroup.qq.com/v2/messages/{message_id}"

            headers = {
                'Authorization': f'QQBot {self.access_token}',
                'Content-Type': 'application/json',
                'X-Union-Appid': self.app_id
            }

            response = self.session.delete(url, headers=headers, timeout=10)

            if response.status_code == 200:
                log_info(0, f"消息撤回成功", "QQ_RECALL_SUCCESS", message_id=message_id)
                return True
            else:
                log_error(0, f"消息撤回失败: {response.status_code}", "QQ_RECALL_FAILED",
                          message_id=message_id, status_code=response.status_code,
                          response_text=response.text)
                return False

        except Exception as e:
            log_error(0, f"撤回消息异常: {e}", "QQ_RECALL_EXCEPTION",
                      message_id=message_id, error=str(e))
            return False

    def upload_media(self, file_type: int, url: str, target_type: str, target_id: str,
                     srv_send_msg: bool = False, file_data: str = None) -> Optional[Dict]:
        """
        上传富媒体文件

        Args:
            file_type: 媒体类型 (1=图片, 2=视频, 3=语音, 4=文件)
            url: 媒体资源的URL（当使用URL上传时）
            target_type: 目标类型 ("group" 或 "user")
            target_id: 目标ID (group_openid 或 user_openid)
            srv_send_msg: 是否直接发送消息到目标端
            file_data: base64编码的文件数据（当直接上传文件时）

        Returns:
            dict: 包含file_info等信息的响应，失败返回None
        """
        try:
            if not self.ensure_authenticated():
                return None

            log_info(0, f"正在上传富媒体文件 (类型: {file_type}, 目标: {target_type})", "QQ_UPLOAD_MEDIA_START",
                     file_type=file_type, url=url, target_type=target_type)

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 按照官方文档的请求格式
            upload_data = {
                "file_type": file_type,
                "srv_send_msg": srv_send_msg
            }

            # 如果有file_data使用base64上传，否则使用URL
            if file_data:
                upload_data["file_data"] = file_data
            else:
                upload_data["url"] = url

            # 根据目标类型选择正确的API端点
            if target_type == "group":
                upload_url = self.upload_group_media_url.format(target_id)
            elif target_type == "user":
                upload_url = self.upload_user_media_url.format(target_id)
            else:
                log_error(0, f"不支持的目标类型: {target_type}", "QQ_UPLOAD_MEDIA_INVALID_TARGET")
                return None

            response = self.session.post(
                upload_url,
                json=upload_data,
                headers=headers,
                timeout=30  # 上传可能需要更长时间
            )

            if response.status_code == 200:
                result = response.json()
                log_info(0, "富媒体文件上传成功", "QQ_UPLOAD_MEDIA_SUCCESS",
                         file_uuid=result.get("file_uuid"),
                         ttl=result.get("ttl"))
                return result
            else:
                error_text = response.text
                log_error(0, f"富媒体文件上传失败: HTTP {response.status_code}", "QQ_UPLOAD_MEDIA_FAILED",
                          status=response.status_code, error=error_text)
                return None

        except Exception as e:
            log_error(0, f"上传富媒体文件异常: {e}", "QQ_UPLOAD_MEDIA_EXCEPTION", error=str(e))
            return None

    def test_connection(self) -> bool:
        """测试连接 - 包含认证和获取机器人信息"""
        try:
            log_info(0, "正在测试QQ API连接...", "QQ_CONNECTION_TEST")

            # 测试认证
            if self.authenticate():
                # 测试获取机器人信息
                bot_info = self.get_bot_info()
                if bot_info:
                    log_info(0, "QQ API连接测试成功", "QQ_CONNECTION_TEST_SUCCESS",
                             qq_bot_id=bot_info.get("id"), username=bot_info.get("username"))
                    return True
                else:
                    # 获取机器人信息失败，错误信息已经在get_bot_info中设置
                    log_error(0, f"获取机器人信息失败: {self.last_error_message or '未知错误'}", "QQ_BOT_INFO_FAILED")
                    return False
            else:
                # 认证失败，错误信息已经在authenticate中设置
                log_error(0, f"QQ API认证失败: {self.last_error_message or '未知错误'}", "QQ_CONNECTION_TEST_FAILED")
                return False

        except Exception as e:
            self.last_error_message = str(e)
            log_error(0, f"QQ API连接测试异常: {e}", "QQ_CONNECTION_TEST_EXCEPTION", error=str(e))
            return False

    def send_channel_message(self, channel_id: str, content: str, msg_id: str = None) -> bool:
        """发送频道消息 - 按照官方文档实现"""
        try:
            if not self.ensure_authenticated():
                return False

            log_info(0, f"正在发送频道消息到频道 {channel_id}", "QQ_SEND_CHANNEL_START",
                     channel_id=channel_id, content_length=len(content))

            # 按照官方文档的鉴权格式
            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 按照官方文档的消息格式
            message_data = {
                "content": content,
                "msg_type": 0,  # 0 文本消息
                "msg_seq": self._generate_msgseq(msg_id)  # 基于msg_id生成序列号
            }

            # 如果是回复消息，添加msg_id
            if msg_id:
                message_data["msg_id"] = msg_id

            url = self.send_channel_message_url.format(channel_id)

            response = self.session.post(
                url,
                json=message_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                log_info(0, f"频道消息发送成功", "QQ_SEND_CHANNEL_SUCCESS",
                         channel_id=channel_id, message_id=result.get('id'))
                return True
            else:
                error_msg = f"频道消息发送失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"

                log_error(0, error_msg, "QQ_SEND_CHANNEL_HTTP_ERROR",
                          status_code=response.status_code, channel_id=channel_id)
                return False

        except Exception as e:
            log_error(0, f"发送频道消息异常: {e}", "QQ_SEND_CHANNEL_ERROR", error=str(e))
            return False

    def send_channel_message_with_type(self, channel_id: str, message_data: dict, msg_id: str = None,
                                       original_msg_id: str = None) -> bool:
        """发送多类型频道消息"""
        try:
            if not self.ensure_authenticated():
                return False

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 使用传入的完整消息数据
            payload = message_data.copy()
            # 确保每条消息都有唯一的msg_seq
            if "msg_seq" not in payload:
                payload["msg_seq"] = self._generate_msgseq(original_msg_id)
            if msg_id:
                payload["msg_id"] = msg_id

            url = self.send_channel_message_url.format(channel_id)

            response = self.session.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                msg_type = message_data.get('msg_type', 0)
                log_info(0, f"频道消息发送成功 (类型: {msg_type})", "QQ_SEND_CHANNEL_TYPE_SUCCESS",
                         channel_id=channel_id, msg_type=msg_type)
                return True
            else:
                log_error(0, f"频道消息发送失败: {response.status_code}", "QQ_SEND_CHANNEL_TYPE_ERROR",
                          channel_id=channel_id, status_code=response.status_code)
                return False

        except Exception as e:
            log_error(0, f"发送频道消息异常: {e}", "QQ_SEND_CHANNEL_TYPE_EXCEPTION", error=str(e))
            return False

    def send_dm_message(self, guild_id: str, content: str, msg_id: str = None) -> bool:
        """发送频道私信消息 - 按照官方文档实现"""
        try:
            if not self.ensure_authenticated():
                return False

            log_info(0, f"正在发送频道私信到频道 {guild_id}", "QQ_SEND_DM_START",
                     guild_id=guild_id, content_length=len(content))

            # 按照官方文档的鉴权格式
            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 按照官方文档的消息格式
            message_data = {
                "content": content,
                "msg_type": 0,  # 0 文本消息
                "msg_seq": self._generate_msgseq(msg_id)  # 基于msg_id生成序列号
            }

            # 如果是回复消息，添加msg_id
            if msg_id:
                message_data["msg_id"] = msg_id

            url = self.send_dm_message_url.format(guild_id)

            response = self.session.post(
                url,
                json=message_data,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                log_info(0, f"频道私信发送成功", "QQ_SEND_DM_SUCCESS",
                         guild_id=guild_id, message_id=result.get('id'))
                return True
            else:
                error_msg = f"频道私信发送失败: HTTP {response.status_code}"
                try:
                    error_detail = response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {response.text}"

                log_error(0, error_msg, "QQ_SEND_DM_HTTP_ERROR",
                          status_code=response.status_code, guild_id=guild_id)
                return False

        except Exception as e:
            log_error(0, f"发送频道私信异常: {e}", "QQ_SEND_DM_ERROR", error=str(e))
            return False

    def send_dm_message_with_type(self, guild_id: str, message_data: dict, msg_id: str = None,
                                  original_msg_id: str = None) -> bool:
        """发送多类型频道私信消息"""
        try:
            if not self.ensure_authenticated():
                return False

            headers = {
                "Authorization": f"QQBot {self.access_token}",
                "Content-Type": "application/json"
            }

            # 使用传入的完整消息数据
            payload = message_data.copy()
            # 确保每条消息都有唯一的msg_seq
            if "msg_seq" not in payload:
                payload["msg_seq"] = self._generate_msgseq(original_msg_id)
            if msg_id:
                payload["msg_id"] = msg_id

            url = self.send_dm_message_url.format(guild_id)

            response = self.session.post(url, json=payload, headers=headers, timeout=10)

            if response.status_code == 200:
                msg_type = message_data.get('msg_type', 0)
                log_info(0, f"频道私信发送成功 (类型: {msg_type})", "QQ_SEND_DM_TYPE_SUCCESS",
                         guild_id=guild_id, msg_type=msg_type)
                return True
            else:
                log_error(0, f"频道私信发送失败: {response.status_code}", "QQ_SEND_DM_TYPE_ERROR",
                          guild_id=guild_id, status_code=response.status_code)
                return False

        except Exception as e:
            log_error(0, f"发送频道私信异常: {e}", "QQ_SEND_DM_TYPE_EXCEPTION", error=str(e))
            return False
