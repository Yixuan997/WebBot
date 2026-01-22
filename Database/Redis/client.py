"""
@Project ：Yapi
@File    ：client.py
@IDE     ：PyCharm
@Author  ：杨逸轩
@Date    ：2024/6/18 下午9:41
"""
import threading
import time
from collections import defaultdict

from redis import ConnectionPool, Redis, RedisError

# 全局变量
_pool = None  # Redis连接池
_memory_cache = defaultdict(dict)  # 内存缓存，用于Redis降级
_redis_available = True  # Redis可用性标志
_last_status = True  # 上一次Redis状态
_failure_count = 0  # Redis失败计数
_app = None  # 存储Flask应用实例
_last_health_check = 0  # 上次健康检查时间

# 线程锁保护全局状态
_redis_lock = threading.Lock()
_cache_lock = threading.Lock()


def health_check():
    """Redis连接池健康检查 - 简化版本"""
    global _redis_available, _last_status, _app, _last_health_check

    while True:
        try:
            if not _app:
                time.sleep(30)
                continue

            with _app.app_context():
                if not _pool:
                    time.sleep(30)
                    continue

                try:
                    # 简单的ping检查
                    with Redis(connection_pool=_pool) as client:
                        client.ping()

                    # 状态恢复
                    with _redis_lock:
                        if not _redis_available or not _last_status:
                            _redis_available = True
                            _last_status = True
                            _app.logger.info("Redis服务已恢复可用")

                except RedisError as e:
                    with _redis_lock:
                        if _last_status:
                            _redis_available = False
                            _last_status = False
                            _app.logger.error(f"Redis服务不可用: {str(e)}")

                except Exception as e:
                    with _redis_lock:
                        if _last_status:
                            _redis_available = False
                            _last_status = False
                            _app.logger.error(f"Redis健康检查失败: {str(e)}")

        except Exception as e:
            with _redis_lock:
                if _last_status:
                    _redis_available = False
                    _last_status = False
            if _app:
                try:
                    with _app.app_context():
                        _app.logger.error(f"Redis健康检查线程异常: {str(e)}")
                except Exception:
                    pass

        finally:
            # 获取检查间隔
            check_interval = 30
            if _app:
                try:
                    with _app.app_context():
                        check_interval = _app.config['REDIS_POOL_CONFIG']['health_check_interval']
                except Exception:
                    pass
            time.sleep(check_interval)


def init_redis(app):
    """初始化Redis连接池 - 简化版本"""
    global _pool, _redis_available, _failure_count, _last_status, _app

    if not app:
        raise ValueError("Flask应用实例不能为None")

    _app = app

    redis_url = app.config.get('REDIS_URL')
    pool_config = app.config.get('REDIS_POOL_CONFIG', {})
    client_config = app.config.get('REDIS_CLIENT_CONFIG', {})

    # 如果没有REDIS_URL，禁用Redis
    if not redis_url:
        _redis_available = False
        _last_status = False
        _failure_count = 0
        return

    try:
        # 合并配置
        final_config = {
            **pool_config,
            'decode_responses': client_config.get('decode_responses', False),
        }

        # 创建连接池
        _pool = ConnectionPool.from_url(redis_url, **final_config)

        # 测试连接
        with Redis(connection_pool=_pool) as client:
            client.ping()

        _redis_available = True
        _last_status = True
        _failure_count = 0

        # 启动健康检查线程
        health_check_thread = threading.Thread(
            target=health_check,
            daemon=True,
            name="RedisHealthCheck"
        )
        health_check_thread.start()

    except Exception as e:
        _redis_available = False
        _last_status = False
        _failure_count = 0
        # 启动时 Redis 不可用，给出友好提示
        if app:
            app.logger.warning(f"Redis 连接失败: {e}")
            app.logger.warning("⚠️  系统将在没有 Redis 的情况下运行（部分功能可能受限）")
            app.logger.info("💡 如需启用 Redis，请安装并启动 Redis 服务，然后重启应用")


def get_redis():
    """
    获取 Redis 客户端实例
    """
    global _redis_available

    with _redis_lock:
        redis_available = _redis_available

    if not redis_available:
        raise RedisError("Redis服务不可用")

    if _pool is None:
        raise RuntimeError("Redis连接池未初始化")

    try:
        # 创建Redis实例，支持上下文管理器
        return Redis(connection_pool=_pool)
    except Exception as e:
        with _redis_lock:
            _redis_available = False
        raise RuntimeError(f"获取Redis连接失败: {str(e)}")


def _try_reconnect():
    """尝试重新连接Redis"""
    global _redis_available, _failure_count, _last_status

    if not _pool:
        return False

    try:
        with Redis(connection_pool=_pool) as client:
            client.ping()
        with _redis_lock:
            _redis_available = True
            _last_status = True
            _failure_count = 0
        return True
    except Exception:
        return False


def _handle_redis_failure():
    """处理Redis操作失败"""
    global _redis_available, _failure_count, _last_status

    with _redis_lock:
        _redis_available = False
        _last_status = False
        _failure_count += 1
        should_reconnect = _failure_count >= 3

    # 达到重试阈值时尝试重连
    if should_reconnect:
        _try_reconnect()


# Redis操作函数
def set_value(key, value, expire_seconds=None):
    """写入键值对，支持Redis降级到内存缓存"""
    global _redis_available

    with _redis_lock:
        redis_available = _redis_available

    if not redis_available and not _try_reconnect():
        _clean_memory_cache()
        with _cache_lock:
            _memory_cache[key] = {
                'value': value,
                'expire_time': time.time() + (expire_seconds or float('inf'))
            }
        return

    try:
        # 使用with语句确保连接立即释放
        with get_redis() as client:
            client.set(key, value, ex=expire_seconds)
    except Exception:
        _handle_redis_failure()
        _clean_memory_cache()
        with _cache_lock:
            _memory_cache[key] = {
                'value': value,
                'expire_time': time.time() + (expire_seconds or float('inf'))
            }


def get_value(key):
    """读取键值，支持Redis降级到内存缓存"""
    global _redis_available

    with _redis_lock:
        redis_available = _redis_available

    if not redis_available and not _try_reconnect():
        _clean_memory_cache()
        with _cache_lock:
            cache_data = _memory_cache.get(key)
            if cache_data and cache_data['expire_time'] > time.time():
                return cache_data['value']
        return None

    try:
        # 使用with语句确保连接立即释放
        with get_redis() as client:
            return client.get(key)
    except Exception:
        _handle_redis_failure()
        _clean_memory_cache()
        with _cache_lock:
            cache_data = _memory_cache.get(key)
            if cache_data and cache_data['expire_time'] > time.time():
                return cache_data['value']
        return None


def delete_key(key):
    """删除键，支持Redis降级到内存缓存"""
    global _redis_available

    with _redis_lock:
        redis_available = _redis_available

    if not redis_available and not _try_reconnect():
        with _cache_lock:
            if key in _memory_cache:
                del _memory_cache[key]
        return

    try:
        # 使用with语句确保连接立即释放
        with get_redis() as client:
            client.delete(key)
    except Exception:
        _handle_redis_failure()
        with _cache_lock:
            if key in _memory_cache:
                del _memory_cache[key]


def _clean_memory_cache():
    """清理过期的内存缓存"""
    current_time = time.time()
    with _cache_lock:
        for key in list(_memory_cache.keys()):
            if _memory_cache[key].get('expire_time', 0) < current_time:
                del _memory_cache[key]


def _get_redis_config():
    """获取Redis配置信息，避免重复代码"""
    if _app and hasattr(_app, 'config'):
        redis_pool_config = _app.config.get('REDIS_POOL_CONFIG', {})
        redis_client_config = _app.config.get('REDIS_CLIENT_CONFIG', {})

        return {
            'pool_max_connections': redis_pool_config.get('max_connections', 200),
            'max_clients': redis_client_config.get('server_max_clients', 10000)
        }
    else:
        return {
            'pool_max_connections': 200,
            'max_clients': 10000
        }


def get_redis_info():
    """
    获取Redis信息，支持降级

    Returns:
        dict: 总是返回包含Redis状态信息的字典
    """
    # 获取配置信息
    config = _get_redis_config()

    try:
        with get_redis() as client:
            # 获取Redis服务器信息
            info = client.info()

            # 尝试获取服务器最大客户端数
            max_clients = config['max_clients']
            try:
                max_clients_config = client.config_get('maxclients')
                if max_clients_config and 'maxclients' in max_clients_config:
                    max_clients = int(max_clients_config['maxclients'])
            except Exception:
                # 获取失败，使用配置默认值
                pass

            return {
                'status': 'connected',
                'version': info.get('redis_version', 'unknown'),
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'max_clients': max_clients,
                'pool_max_connections': config['pool_max_connections'],
                'uptime': info.get('uptime_in_seconds', 0)
            }

    except Exception as e:
        # 连接失败，返回降级信息
        return {
            'status': 'disconnected',
            'version': 'unknown',
            'used_memory': 'N/A',
            'connected_clients': 0,
            'max_clients': config['max_clients'],
            'pool_max_connections': config['pool_max_connections'],
            'uptime': 0,
            'error': str(e)
        }


def get_redis_stats():
    """获取Redis统计信息，支持降级"""
    try:
        client = get_redis()
        info = client.info()
        return {
            'total_commands_processed': info.get('total_commands_processed', 0),
            'keyspace_hits': info.get('keyspace_hits', 0),
            'keyspace_misses': info.get('keyspace_misses', 0),
            'used_memory': info.get('used_memory', 0),
            'connected_clients': info.get('connected_clients', 0)
        }
    except Exception:
        return {
            'total_commands_processed': 0,
            'keyspace_hits': 0,
            'keyspace_misses': 0,
            'used_memory': 0,
            'connected_clients': 0
        }


def get_redis_keys_info():
    """获取Redis键信息，支持降级"""
    try:
        client = get_redis()
        db_size = client.dbsize()
        info = client.info()
        used_memory = info.get('used_memory', 0)

        # 计算每个键的平均内存使用
        memory_per_key = 'N/A'
        if db_size > 0 and used_memory > 0:
            memory_per_key = f"{used_memory / db_size:.2f}"

        return {
            'total_keys': db_size,
            'memory_per_key': memory_per_key
        }
    except Exception:
        return {
            'total_keys': len(_memory_cache),
            'memory_per_key': 'N/A'
        }
