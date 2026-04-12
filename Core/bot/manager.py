import time

from Adapters import get_adapter_manager
from Core.bot.cache import bot_cache_manager
from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from Core.message.handler import MessageHandler


class BotManager:
    """机器人管理器"""

    def __init__(self):
        self.bots = {}  # 存储机器人实例
        self.message_handler = MessageHandler()  # 使用工作流引擎
        self.running_bots = set()
        self._shutdown_event = None
        self._monitor_thread = None
        self._app = None

        self._start_status_monitoring()

    def start_bot(self, bot_id):
        """启动机器人 - Webhook模式下表示启用消息处理"""
        try:
            if bot_id in self.running_bots:
                log_info(bot_id, "机器人已在本进程中运行，跳过启动", "BOT_ALREADY_RUNNING_LOCAL")
                return {"success": False, "message": "机器人已在运行"}

            bot_config = self._get_bot_config(bot_id)
            if not bot_config:
                return {"success": False, "message": "机器人配置不存在"}
            protocol = bot_config.get('protocol')
            if not protocol:
                return {"success": False, "message": "机器人配置缺少协议类型"}

            adapter_manager = get_adapter_manager()
            adapter_class = adapter_manager.get_adapter_class(protocol)
            if not adapter_class:
                return {"success": False, "message": f"不支持的协议类型: {protocol}"}

            config_ok, config_error = adapter_class.validate_bot_config(bot_config)
            if not config_ok:
                return {"success": False, "message": config_error}

            log_info(bot_id, f"开始启动机器人: {bot_config['name']}", "BOT_START_BEGIN")
            from flask import current_app
            try:
                app = current_app._get_current_object()
            except RuntimeError:
                # 如果无法获取当前应用，导入应用实例
                from app import app

            with app.app_context():
                success, error_message = adapter_manager.start_adapter(
                    bot_id=bot_id,
                    protocol=protocol,
                    config=bot_config,
                    message_handler=self._handle_webhook_message
                )

            log_info(bot_id, f"适配器启动结果: success={success}, error_message='{error_message}'",
                     "ADAPTER_START_RESULT")

            if success:
                adapter_manager = get_adapter_manager()
                adapter_status = adapter_manager.get_adapter_status(bot_id)
                if adapter_status:
                    self.running_bots.add(bot_id)
                    self.bots[bot_id] = {
                        'config': bot_config,
                        'adapter_status': adapter_status,
                        'start_time': time.time(),
                        'status': 'webhook_ready',
                        'connection_status': 'webhook_listening',
                        'last_heartbeat': time.time()
                    }

                self._update_bot_status_in_db(bot_id, 'running')
                self._update_bot_cache(bot_id, bot_config, 'running')

                log_info(bot_id, f" 机器人 {bot_config['name']} 已启用消息处理", "BOT_WEBHOOK_ENABLED",
                         protocol=protocol, config_info=self._get_log_safe_config(bot_config, protocol))

                return {"success": True, "message": "机器人已启用，可接收Webhook消息"}
            else:
                if not error_message or error_message.strip() == "":
                    error_message = adapter_class.get_startup_error_hint()

                return {"success": False, "message": error_message}

        except Exception as e:
            log_error(bot_id if 'bot_id' in locals() else 0, f"启用机器人失败: {e}", "BOT_START_ERROR", error=str(e))
            return {"success": False, "message": f"启用失败: {e}"}

    async def _handle_webhook_message(self, event):
        """处理Webhook消息"""
        try:
            bot_id = event.bot.adapter.bot_id if hasattr(event, 'bot') else 0
            # 直接调用异步处理方法
            await self.message_handler._async_process_message(event, bot_id)
        except Exception as e:
            log_error(bot_id, f"处理Webhook消息异常: {e}", "WEBHOOK_MESSAGE_ERROR", error=str(e))

    def _send_response(self, bot_id, target, response, reply_to_msg_id=None, original_msg_id=None):
        """发送响应"""
        try:
            log_debug(bot_id, f"准备发送响应", "SEND_RESPONSE_START",
                      target=target,
                      response_type=type(response).__name__,
                      has_reply_id=reply_to_msg_id is not None,
                      has_original_id=original_msg_id is not None)
            if not isinstance(response, dict):
                log_error(bot_id, f"无效的响应格式: {type(response)}", "INVALID_RESPONSE_FORMAT")
                return False
            if 'msg_type' not in response:
                log_error(bot_id, f"消息对象缺少msg_type字段", "MISSING_MSG_TYPE")
                return False

            adapter_manager = get_adapter_manager()
            log_debug(bot_id, f"获取适配器管理器", "ADAPTER_MANAGER_GET",
                      adapter_manager_type=type(adapter_manager).__name__)
            adapter_status = adapter_manager.get_adapter_status(bot_id)
            if not adapter_status:
                log_error(bot_id, f"机器人在适配器中不存在", "BOT_NOT_IN_ADAPTER")
                return False

            log_debug(bot_id, f"适配器状态检查通过", "ADAPTER_STATUS_OK",
                      running=adapter_status.get('running', False),
                      protocol=adapter_status.get('protocol'))
            result = adapter_manager.send_message(bot_id, target, response,
                                                  reply_to_msg_id=reply_to_msg_id,
                                                  original_msg_id=original_msg_id)

            log_debug(bot_id, f"适配器发送结果: {result}", "ADAPTER_SEND_RESULT")
            return result

        except Exception as e:
            log_error(bot_id, f"发送响应异常: {e}", "SEND_RESPONSE_ERROR", error=str(e))
            import traceback
            log_error(bot_id, f"发送响应异常堆栈", "SEND_RESPONSE_TRACEBACK",
                      traceback=traceback.format_exc())
            return False

    def _build_target_from_message(self, message_data):
        """从消息数据构建目标字符串"""
        try:
            msg_type = message_data.get('type')
            if msg_type == 'group_at':
                target = f"group:{message_data.get('group_openid')}"
            elif msg_type == 'c2c':
                target = f"user:{message_data.get('openid') or message_data.get('author', {}).get('user_openid')}"
            elif msg_type == 'channel':
                target = f"channel:{message_data.get('channel_id')}"
            elif msg_type == 'at_message':
                target = f"channel:{message_data.get('channel_id')}"
            elif msg_type == 'direct_message':
                target = f"dm:{message_data.get('guild_id')}"
            else:
                log_error(0, f"未知的消息类型: {msg_type}", "BUILD_TARGET_UNKNOWN_TYPE", msg_type=msg_type)
                return None
            return target

        except Exception as e:
            log_error(0, f"构建目标字符串失败: {e}", "BUILD_TARGET_ERROR", error=str(e))
            return None

    def stop_bot(self, bot_id):
        """停止机器人"""
        try:
            if not self._is_bot_running_in_db(bot_id):
                return {"success": False, "message": "机器人未在运行"}

            adapter_manager = get_adapter_manager()
            success = adapter_manager.stop_adapter(bot_id)

            if success:
                self.running_bots.discard(bot_id)
                if bot_id in self.bots:
                    self.bots[bot_id]['status'] = 'stopped'
                    self.bots[bot_id]['stop_time'] = time.time()
                    self.bots[bot_id]['connection_status'] = 'webhook_disabled'

                self._update_bot_status_in_db(bot_id, 'stopped')
                self._update_bot_cache_status(bot_id, 'stopped')

                log_info(bot_id, f" 机器人已禁用消息处理", "BOT_WEBHOOK_DISABLED")

                return {"success": True, "message": "机器人已禁用，不再处理Webhook消息"}
            else:
                return {"success": False, "message": "禁用机器人失败"}

        except Exception as e:
            log_error(bot_id, f"禁用机器人失败: {e}", "BOT_STOP_ERROR", error=str(e))
            return {"success": False, "message": f"禁用失败: {e}"}

    def restart_bot(self, bot_id):
        """重启机器人"""
        stop_result = self.stop_bot(bot_id)
        if stop_result["success"]:
            time.sleep(1)  # 等待1秒
            return self.start_bot(bot_id)
        return stop_result

    def get_bot_status(self, bot_id):
        """获取机器人状态 - 从适配器获取"""
        # 首先从适配器获取状态
        # 确保在Flask应用上下文中运行
        adapter_manager = get_adapter_manager()
        adapter_status = adapter_manager.get_adapter_status(bot_id)

        if adapter_status:
            # 合并本地状态和适配器状态
            local_info = self.bots.get(bot_id, {})

            # 计算运行时长
            start_time = local_info.get('start_time')
            if start_time:
                uptime_seconds = int(time.time() - start_time)
                if uptime_seconds < 60:
                    uptime = f"{uptime_seconds}秒"
                elif uptime_seconds < 3600:
                    uptime = f"{uptime_seconds // 60}分钟"
                elif uptime_seconds < 86400:
                    hours = uptime_seconds // 3600
                    minutes = (uptime_seconds % 3600) // 60
                    uptime = f"{hours}小时{minutes}分钟"
                else:
                    days = uptime_seconds // 86400
                    hours = (uptime_seconds % 86400) // 3600
                    uptime = f"{days}天{hours}小时"
            else:
                uptime = adapter_status.get('uptime', '0秒')

            status = {
                'is_running': adapter_status.get('running', False),
                'protocol': adapter_status.get('protocol', ''),
                'bot_name': adapter_status.get('bot_name', '未知'),
                'app_id': adapter_status.get('app_id', ''),
                'message_count': adapter_status.get('message_count', 0),
                'error_count': adapter_status.get('error_count', 0),
                'connection_status': adapter_status.get('connection_status', 'disconnected'),
                'uptime': uptime,

                # 添加本地管理的信息
                'config': local_info.get('config', {}),
                'start_time': start_time,
                'last_heartbeat': local_info.get('last_heartbeat'),

                # 添加统计信息
                'avg_response_time': 0,  # 适配器暂不提供此信息
                'response_count': 0
            }

            return status

        # 如果适配器中没有，检查本地状态
        elif bot_id in self.bots:
            bot_info = self.bots[bot_id].copy()
            bot_info['is_running'] = bot_id in self.running_bots
            bot_info['uptime'] = "0秒"
            return bot_info

        return None

    def list_running_bots(self):
        """列出正在运行的机器人 - 多进程安全版本"""
        # 从数据库获取全局运行状态
        try:
            from Models import Bot, db
            from flask import current_app

            with current_app.app_context():
                running_bots_in_db = Bot.query.filter_by(is_running=True).all()
                global_running_bots = [bot.id for bot in running_bots_in_db]

                # 合并本地状态和数据库状态
                # 优先使用数据库状态作为权威来源
                return global_running_bots

        except Exception as e:
            log_warn(0, f"获取全局运行状态失败，使用本地状态: {e}", "GLOBAL_STATUS_FALLBACK")
            # 如果数据库查询失败，回退到本地状态
            return list(self.running_bots)

    def _get_log_safe_config(self, config, protocol):
        """获取日志安全的配置信息（隐藏敏感信息）"""
        adapter_manager = get_adapter_manager()
        adapter_class = adapter_manager.get_adapter_class(protocol)
        if not adapter_class:
            return "unknown protocol"
        return adapter_class.get_config_summary(config or {})

    def _get_bot_config(self, bot_id, log_success=True):
        """获取机器人配置 - 支持控制日志记录"""
        try:
            # 优先从缓存获取配置
            cached_config = bot_cache_manager.get_bot_config_cached(bot_id)
            if cached_config:
                return cached_config

            # 缓存未命中，从数据库获取
            try:
                from Models import Bot, db
                from flask import current_app

                with current_app.app_context():
                    bot = Bot.query.get(bot_id)
                    if bot:
                        # 获取协议和配置
                        protocol = getattr(bot, 'protocol', None) or ""
                        bot_config_data = bot.get_config()  # 使用辅助方法获取配置

                        # 构建config字典，合并协议特定配置
                        config = {
                            'id': bot.id,
                            'name': bot.name,
                            'protocol': protocol,
                            'description': getattr(bot, 'description', ''),
                            'status': 'running' if getattr(bot, 'is_running', False) else 'inactive',
                            'created_at': getattr(bot, 'created_at', None),
                            'updated_at': getattr(bot, 'updated_at', None),
                            # 合并协议特定配置
                            **bot_config_data
                        }

                        # 只在需要时记录日志 (避免Webhook查找时的重复日志)
                        if log_success:
                            log_safe_info = self._get_log_safe_config(config, protocol)
                            log_info(bot_id, f"从数据库获取配置成功", "DB_CONFIG_SUCCESS",
                                     protocol=protocol, config_info=log_safe_info)

                        # 更新配置缓存
                        bot_cache_manager.update_bot_config_cache(bot_id, config)

                        return config
                    else:
                        log_warn(bot_id, f"数据库中未找到机器人ID {bot_id}", "BOT_NOT_FOUND")
                        return None

            except Exception as db_error:
                log_error(bot_id, f"数据库获取配置失败: {db_error}", "DB_CONFIG_ERROR", error=str(db_error))
                return None

        except Exception as e:
            log_error(bot_id, f"获取机器人配置异常: {e}", "GET_CONFIG_EXCEPTION", error=str(e))
            return None

    def _is_bot_running_in_db(self, bot_id):
        """检查机器人在数据库中的运行状态 - 多进程安全"""
        try:
            from Models import Bot, db
            from flask import current_app

            with current_app.app_context():
                bot = Bot.query.get(bot_id)
                if bot:
                    # 检查数据库中的状态字段
                    return getattr(bot, 'is_running', False)
                return False
        except Exception as e:
            log_warn(bot_id, f"检查数据库运行状态失败: {e}", "DB_STATUS_CHECK_ERROR")
            return False

    def _update_bot_status_in_db(self, bot_id, status):
        """更新机器人在数据库中的状态 - 多进程安全"""
        try:
            from Models import Bot, db
            from flask import current_app

            with current_app.app_context():
                bot = Bot.query.get(bot_id)
                if bot:
                    # 更新运行状态 (Bot模型只有is_running字段，没有status字段)
                    bot.is_running = (status == 'running')
                    bot.updated_at = self._get_current_time()
                    db.session.commit()
                    log_info(bot_id, f"数据库状态已更新为: {status}", "DB_STATUS_UPDATE")
                    return True
                else:
                    log_warn(bot_id, "机器人不存在，无法更新状态", "DB_BOT_NOT_FOUND")
                    return False
        except Exception as e:
            log_error(bot_id, f"更新数据库状态失败: {e}", "DB_STATUS_UPDATE_ERROR", error=str(e))
            return False

    def _get_current_time(self):
        """获取当前时间"""
        try:
            from Models.Extensions import get_current_time
            return get_current_time()
        except ImportError:
            from datetime import datetime
            return datetime.now()

    def _update_bot_cache(self, bot_id: int, bot_config: dict, status: str):
        """更新机器人缓存 - 统一缓存管理接口"""
        try:
            protocol = bot_config.get('protocol')
            if not protocol:
                log_warn(bot_id, "机器人配置缺少协议，跳过缓存映射更新", "BOT_CACHE_PROTOCOL_MISSING")
                bot_cache_manager.update_bot_config_cache(bot_id, bot_config)
                return

            # 从适配器类获取缓存键字段名
            adapter_manager = get_adapter_manager()
            adapter_class = adapter_manager.adapters.get(protocol)

            if adapter_class:
                cache_key_field = adapter_class.get_cache_key_field()

                # 如果适配器声明了缓存键字段，更新映射
                if cache_key_field:
                    cache_key = bot_config.get(cache_key_field)
                    if cache_key:
                        bot_cache_manager.update_bot_mapping(bot_id, protocol, str(cache_key), status)
                        log_debug(bot_id, f"机器人缓存映射已更新", "BOT_CACHE_MAPPING_UPDATED",
                                  protocol=protocol, cache_key=cache_key, status=status)

            # 所有协议都更新配置缓存
            bot_cache_manager.update_bot_config_cache(bot_id, bot_config)
            log_debug(bot_id, f"机器人配置缓存已更新", "BOT_CACHE_CONFIG_UPDATED",
                      protocol=protocol, status=status)

        except Exception as e:
            # Redis不可用时不应该阻止机器人启动，只记录警告
            log_warn(bot_id, f"更新机器人缓存失败(Redis可能不可用): {e}", "BOT_CACHE_UPDATE_WARNING", error=str(e))

    def _update_bot_cache_status(self, bot_id: int, status: str):
        """仅更新机器人状态缓存"""
        try:
            bot_cache_manager.update_bot_status(bot_id, status)
            log_debug(bot_id, f"机器人状态缓存已更新", "BOT_CACHE_STATUS_UPDATED", status=status)
        except Exception as e:
            # Redis不可用时不应该阻止机器人操作，只记录警告
            log_warn(bot_id, f"更新机器人状态缓存失败(Redis可能不可用): {e}", "BOT_CACHE_STATUS_UPDATE_WARNING",
                     error=str(e))

    @staticmethod
    def _extract_protocol_cache_key(protocol: str, bot_config: dict | None) -> str | None:
        """根据协议配置提取缓存映射键值"""
        if not protocol or not bot_config:
            return None
        try:
            adapter_manager = get_adapter_manager()
            adapter_class = adapter_manager.get_adapter_class(protocol)
            if not adapter_class:
                return None
            cache_key_field = adapter_class.get_cache_key_field()
            if not cache_key_field:
                return None
            cache_key = bot_config.get(cache_key_field)
            if cache_key is None:
                return None
            cache_key = str(cache_key).strip()
            return cache_key or None
        except Exception:
            return None

    def _clear_bot_cache(self, bot_id: int, protocol: str = None, cache_key: str = None):
        """清理机器人缓存"""
        try:
            bot_cache_manager.clear_bot_cache(bot_id, protocol=protocol, cache_key=cache_key)
            log_debug(bot_id, f"机器人缓存已清理", "BOT_CACHE_CLEARED",
                      protocol=protocol, cache_key=cache_key)
        except Exception as e:
            # Redis不可用时不应该阻止机器人操作，只记录警告
            log_warn(bot_id, f"清理机器人缓存失败(Redis可能不可用): {e}", "BOT_CACHE_CLEAR_WARNING", error=str(e))

    @classmethod
    def auto_recover_bot_status_on_startup(cls):
        """应用启动时自动恢复机器人状态 - 根据之前的运行状态决定是否自动启动"""
        try:
            from Models import Bot, db
            from flask import current_app

            with current_app.app_context():
                # 查找所有标记为运行中的机器人
                running_bots = Bot.query.filter_by(is_running=True).all()

                if running_bots:
                    log_info(0, f"检测到{len(running_bots)}个机器人之前在运行，开始自动恢复",
                             "STARTUP_AUTO_RECOVERY_START")

                    # 获取全局机器人管理器实例
                    from BluePrints.admin.bots import get_bot_manager
                    bot_manager = get_bot_manager()

                    success_count = 0
                    failed_count = 0

                    for bot in running_bots:
                        try:
                            bot_config = bot.get_config()
                            protocol = bot.protocol
                            log_info(bot.id, f"正在自动启动机器人: {bot.name}", "BOT_AUTO_START_BEGIN",
                                     bot_name=bot.name, protocol=protocol)

                            # 检查机器人配置完整性
                            adapter_manager = get_adapter_manager()
                            adapter_class = adapter_manager.get_adapter_class(protocol)
                            config_valid, config_error = (False, f"不支持的协议类型: {protocol}")
                            if adapter_class:
                                config_valid, config_error = adapter_class.validate_bot_config(bot_config)

                            if not config_valid:
                                failed_count += 1
                                bot.is_running = False
                                bot.updated_at = cls._get_current_time_static()
                                log_error(bot.id, f" 机器人 {bot.name} 配置无效，跳过自动启动: {config_error}",
                                          "BOT_AUTO_START_CONFIG_INCOMPLETE", bot_name=bot.name, error=config_error)
                                continue

                            # 尝试启动机器人
                            result = bot_manager.start_bot(bot.id)

                            if result['success']:
                                success_count += 1
                                log_info(bot.id, f" 机器人 {bot.name} 自动启动成功", "BOT_AUTO_START_SUCCESS",
                                         bot_name=bot.name)
                            elif "已在运行" in result.get('message', ''):
                                # 机器人已在运行，这也算成功恢复
                                success_count += 1
                                log_info(bot.id, f" 机器人 {bot.name} 已在运行，无需启动",
                                         "BOT_AUTO_START_ALREADY_RUNNING",
                                         bot_name=bot.name)
                            else:
                                failed_count += 1
                                # 启动失败，重置状态为停止
                                bot.is_running = False
                                bot.updated_at = cls._get_current_time_static()

                                # 清理缓存
                                try:
                                    cache_key = cls._extract_protocol_cache_key(protocol, bot_config)
                                    bot_cache_manager.clear_bot_cache(bot.id, protocol=protocol, cache_key=cache_key)
                                except Exception:
                                    pass  # 缓存清理失败不影响主流程

                                log_error(bot.id,
                                          f" 机器人 {bot.name} 自动启动失败: {result.get('message', '未知错误')}",
                                          "BOT_AUTO_START_FAILED", bot_name=bot.name,
                                          error=result.get('message', '未知错误'))

                        except Exception as e:
                            failed_count += 1
                            # 启动异常，重置状态为停止
                            bot.is_running = False
                            bot.updated_at = cls._get_current_time_static()

                            # 清理缓存
                            try:
                                bot_config = bot.get_config()
                                protocol = bot.protocol
                                cache_key = cls._extract_protocol_cache_key(protocol, bot_config)
                                bot_cache_manager.clear_bot_cache(bot.id, protocol=protocol, cache_key=cache_key)
                            except Exception:
                                pass  # 缓存清理失败不影响主流程

                            log_error(bot.id, f" 机器人 {bot.name} 自动启动异常: {e}", "BOT_AUTO_START_EXCEPTION",
                                      bot_name=bot.name, error=str(e))
                            # 记录详细的异常堆栈
                            import traceback
                            log_error(bot.id, f"自动启动异常详细信息", "BOT_AUTO_START_EXCEPTION_DETAIL",
                                      traceback=traceback.format_exc())

                    # 提交数据库更改
                    db.session.commit()

                    # 批量同步缓存 (预热)
                    if success_count > 0:
                        try:
                            synced_count = bot_cache_manager.batch_sync_from_database()
                            log_info(0, f"缓存预热完成，同步了 {synced_count} 个机器人", "STARTUP_CACHE_PRELOAD")
                        except Exception as cache_error:
                            log_warn(0, f"缓存预热失败: {cache_error}", "STARTUP_CACHE_PRELOAD_ERROR")

                        # 验证适配器状态 - 确保自动恢复的机器人在适配器中存在
                        try:
                            adapter_manager = get_adapter_manager()

                            verified_count = 0
                            for bot in running_bots:
                                if bot.is_running:  # 只检查成功启动的机器人
                                    adapter_status = adapter_manager.get_adapter_status(bot.id)
                                    if adapter_status:
                                        verified_count += 1
                                        log_debug(bot.id, f"适配器状态验证通过", "STARTUP_ADAPTER_VERIFIED",
                                                  running=adapter_status.get('running', False))
                                    else:
                                        log_warn(bot.id, f" 机器人 {bot.name} 自动恢复后适配器状态异常，尝试重新启动",
                                                 "STARTUP_ADAPTER_MISSING", bot_name=bot.name)
                                        # 尝试重新启动这个机器人
                                        try:
                                            restart_result = bot_manager.restart_bot(bot.id)
                                            if restart_result['success']:
                                                log_info(bot.id, f" 机器人 {bot.name} 重新启动成功",
                                                         "STARTUP_ADAPTER_RESTART_SUCCESS", bot_name=bot.name)
                                            else:
                                                log_error(bot.id,
                                                          f" 机器人 {bot.name} 重新启动失败: {restart_result.get('message')}",
                                                          "STARTUP_ADAPTER_RESTART_FAILED", bot_name=bot.name)
                                        except Exception as restart_error:
                                            log_error(bot.id, f" 机器人 {bot.name} 重新启动异常: {restart_error}",
                                                      "STARTUP_ADAPTER_RESTART_ERROR", bot_name=bot.name,
                                                      error=str(restart_error))

                            log_info(0, f"适配器状态验证完成，验证通过: {verified_count}/{success_count}",
                                     "STARTUP_ADAPTER_VERIFICATION_COMPLETE")

                        except Exception as verify_error:
                            log_warn(0, f"适配器状态验证失败: {verify_error}", "STARTUP_ADAPTER_VERIFICATION_ERROR")

                    log_info(0, f" 启动时自动恢复完成 - 成功: {success_count}, 失败: {failed_count}",
                             "STARTUP_AUTO_RECOVERY_COMPLETE", success_count=success_count, failed_count=failed_count)
                else:
                    log_info(0, " 启动时检查完成，没有需要恢复的机器人", "STARTUP_NO_RECOVERY_NEEDED")

        except Exception as e:
            log_error(0, f" 启动时自动恢复失败: {e}", "STARTUP_AUTO_RECOVERY_ERROR", error=str(e))
            # 即使恢复失败也不应该阻止应用启动

    @classmethod
    def force_reset_all_bot_status(cls):
        """强制重置所有机器人状态为停止 - 用于紧急情况或手动重置"""
        try:
            from Models import Bot, db
            from flask import current_app

            with current_app.app_context():
                # 查找所有标记为运行中的机器人
                running_bots = Bot.query.filter_by(is_running=True).all()

                if running_bots:
                    log_info(0, f"强制重置{len(running_bots)}个机器人状态", "FORCE_RESET_START")

                    reset_count = 0
                    for bot in running_bots:
                        try:
                            # 重置状态
                            bot.is_running = False
                            bot.updated_at = cls._get_current_time_static()
                            reset_count += 1

                            log_info(bot.id, f"强制重置机器人 {bot.name} 状态为停止", "BOT_FORCE_RESET",
                                     bot_name=bot.name)
                        except Exception as e:
                            log_error(bot.id, f"强制重置机器人状态失败: {e}", "BOT_FORCE_RESET_ERROR", error=str(e))

                    # 提交数据库更改
                    db.session.commit()
                    log_info(0, f" 强制重置完成，共重置{reset_count}个机器人", "FORCE_RESET_COMPLETE",
                             reset_count=reset_count)
                    return True
                else:
                    log_info(0, " 没有需要重置的机器人", "FORCE_RESET_NO_NEED")
                    return True

        except Exception as e:
            log_error(0, f" 强制重置失败: {e}", "FORCE_RESET_ERROR", error=str(e))
            return False

    @staticmethod
    def _get_current_time_static():
        """静态方法获取当前时间"""
        try:
            from Models.Extensions import get_current_time
            return get_current_time()
        except ImportError:
            from datetime import datetime
            return datetime.now()

    def _format_uptime(self, seconds):
        """格式化运行时长"""
        if seconds < 60:
            return f"{int(seconds)}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes}分钟"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分钟"

    def set_app(self, app):
        """设置 Flask 应用引用"""
        self._app = app

    def _start_status_monitoring(self):
        """启动状态监控"""
        import threading

        self._shutdown_event = threading.Event()

        def status_monitor():
            while not self._shutdown_event.is_set():
                try:
                    # 使用 wait 代替 sleep，可以被 shutdown_event 打断
                    if self._shutdown_event.wait(timeout=60):  # 60秒或被中断
                        break  # 收到停止信号，退出

                    # 在Flask应用上下文中执行状态检查
                    if self._app:
                        with self._app.app_context():
                            self._log_system_status()
                    else:
                        # 如果没有保存的 app 引用，尝试获取
                        try:
                            from flask import current_app
                            app = current_app._get_current_object()
                            with app.app_context():
                                self._log_system_status()
                        except RuntimeError:
                            # 如果无法获取当前应用，导入应用实例
                            from app import app
                            with app.app_context():
                                self._log_system_status()

                except Exception as e:
                    log_error(0, f"状态监控异常: {e}", "BOT_MANAGER_MONITOR_ERROR", error=str(e))

        # 启动后台监控线程
        self._monitor_thread = threading.Thread(target=status_monitor, daemon=True, name="BotStatusMonitor")
        self._monitor_thread.start()

    def shutdown(self):
        """优雅关闭 BotManager"""
        try:
            log_info(0, "开始关闭 BotManager...", "BOT_MANAGER_SHUTDOWN_START")

            # 通知监控线程停止
            if self._shutdown_event:
                self._shutdown_event.set()

            # 等待监控线程结束（最多等待 5 秒）
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)

            log_info(0, "BotManager 已关闭", "BOT_MANAGER_SHUTDOWN_COMPLETE")
        except Exception as e:
            log_error(0, f"BotManager 关闭异常: {e}", "BOT_MANAGER_SHUTDOWN_ERROR", error=str(e))

    def _log_system_status(self):
        """记录系统状态"""
        if not self.running_bots:
            return

        # 记录系统级状态
        running_count = len(self.running_bots)
        total_messages = sum(bot.get('message_count', 0) for bot in self.bots.values())
        total_errors = sum(bot.get('error_count', 0) for bot in self.bots.values())

        log_info(0, f"系统状态检查", "SYSTEM_STATUS",
                 running_bots=running_count, total_messages=total_messages,
                 total_errors=total_errors)

        # 为每个运行中的机器人记录状态
        for bot_id in self.running_bots:
            if bot_id in self.bots:
                bot_info = self.bots[bot_id]
                status = self.get_bot_status(bot_id)
                # 状态正常，无需记录日志
