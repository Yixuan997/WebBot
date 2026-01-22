"""
适配器模块 - 新架构
支持多种协议的统一适配器架构
"""

import threading
from typing import Dict, Any, Optional, List

# 导出基类
from .base import BaseAdapter, BaseBot, BaseEvent, BaseMessage, BaseMessageSegment

# 适配器注册表
_adapter_registry = {}


class AdapterManager:
    """适配器管理器"""

    def __init__(self):
        self.adapters: Dict[str, type] = {}
        self.running_adapters: Dict[int, BaseAdapter] = {}
        self._start_locks: Dict[int, threading.Lock] = {}  # 每个bot_id的启动锁
        self._locks_lock = threading.Lock()  # 保护_start_locks字典的锁

    def register_adapter(self, protocol_name: str, adapter_class: type):
        """注册适配器类"""
        if not issubclass(adapter_class, BaseAdapter):
            raise ValueError(f"适配器类必须继承自BaseAdapter")

        self.adapters[protocol_name] = adapter_class

        try:
            from Core.logging.file_logger import log_info
            log_info(0, f"📝 适配器已注册: {adapter_class.__name__}", "ADAPTER_REGISTERED",
                     protocol=protocol_name)
        except ImportError:
            pass

    def get_available_protocols(self) -> List[str]:
        """获取可用的协议列表"""
        return list(self.adapters.keys())

    def start_adapter(self, bot_id: int, protocol: str, config: Dict[str, Any],
                      message_handler=None) -> tuple[bool, str]:
        """启动指定协议的适配器，返回(成功状态, 错误信息)"""
        if protocol not in self.adapters:
            return False, f"未知的协议: {protocol}"

        # 获取或创建此bot_id的锁
        with self._locks_lock:
            if bot_id not in self._start_locks:
                self._start_locks[bot_id] = threading.Lock()
            bot_lock = self._start_locks[bot_id]

        # 使用bot特定的锁防止并发启动
        with bot_lock:
            # 再次检查，因为可能在等待锁时另一个线程已启动
            if bot_id in self.running_adapters:
                # 如果已有适配器运行，且当前传入message_handler，需要更新
                existing_adapter = self.running_adapters[bot_id]

                if message_handler and not existing_adapter.message_handler:
                    # 更新message_handler而不是重启
                    try:
                        from Core.logging.file_logger import log_info
                        log_info(bot_id, f"⚙️ 为已运行的适配器设置message_handler", "ADAPTER_HANDLER_SET",
                                 adapter_id=id(existing_adapter))
                    except ImportError:
                        pass
                    existing_adapter.set_message_handler(message_handler)
                    return True, ""
                else:
                    # 适配器已运行且配置完整，跳过
                    try:
                        from Core.logging.file_logger import log_debug
                        log_debug(bot_id, "适配器已运行，跳过重复启动", "ADAPTER_ALREADY_RUNNING",
                                  adapter_id=id(existing_adapter))
                    except ImportError:
                        pass
                    return True, ""

            try:
                adapter_class = self.adapters[protocol]
                adapter = adapter_class(bot_id, config)

                if message_handler:
                    adapter.set_message_handler(message_handler)

                success = adapter.start()
                if success:
                    self.running_adapters[bot_id] = adapter
                    return True, ""
                else:
                    # 获取适配器的错误信息
                    error_message = getattr(adapter, 'last_error', None) or "适配器启动失败"
                    return False, error_message

            except Exception as e:
                return False, str(e)

    def stop_adapter(self, bot_id: int) -> bool:
        """停止适配器"""
        if bot_id not in self.running_adapters:
            return True

        adapter = self.running_adapters[bot_id]
        success = adapter.stop()

        if success:
            del self.running_adapters[bot_id]

        return success

    def get_adapter_status(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """获取适配器状态"""
        if bot_id not in self.running_adapters:
            return None

        adapter = self.running_adapters[bot_id]
        return adapter.get_status()

    def get_running_adapters(self) -> Dict[int, str]:
        """获取正在运行的适配器"""
        return {
            bot_id: adapter.get_protocol_name()
            for bot_id, adapter in self.running_adapters.items()
        }


def _load_adapter_modules():
    """
    加载所有适配器模块，触发注册
    
    扫描 Adapters 目录，导入所有 adapter.py 模块
    """
    import os

    adapters_dir = os.path.dirname(os.path.abspath(__file__))

    # QQ适配器
    try:
        from .qq.adapter import QQAdapter
        _adapter_registry['qq'] = QQAdapter
    except ImportError as e:
        from Core.logging.file_logger import log_warn
        log_warn(0, f"无法导入QQ适配器: {e}", "ADAPTER_IMPORT_ERROR")

    # OneBot适配器
    try:
        from .onebot.v11.adapter import OneBotAdapter
        _adapter_registry['onebot'] = OneBotAdapter
    except ImportError as e:
        from Core.logging.file_logger import log_warn
        log_warn(0, f"无法导入OneBot适配器: {e}", "ADAPTER_IMPORT_ERROR")


def _register_adapters_to_instance(manager_instance):
    """将所有已注册的适配器添加到管理器实例"""
    from Core.logging.file_logger import log_info, log_error, log_debug

    log_debug(0, "开始注册适配器", "ADAPTER_REGISTER_START")

    # 加载适配器模块
    _load_adapter_modules()

    log_debug(0, f"适配器模块加载完成，注册表: {list(_adapter_registry.keys())}",
              "ADAPTER_MODULES_LOADED")

    # 注册到管理器
    registered_count = 0
    for protocol_name, adapter_class in _adapter_registry.items():
        try:
            manager_instance.register_adapter(protocol_name, adapter_class)
            registered_count += 1
            log_debug(0, f"适配器注册成功: {protocol_name} -> {adapter_class.__name__}",
                      "ADAPTER_REGISTERED_SUCCESS")
        except Exception as e:
            log_error(0, f"注册适配器失败: {protocol_name}", "ADAPTER_REGISTER_ERROR",
                      error=str(e))

    if registered_count > 0:
        log_info(0, f"✅ 成功注册 {registered_count} 个适配器", "ADAPTERS_REGISTERED",
                 count=registered_count,
                 protocols=list(_adapter_registry.keys()))
    else:
        log_error(0, "⚠️ 没有成功注册任何适配器", "NO_ADAPTERS_REGISTERED")


# 全局适配器管理器
_manager_instance = None
_manager_lock = threading.Lock()


def get_adapter_manager() -> AdapterManager:
    """获取适配器管理器单例"""
    global _manager_instance

    if _manager_instance is None:
        with _manager_lock:
            if _manager_instance is None:
                _manager_instance = AdapterManager()
                # 注册适配器到新实例
                _register_adapters_to_instance(_manager_instance)

    return _manager_instance


__all__ = [
    'BaseAdapter', 'BaseBot', 'BaseEvent', 'BaseMessage', 'BaseMessageSegment',
    'AdapterManager', 'get_adapter_manager'
]
