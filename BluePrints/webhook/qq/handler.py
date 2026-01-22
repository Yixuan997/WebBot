"""
QQ协议Webhook处理器
实现QQ官方机器人的Webhook处理逻辑
"""

import json
from datetime import datetime

from Core.logging.file_logger import log_info, log_error, log_debug, log_warn
from Database.Redis.client import set_value, get_value
from .events import QQEventProcessor
from ..base import BaseWebhookHandler


class QQWebhookHandler(BaseWebhookHandler):
    """QQ协议Webhook处理器"""

    def __init__(self):
        super().__init__("QQ")
        self.event_processor = QQEventProcessor()  # 初始化事件处理器

    def validate_request(self, raw_data: bytes, headers: dict) -> tuple[bool, str]:
        """验证QQ Webhook请求"""
        # 检查必需的请求头
        app_id = headers.get('X-Bot-Appid')
        if not app_id:
            return False, "Missing X-Bot-Appid header"

        # 验证User-Agent
        user_agent = headers.get('User-Agent', '')
        if not user_agent.startswith('QQBot-Callback'):
            log_warn(0, f"可疑的User-Agent: {user_agent}", "QQ_WEBHOOK_SUSPICIOUS_UA")

        return True, ""

    def _get_event_redis_key(self, event_id: str) -> str:
        """获取事件Redis键名"""
        today = datetime.now().strftime("%Y%m%d")
        return f"qq_event_dedup:{today}:{event_id}"

    def _is_duplicate_event(self, event_id: str) -> bool:
        """检查是否为重复事件 - 使用Redis存储"""
        try:
            redis_key = self._get_event_redis_key(event_id)
            return get_value(redis_key) is not None
        except Exception as e:
            log_error(0, f"检查重复事件失败: {e}", "QQ_EVENT_DUPLICATE_CHECK_ERROR")
            return False

    def _record_event(self, event_id: str):
        """记录事件ID - 使用Redis存储，24小时自动过期"""
        try:
            redis_key = self._get_event_redis_key(event_id)
            # 设置24小时过期，自动清理旧记录
            set_value(redis_key, "true", expire_seconds=86400)
        except Exception as e:
            log_error(0, f"记录事件ID失败: {e}", "QQ_EVENT_RECORD_ERROR")

    def parse_event(self, raw_data: bytes) -> dict:
        """解析QQ事件数据"""
        try:
            return json.loads(raw_data.decode('utf-8'))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON data: {e}")

    def get_bot_identifier(self, headers: dict, event_data: dict) -> str:
        """获取QQ机器人的AppID"""
        return headers.get('X-Bot-Appid')

    def verify_signature(self, raw_data: bytes, headers: dict, secret: str) -> bool:
        """验证QQ Webhook签名"""
        try:
            # 检查是否是验证请求
            try:
                import json
                event_data = json.loads(raw_data.decode('utf-8'))
                op_code = event_data.get('op')

                if op_code == 13:  # 回调验证请求
                    log_info(0, "QQ回调验证请求", "QQ_WEBHOOK_VERIFICATION")
            except Exception as e:
                log_warn(0, f"解析事件数据失败: {e}", "QQ_WEBHOOK_EVENT_PARSE_ERROR")

            # 获取签名相关头部
            signature = headers.get('X-Signature-Ed25519')
            timestamp = headers.get('X-Signature-Timestamp')

            if not signature or not timestamp:
                log_error(0, "缺少QQ签名头部", "QQ_WEBHOOK_MISSING_SIGNATURE")
                return False

            # 使用PyNaCl进行Ed25519签名验证
            result = self._verify_ed25519_simple(raw_data, signature, timestamp, secret)

            if not result:
                log_error(0, "QQ签名验证失败", "QQ_WEBHOOK_SIGNATURE_FAILED")

            return result

        except Exception as e:
            log_error(0, f"QQ签名验证异常: {e}", "QQ_WEBHOOK_SIGNATURE_ERROR")
            return False

    def _verify_ed25519_simple(self, raw_data: bytes, signature: str, timestamp: str, secret: str) -> bool:
        """Ed25519签名验证"""
        try:
            import nacl.signing
            import nacl.encoding

            # 1. 生成seed
            seed = secret
            while len(seed) < 32:
                seed += seed
            seed = seed[:32].encode('utf-8')

            # 2. 生成验证密钥
            verify_key = nacl.signing.SigningKey(seed).verify_key

            # 3. 解码签名
            try:
                signature_bytes = bytes.fromhex(signature)
            except Exception:
                return False

            # 4. 构建验证消息：timestamp + body
            verify_message = (timestamp + raw_data.decode('utf-8')).encode('utf-8')

            # 5. 验证签名
            try:
                verify_key.verify(verify_message, signature_bytes)
                return True
            except Exception:
                return False

        except ImportError:
            log_error(0, "缺少PyNaCl库", "QQ_WEBHOOK_MISSING_NACL")
            return False
        except Exception:
            return False

    def generate_verification_signature(self, event_ts: str, plain_token: str) -> str:
        """生成回调验证的signature"""
        try:
            import nacl.signing

            # 获取机器人的secret
            from flask import request
            app_id = request.headers.get('X-Bot-Appid')

            if not app_id:
                log_error(0, "无法获取AppID", "QQ_WEBHOOK_VERIFICATION_NO_APPID")
                return None

            # 从数据库获取机器人配置
            try:
                from app import app as flask_app
                with flask_app.app_context():
                    from Models import Bot
                    # 查询QQ协议的机器人
                    bots = Bot.query.filter_by(protocol='qq').all()
                    secret = None
                    for bot in bots:
                        bot_config = bot.get_config()
                        if bot_config.get('app_id') == app_id:
                            secret = bot_config.get('app_secret')
                            break

                    if not secret:
                        log_error(0, f"未找到机器人: {app_id}", "QQ_WEBHOOK_BOT_NOT_FOUND")
                        return None
            except Exception as e:
                log_error(0, "数据库查询失败", "QQ_WEBHOOK_DB_ERROR")
                return None

            # 生成seed
            seed = secret
            while len(seed) < 32:
                seed += seed
            seed = seed[:32].encode('utf-8')

            # 生成签名
            signing_key = nacl.signing.SigningKey(seed)
            message = (event_ts + plain_token).encode('utf-8')
            signature_bytes = signing_key.sign(message).signature

            return signature_bytes.hex()

        except Exception as e:
            log_error(0, f"生成signature失败: {e}", "QQ_WEBHOOK_VERIFICATION_SIGNATURE_ERROR")
            return None

    def find_bot_by_identifier(self, identifier: str, bot_manager) -> int:
        """根据AppID查找QQ机器人ID"""
        try:
            # 优先使用缓存查找 (O(1)性能)
            from Core.bot.cache import bot_cache_manager

            bot_id = bot_cache_manager.get_bot_by_app_id(identifier)
            if bot_id:
                log_debug(0, f"✅ 缓存命中找到机器人", "QQ_WEBHOOK_BOT_FOUND_CACHE",
                          found_bot_id=bot_id, app_id=identifier)
                return bot_id

            # 缓存未命中，回退到数据库查找
            log_debug(0, f"缓存未命中，从数据库查找", "QQ_WEBHOOK_CACHE_MISS", app_id=identifier)

            bot_id = self._find_bot_from_database(identifier)
            if bot_id:
                # 找到后更新缓存 (为下次查找做准备)
                try:
                    # 获取机器人配置但不记录日志 (避免重复日志)
                    bot_config = bot_manager._get_bot_config(bot_id, log_success=False)
                    if bot_config:
                        bot_cache_manager.update_bot_mapping(bot_id, identifier, 'running')
                        bot_cache_manager.update_bot_config_cache(bot_id, bot_config)
                        log_debug(0, f"已更新缓存映射", "QQ_WEBHOOK_CACHE_UPDATE",
                                  bot_id=bot_id, app_id=identifier)
                except Exception as cache_error:
                    log_warn(0, f"更新缓存失败: {cache_error}", "QQ_WEBHOOK_CACHE_UPDATE_ERROR")

                return bot_id

            # 完全未找到
            log_error(0, f"❌ 未找到AppID为 {identifier} 的机器人", "QQ_WEBHOOK_BOT_NOT_FOUND")
            return None

        except Exception as e:
            log_error(0, f"根据AppID查找QQ机器人异常: {e}", "QQ_WEBHOOK_FIND_BOT_ERROR", error=str(e))
            import traceback
            log_error(0, f"查找机器人异常堆栈", "QQ_WEBHOOK_FIND_BOT_TRACEBACK",
                      traceback=traceback.format_exc())
            return None

    def _find_bot_from_database(self, app_id: str) -> int:
        """直接从数据库查找机器人"""
        try:
            # 使用Flask的current_app，避免延迟导入
            from flask import current_app

            with current_app.app_context():
                from Models import Bot

                # 查找匹配的机器人 - 遍历QQ协议的机器人
                bots = Bot.query.filter_by(protocol='qq').all()
                for bot in bots:
                    bot_config = bot.get_config()
                    if bot_config.get('app_id') == app_id:
                        log_info(0, "从数据库找到机器人", "QQ_WEBHOOK_BOT_FOUND_DB",
                                 found_bot_id=bot.id, app_id=app_id, name=bot.name)
                        return bot.id

                log_error(0, f"数据库中未找到AppID为 {app_id} 的机器人", "QQ_WEBHOOK_BOT_NOT_FOUND_DB")
                return None

        except Exception as e:
            log_error(0, f"从数据库查找机器人异常: {e}", "QQ_WEBHOOK_FIND_BOT_DB_ERROR", error=str(e))
            return None

    def get_bot_secret(self, bot_id: int, bot_manager) -> str:
        """获取QQ机器人的AppSecret"""
        try:
            bot_config = bot_manager._get_bot_config(bot_id)
            return bot_config.get('app_secret') if bot_config else None
        except Exception as e:
            log_error(0, f"获取QQ机器人AppSecret异常: {e}", "QQ_WEBHOOK_GET_SECRET_ERROR")
            return None

    def handle_event(self, bot_id: int, event_data: dict, bot_manager) -> dict:
        """
        处理QQ事件数据 - 路由到事件处理器
        """
        try:
            # 1. 提取事件信息
            event_type = event_data.get('t')  # 事件类型
            event_payload = event_data.get('d')  # 事件数据
            op_code = event_data.get('op', 0)  # 操作码

            # 直接使用QQ提供的事件ID
            unique_event_id = event_data.get('id')

            # 2. 事件去重检查
            if unique_event_id and self._is_duplicate_event(unique_event_id):
                log_info(bot_id, f"🔄 重复事件: {unique_event_id}", "QQ_DUPLICATE_EVENT", event_id=unique_event_id)
                return {"status": "duplicate", "message": "Event already processed"}

            # 立即记录事件ID
            if unique_event_id:
                self._record_event(unique_event_id)
                log_debug(bot_id, f"📝 事件ID已记录: {unique_event_id}", "QQ_EVENT_RECORDED_EARLY",
                          event_id=unique_event_id)

            # 提取时间戳信息
            timestamp = event_payload.get('timestamp') if event_payload else None

            log_info(bot_id, f"📨 收到QQ事件: {event_type}", "QQ_WEBHOOK_EVENT_HANDLE",
                     qq_event_type=event_type,
                     op_code=op_code,
                     timestamp=timestamp,
                     event_id=unique_event_id,
                     payload_keys=list(event_payload.keys()) if event_payload else [])

            log_debug(bot_id, f"事件详细信息", "QQ_EVENT_DEBUG",
                      qq_event_type=event_type, op_code=op_code,
                      payload_size=len(str(event_payload)) if event_payload else 0,
                      has_bot_manager=bot_manager is not None)

            # 处理回调地址验证（这个逻辑已经在基类中优先处理了，这里不应该再执行到）
            if op_code == 13:  # 回调地址验证
                log_warn(bot_id, "回调验证请求到达了QQ处理器，应该在基类中处理", "QQ_WEBHOOK_VERIFICATION_UNEXPECTED")
                return self.event_processor.handle_callback_verification(bot_id, event_payload)

            # 路由事件到事件处理器并处理结果
            result = None

            # 消息事件
            if event_type == 'GROUP_AT_MESSAGE_CREATE':  # 群聊@消息
                result = self.event_processor.handle_group_at_message(bot_id, event_payload, bot_manager)
            elif event_type == 'C2C_MESSAGE_CREATE':  # 单聊消息
                result = self.event_processor.handle_c2c_message(bot_id, event_payload, bot_manager)
            elif event_type == 'MESSAGE_CREATE':  # 频道消息
                result = self.event_processor.handle_channel_message(bot_id, event_payload, bot_manager)
            elif event_type == 'AT_MESSAGE_CREATE':  # 公域频道@消息
                result = self.event_processor.handle_at_message(bot_id, event_payload, bot_manager)
            elif event_type == 'DIRECT_MESSAGE_CREATE':  # 私信消息
                result = self.event_processor.handle_direct_message(bot_id, event_payload, bot_manager)

            # 频道管理事件
            elif event_type in ['GUILD_CREATE', 'GUILD_UPDATE', 'GUILD_DELETE']:
                result = self.event_processor.handle_guild_event(bot_id, event_type, event_payload, bot_manager)
            elif event_type in ['CHANNEL_CREATE', 'CHANNEL_UPDATE', 'CHANNEL_DELETE']:
                result = self.event_processor.handle_channel_event(bot_id, event_type, event_payload, bot_manager)

            # 成员管理事件
            elif event_type in ['GUILD_MEMBER_ADD', 'GUILD_MEMBER_UPDATE', 'GUILD_MEMBER_REMOVE']:
                result = self.event_processor.handle_member_event(bot_id, event_type, event_payload, bot_manager)

            # 好友和群聊管理事件
            elif event_type in ['FRIEND_ADD', 'FRIEND_DEL']:
                result = self.event_processor.handle_friend_event(bot_id, event_type, event_payload, bot_manager)
            elif event_type in ['GROUP_ADD_ROBOT', 'GROUP_DEL_ROBOT']:
                result = self.event_processor.handle_group_robot_event(bot_id, event_type, event_payload, bot_manager)

            # 消息推送开关事件
            elif event_type in ['C2C_MSG_REJECT', 'C2C_MSG_RECEIVE', 'GROUP_MSG_REJECT', 'GROUP_MSG_RECEIVE']:
                result = self.event_processor.handle_message_setting_event(bot_id, event_type, event_payload,
                                                                           bot_manager)

            # 其他事件
            elif event_type == 'INTERACTION_CREATE':  # 互动事件
                result = self.event_processor.handle_interaction_event(bot_id, event_payload, bot_manager)
            elif event_type in ['MESSAGE_AUDIT_PASS', 'MESSAGE_AUDIT_REJECT']:  # 消息审核事件
                result = self.event_processor.handle_audit_event(bot_id, event_type, event_payload, bot_manager)

            else:
                log_info(bot_id, f"未处理的QQ事件类型: {event_type}", "QQ_WEBHOOK_UNHANDLED_EVENT")
                result = {"status": "ignored", "message": f"Unhandled event type: {event_type}"}

            # 移除原有的延迟记录逻辑，因为已经在前面立即记录了
            log_debug(bot_id, f"✅ 事件处理完成: {event_type}", "QQ_EVENT_PROCESSED",
                      event_id=unique_event_id, result_status=result.get("status") if result else "none")

            return result

        except Exception as e:
            log_error(bot_id, f"处理QQ事件异常: {e}", "QQ_WEBHOOK_EVENT_ERROR", error=str(e))
            return {"status": "error", "message": str(e)}
