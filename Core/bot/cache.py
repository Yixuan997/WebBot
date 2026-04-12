"""
机器人缓存管理器

基于Redis的高性能机器人查找和状态缓存系统
支持智能缓存刷新机制
"""

import json
import threading
import time

from Core.logging.file_logger import log_info, log_error, log_warn, log_debug
from Database.Redis.client import get_redis, set_value, get_value, delete_key


class BotCacheManager:
    """机器人缓存管理器"""

    def __init__(self):
        # 缓存键前缀设计 - 与插件系统保持一致的命名风格
        self.mapping_prefix = "bot:mapping:"  # protocol:cache_key → bot_id 映射
        self.status_prefix = "bot:status:"  # bot_id → 运行状态
        self.config_prefix = "bot:config:"  # bot_id → 配置缓存

        # 缓存TTL设置 - 与插件系统保持一致
        self.config_ttl = 300  # 配置缓存5分钟，避免配置更新不同步
        # 映射和状态不设置TTL，除非机器人删除

        # 智能缓存比例控制
        self.refresh_ratio = 0.7  # 70%后异步刷新 (3.5分钟)
        self.max_age_ratio = 6  # 6倍后强制刷新 (30分钟)

        # 刷新锁，防止重复刷新
        self._refresh_locks = {}

    def _get_mapping_key(self, protocol: str, cache_key: str) -> str:
        """获取 protocol + cache_key 到 bot_id 的映射键"""
        return f"{self.mapping_prefix}{protocol}:{cache_key}"

    def _get_status_key(self, bot_id: int) -> str:
        """获取机器人状态缓存键"""
        return f"{self.status_prefix}{bot_id}"

    def _get_config_key(self, bot_id: int) -> str:
        """获取机器人配置缓存键"""
        return f"{self.config_prefix}{bot_id}"

    def update_bot_mapping(self, bot_id: int, protocol: str, cache_key: str, status: str) -> bool:
        """
        更新机器人映射和状态

        Args:
            bot_id: 机器人ID
            protocol: 协议标识
            cache_key: 协议缓存键（如 app_id）
            status: 运行状态 ("running" 或 "stopped")

        Returns:
            bool: 操作是否成功
        """
        try:
            # 更新映射关系 (永久存储)
            mapping_key = self._get_mapping_key(protocol, cache_key)
            set_value(mapping_key, str(bot_id))

            # 更新状态
            status_key = self._get_status_key(bot_id)
            set_value(status_key, status)

            log_debug(bot_id, f"更新机器人缓存映射", "BOT_CACHE_MAPPING_UPDATE",
                      protocol=protocol, cache_key=cache_key, status=status)
            return True

        except Exception as e:
            # Redis不可用时不应该阻止机器人启动，只记录警告
            log_warn(bot_id, f"更新机器人缓存映射失败(Redis可能不可用): {e}", "BOT_CACHE_MAPPING_UPDATE_WARNING",
                     protocol=protocol, cache_key=cache_key, error=str(e))
            return True  # 返回True，不阻止机器人启动

    def update_bot_config_cache(self, bot_id: int, config: dict) -> bool:
        """
        更新机器人配置缓存 - 智能缓存版本

        Args:
            bot_id: 机器人ID
            config: 机器人配置字典

        Returns:
            bool: 操作是否成功
        """
        try:
            config_key = self._get_config_key(bot_id)

            # 处理datetime对象，转换为字符串
            serializable_config = self._make_config_serializable(config)

            # 构建智能缓存格式
            smart_cache = {
                "data": serializable_config,
                "metadata": {
                    "cached_at": time.time(),
                    "refreshing": False
                }
            }

            # 保存为智能缓存格式，不设置TTL让缓存"永不过期"
            set_value(config_key, json.dumps(smart_cache))

            log_debug(bot_id, f"更新机器人配置缓存", "BOT_CACHE_CONFIG_UPDATE")
            return True

        except Exception as e:
            # Redis不可用时不应该阻止机器人启动，只记录警告
            log_warn(bot_id, f"更新机器人配置缓存失败(Redis可能不可用): {e}", "BOT_CACHE_CONFIG_UPDATE_WARNING",
                     error=str(e))
            return True  # 返回True，不阻止机器人启动

    def _make_config_serializable(self, config: dict) -> dict:
        """
        将配置字典转换为可JSON序列化的格式

        Args:
            config: 原始配置字典

        Returns:
            dict: 可序列化的配置字典
        """
        import datetime

        serializable_config = {}
        for key, value in config.items():
            if isinstance(value, datetime.datetime):
                # 将datetime转换为ISO格式字符串
                serializable_config[key] = value.isoformat() if value else None
            elif isinstance(value, datetime.date):
                # 将date转换为ISO格式字符串
                serializable_config[key] = value.isoformat() if value else None
            else:
                serializable_config[key] = value

        return serializable_config

    def get_bot_by_mapping(self, protocol: str, cache_key: str) -> int | None:
        """
        通过协议映射键查找 bot_id (高性能版本)

        Args:
            protocol: 协议标识
            cache_key: 协议缓存键

        Returns:
            int: 机器人ID，如果未找到或未运行则返回None
        """
        try:
            # 1. 从Redis查找映射
            mapping_key = self._get_mapping_key(protocol, cache_key)
            bot_id_str = get_value(mapping_key)

            if bot_id_str:
                try:
                    # 解码字节串
                    if isinstance(bot_id_str, bytes):
                        bot_id_str = bot_id_str.decode('utf-8')

                    bot_id = int(bot_id_str)

                    # 2. 检查运行状态
                    status_key = self._get_status_key(bot_id)
                    status = get_value(status_key)

                    if isinstance(status, bytes):
                        status = status.decode('utf-8')

                    if status == "running":
                        log_debug(0, f"缓存命中: {protocol}:{cache_key} → bot_id={bot_id}",
                                  "BOT_CACHE_HIT", protocol=protocol, cache_key=cache_key, found_bot_id=bot_id)
                        return bot_id
                    else:
                        log_debug(0, f"机器人未运行: {protocol}:{cache_key}, status={status}",
                                  "BOT_CACHE_NOT_RUNNING", protocol=protocol, cache_key=cache_key, bot_status=status)
                        return None

                except (ValueError, TypeError) as e:
                    log_warn(0, f"缓存数据格式错误: {e}", "BOT_CACHE_FORMAT_ERROR",
                             protocol=protocol, cache_key=cache_key, error=str(e))
                    return None

            # 3. 缓存未命中
            log_debug(0, f"缓存未命中: {protocol}:{cache_key}", "BOT_CACHE_MISS",
                      protocol=protocol, cache_key=cache_key)
            return None

        except Exception as e:
            log_error(0, f"查找机器人缓存异常: {e}", "BOT_CACHE_LOOKUP_ERROR",
                      protocol=protocol, cache_key=cache_key, error=str(e))
            return None

    def get_bot_config_cached(self, bot_id: int) -> dict | None:
        """
        获取缓存的机器人配置 - 智能缓存版本

        Args:
            bot_id: 机器人ID

        Returns:
            dict: 机器人配置，如果缓存未命中则返回None
        """
        try:
            config_key = self._get_config_key(bot_id)
            cached_data = get_value(config_key)

            if cached_data:
                try:
                    if isinstance(cached_data, bytes):
                        cached_data = cached_data.decode('utf-8')

                    cache_obj = json.loads(cached_data)

                    if isinstance(cache_obj, dict) and 'data' in cache_obj and 'metadata' in cache_obj:
                        return self._handle_smart_cache(bot_id, cache_obj)

                    log_warn(
                        bot_id,
                        "配置缓存格式无效，忽略缓存并等待重建",
                        "BOT_CONFIG_CACHE_INVALID_FORMAT"
                    )
                    return None

                except (json.JSONDecodeError, AttributeError) as e:
                    log_warn(bot_id, f"解析配置缓存失败: {e}", "BOT_CONFIG_CACHE_PARSE_ERROR",
                             error=str(e))
                    return None

            log_debug(bot_id, f"配置缓存未命中", "BOT_CONFIG_CACHE_MISS")
            return None

        except Exception as e:
            log_error(bot_id, f"获取配置缓存异常: {e}", "BOT_CONFIG_CACHE_ERROR", error=str(e))
            return None

    def _handle_smart_cache(self, bot_id: int, cache_obj: dict) -> dict:
        """
        处理智能缓存逻辑，根据缓存年龄决定是否需要刷新
        
        Args:
            bot_id: 机器人id
            cache_obj: 智能缓存对象，包含data和metadata
            
        Returns:
            dict: 机器人配置字典
        """
        current_time = time.time()
        data = cache_obj['data']
        metadata = cache_obj['metadata']
        cached_at = metadata.get('cached_at', 0)
        is_refreshing = metadata.get('refreshing', False)

        if cached_at == 0:
            # 无效的缓存时间，重新加载
            log_warn(bot_id, "缓存时间无效，重新加载", "CACHE_INVALID_TIME")
            return self._load_and_cache_from_database(bot_id)

        age = current_time - cached_at
        refresh_time = self.config_ttl * self.refresh_ratio  # 3.5分钟
        max_age_time = self.config_ttl * self.max_age_ratio  # 30分钟

        # 情况1：太旧了，必须刷新
        if age > max_age_time:
            log_info(bot_id, f"缓存过旧 > {max_age_time:.0f}s)，重新加载", "CACHE_TOO_OLD")
            return self._load_and_cache_from_database(bot_id)

        # 情况2：该刷新了，后台刷新
        elif age > refresh_time and not is_refreshing:
            log_debug(bot_id, f"触发后台刷新 > {refresh_time:.0f}s)", "CACHE_BACKGROUND_REFRESH")
            self._async_refresh_cache(bot_id, cache_obj)

        # 返回现有数据
        log_debug(bot_id, f"智能缓存命中", "BOT_CONFIG_SMART_CACHE_HIT")
        return data

    def _load_and_cache_from_database(self, bot_id: int) -> dict | None:
        """
        从数据库加载配置并缓存
        
        Args:
            bot_id: 机器人id
            
        Returns:
            dict | None: 机器人配置，失败返回None
        """
        try:
            from Models import Bot
            from flask import current_app

            def _load_with_context():
                bot = Bot.query.get(bot_id)
                if bot:
                    # 获取协议配置
                    protocol = getattr(bot, 'protocol', None) or ""
                    bot_config_data = bot.get_config()

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
                    return config
                return None

            # 尝试在当前上下文中执行
            try:
                config = _load_with_context()
            except RuntimeError as e:
                # 不在Flask应用上下文中，创建新的上下文
                log_debug(bot_id, "不在应用上下文中，创建新的上下文", "BOT_CONFIG_NO_APP_CONTEXT")
                from app import app
                with app.app_context():
                    config = _load_with_context()

            if config:
                # 保存为智能缓存格式
                self.update_bot_config_cache(bot_id, config)
                log_info(bot_id, "从数据库重新加载配置", "BOT_CONFIG_DB_RELOAD")
                return config
            else:
                log_warn(bot_id, f"数据库中未找到机器人ID {bot_id}", "BOT_NOT_FOUND_IN_DB")
                return None

        except (ImportError, AttributeError) as e:
            from Core.logging.utils import format_exception
            log_error(bot_id, f"从数据库加载配置失败: {e}", "BOT_CONFIG_DB_LOAD_ERROR",
                      error=str(e), traceback=format_exception(e))
            return None

    def _async_refresh_cache(self, bot_id: int, cache_obj: dict):
        """
        异步刷新缓存（后台线程）
        
        Args:
            bot_id: 机器人id
            cache_obj: 当前缓存对象引用
        """
        # 防止重复刷新
        lock_key = f"refresh_lock_{bot_id}"
        if lock_key in self._refresh_locks:
            return

        def refresh_task():
            try:
                self._refresh_locks[lock_key] = True

                # 标记正在刷新
                cache_obj['metadata']['refreshing'] = True
                config_key = self._get_config_key(bot_id)
                set_value(config_key, json.dumps(cache_obj))

                # 加载新数据
                new_config = self._load_and_cache_from_database(bot_id)
                if new_config:
                    log_info(bot_id, "后台缓存刷新完成", "CACHE_BACKGROUND_REFRESH_DONE")
                else:
                    # 刷新失败，恢复状态
                    cache_obj['metadata']['refreshing'] = False
                    set_value(config_key, json.dumps(cache_obj))
                    log_warn(bot_id, "后台缓存刷新失败", "CACHE_BACKGROUND_REFRESH_FAILED")

            except Exception as e:
                from Core.logging.utils import format_exception
                log_error(bot_id, f"后台缓存刷新异常: {e}", "CACHE_BACKGROUND_REFRESH_ERROR",
                          error=str(e), traceback=format_exception(e))
            finally:
                if lock_key in self._refresh_locks:
                    del self._refresh_locks[lock_key]

        # 启动后台刷新线程
        refresh_thread = threading.Thread(target=refresh_task, daemon=True)
        refresh_thread.start()

    def update_bot_status(self, bot_id: int, status: str) -> bool:
        """
        更新机器人状态
        
        Args:
            bot_id: 机器人ID
            status: 新状态 ("running" 或 "stopped")
            
        Returns:
            bool: 操作是否成功
        """
        try:
            status_key = self._get_status_key(bot_id)
            set_value(status_key, status)

            log_debug(bot_id, f"更新机器人状态缓存", "BOT_CACHE_STATUS_UPDATE", status=status)
            return True

        except Exception as e:
            # Redis不可用时不应该阻止机器人启动，只记录警告
            log_warn(bot_id, f"更新机器人状态缓存失败(Redis可能不可用): {e}", "BOT_CACHE_STATUS_UPDATE_WARNING",
                     error=str(e))
            return True  # 返回True，不阻止机器人启动

    def clear_bot_cache(self, bot_id: int, protocol: str = None, cache_key: str = None) -> bool:
        """
        清理机器人缓存
        
        Args:
            bot_id: 机器人ID
            protocol: 协议标识（可选）
            cache_key: 协议缓存键（可选，如果提供则同时清理映射）
            
        Returns:
            bool: 操作是否成功
        """
        try:
            success = True

            # 清理状态缓存
            status_key = self._get_status_key(bot_id)
            if not delete_key(status_key):
                success = False

            # 清理配置缓存
            config_key = self._get_config_key(bot_id)
            if not delete_key(config_key):
                success = False

            # 如果提供了映射键，清理协议映射
            if protocol and cache_key:
                mapping_key = self._get_mapping_key(protocol, cache_key)
                if not delete_key(mapping_key):
                    success = False

            if success:
                log_debug(bot_id, f"清理机器人缓存", "BOT_CACHE_CLEAR",
                          protocol=protocol, cache_key=cache_key)
            else:
                log_warn(bot_id, f"清理机器人缓存部分失败", "BOT_CACHE_CLEAR_PARTIAL",
                         protocol=protocol, cache_key=cache_key)

            return success

        except Exception as e:
            log_error(bot_id, f"清理机器人缓存异常: {e}", "BOT_CACHE_CLEAR_ERROR",
                      protocol=protocol, cache_key=cache_key, error=str(e))
            return False

    def batch_sync_from_database(self) -> int:
        """
        从数据库批量同步机器人缓存 (用于启动时预热)
        
        Returns:
            int: 同步的机器人数量
        """
        try:
            from Models import Bot
            from flask import current_app

            # 确保在Flask应用上下文中执行
            def _sync_with_context():
                # 查找所有运行中的机器人
                running_bots = Bot.query.filter_by(is_running=True).all()
                sync_count = 0

                for bot in running_bots:
                    try:
                        # 获取协议配置
                        protocol = getattr(bot, 'protocol', None) or ""
                        bot_config_data = bot.get_config()

                        # 构建配置字典
                        config = {
                            'id': bot.id,
                            'name': bot.name,
                            'protocol': protocol,
                            'description': bot.description or '',
                            'status': 'running' if bot.is_running else 'stopped',
                            'created_at': bot.created_at,
                            'updated_at': bot.updated_at,
                            **bot_config_data
                        }

                        # 更新缓存映射（由适配器声明缓存键字段）
                        if protocol:
                            from Adapters import get_adapter_manager
                            adapter_class = get_adapter_manager().get_adapter_class(protocol)
                            if adapter_class:
                                cache_key_field = adapter_class.get_cache_key_field()
                                if cache_key_field:
                                    cache_key = bot_config_data.get(cache_key_field)
                                    if cache_key:
                                        self.update_bot_mapping(bot.id, protocol, str(cache_key), 'running')
                        self.update_bot_config_cache(bot.id, config)
                        sync_count += 1
                    except Exception:
                        pass

                return sync_count

            # 尝试在当前上下文中执行
            try:
                sync_count = _sync_with_context()
            except RuntimeError:
                # 不在Flask应用上下文中，创建新的上下文
                from app import app
                with app.app_context():
                    sync_count = _sync_with_context()

            if sync_count > 0:
                log_info(0, f"批量同步机器人缓存完成", "BOT_CACHE_BATCH_SYNC", sync_count=sync_count)

            return sync_count

        except Exception as e:
            log_error(0, f"批量同步机器人缓存失败: {e}", "BOT_CACHE_BATCH_SYNC_ERROR", error=str(e))
            return 0

    def get_cache_stats(self) -> dict:
        """
        获取缓存统计信息
        
        Returns:
            dict: 缓存统计信息
        """
        try:
            redis_client = get_redis()
            if not redis_client:
                return {
                    'redis_available': False,
                    'mapping_count': 0,
                    'status_count': 0,
                    'config_count': 0
                }

            # 统计各类缓存键的数量
            mapping_pattern = f"{self.mapping_prefix}*"
            status_pattern = f"{self.status_prefix}*"
            config_pattern = f"{self.config_prefix}*"

            mapping_count = len(list(redis_client.scan_iter(match=mapping_pattern)))
            status_count = len(list(redis_client.scan_iter(match=status_pattern)))
            config_count = len(list(redis_client.scan_iter(match=config_pattern)))

            return {
                'redis_available': True,
                'mapping_count': mapping_count,
                'status_count': status_count,
                'config_count': config_count
            }

        except Exception as e:
            log_error(0, f"获取缓存统计失败: {e}", "BOT_CACHE_STATS_ERROR", error=str(e))
            return {
                'redis_available': False,
                'mapping_count': 0,
                'status_count': 0,
                'config_count': 0,
                'error': str(e)
            }


# 创建全局实例
bot_cache_manager = BotCacheManager()
