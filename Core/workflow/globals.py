"""
全局变量管理器

从数据库加载全局变量并缓存到 Redis，供工作流使用
"""
import json
from typing import Any

from Core.logging.file_logger import log_info, log_error

# Redis key
GLOBALS_CACHE_KEY = "workflow:globals"


class GlobalVariableManager:
    """全局变量管理器"""

    _instance = None
    _cache = {}  # 内存缓存

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self):
        """从数据库加载全局变量到缓存"""
        try:
            from Models import GlobalVariable
            from Database.Redis.client import set_value

            variables = GlobalVariable.get_all()
            self._cache = {var.key: var.value for var in variables}

            # 同步到 Redis
            set_value(GLOBALS_CACHE_KEY, json.dumps(self._cache, ensure_ascii=False))

            log_info(0, f"加载全局变量: {len(self._cache)} 个", "GLOBALS_LOAD")
            return len(self._cache)

        except Exception as e:
            log_error(0, f"加载全局变量失败: {e}", "GLOBALS_LOAD_ERROR", error=str(e))
            return 0

    def reload(self):
        """重新加载全局变量"""
        return self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """获取全局变量值"""
        # 优先从内存缓存读取
        if key in self._cache:
            return self._cache[key]

        # 内存没有则尝试从 Redis 读取
        try:
            from Database.Redis.client import get_value
            cached = get_value(GLOBALS_CACHE_KEY)
            if cached:
                if isinstance(cached, bytes):
                    cached = cached.decode('utf-8')
                self._cache = json.loads(cached)
                return self._cache.get(key, default)
        except Exception:
            pass

        return default

    def get_all(self) -> dict:
        """获取所有全局变量"""
        # 如果内存缓存为空，尝试从 Redis 加载
        if not self._cache:
            try:
                from Database.Redis.client import get_value
                cached = get_value(GLOBALS_CACHE_KEY)
                if cached:
                    if isinstance(cached, bytes):
                        cached = cached.decode('utf-8')
                    self._cache = json.loads(cached)
            except Exception:
                pass
        return self._cache.copy()

    def set(self, key: str, value: str, description: str = None, is_secret: bool = False):
        """设置全局变量（同时更新数据库和缓存）"""
        try:
            from Models import GlobalVariable
            from Database.Redis.client import set_value

            # 更新数据库
            GlobalVariable.set_value(key, value, description, is_secret)

            # 更新缓存
            self._cache[key] = value
            set_value(GLOBALS_CACHE_KEY, json.dumps(self._cache, ensure_ascii=False))
            return True

        except Exception as e:
            log_error(0, f"设置全局变量失败: {e}", "GLOBALS_SET_ERROR", key=key, error=str(e))
            return False

    def delete(self, key: str):
        """删除全局变量"""
        try:
            from Models import GlobalVariable
            from Database.Redis.client import set_value

            # 从数据库删除
            GlobalVariable.delete_by_key(key)

            # 更新缓存
            if key in self._cache:
                del self._cache[key]
            set_value(GLOBALS_CACHE_KEY, json.dumps(self._cache, ensure_ascii=False))
            return True

        except Exception as e:
            log_error(0, f"删除全局变量失败: {e}", "GLOBALS_DELETE_ERROR", key=key, error=str(e))
            return False


# 单例实例
global_variables = GlobalVariableManager()
