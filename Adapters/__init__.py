"""
适配器模块 - 新架构
支持多种协议的统一适配器架构
"""

import importlib
import pkgutil
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
            log_info(0, f" 适配器已注册: {adapter_class.__name__}", "ADAPTER_REGISTERED",
                     protocol=protocol_name)
        except ImportError:
            pass

    def get_available_protocols(self) -> List[str]:
        """获取可用的协议列表"""
        return list(self.adapters.keys())

    def get_adapter_class(self, protocol_name: str) -> Optional[type]:
        """获取协议对应的适配器类"""
        return self.adapters.get(protocol_name)

    def get_protocol_meta(self, protocol_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取协议元数据

        Args:
            protocol_name: 指定协议，None 表示返回全部
        """
        def _meta(adapter_class: type) -> Dict[str, Any]:
            return {
                "id": adapter_class.get_protocol_id(),
                "name": adapter_class.get_display_name(),
                "message_types": sorted(adapter_class.get_supported_message_types()),
                "webhook_path": adapter_class.get_webhook_path(),
                "webhook_handler": adapter_class.get_webhook_handler(),
                "config_fields": adapter_class.get_bot_config_fields(),
                "required_fields": adapter_class.get_required_config_fields(),
                "startup_error_hint": adapter_class.get_startup_error_hint(),
            }

        if protocol_name:
            adapter_class = self.adapters.get(protocol_name)
            if not adapter_class:
                return {}
            return _meta(adapter_class)

        result = {}
        for protocol, adapter_class in self.adapters.items():
            result[protocol] = _meta(adapter_class)
        return result

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
                        log_info(bot_id, f" 为已运行的适配器设置message_handler", "ADAPTER_HANDLER_SET",
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
    from Core.logging.file_logger import log_debug, log_warn

    _adapter_registry.clear()
    package_name = __name__

    for module_info in pkgutil.iter_modules(__path__):
        module_name = module_info.name
        if module_name.startswith("_") or module_name == "base":
            continue

        full_module_name = f"{package_name}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
        except Exception as e:
            log_warn(0, f"无法导入适配器模块 {full_module_name}: {e}", "ADAPTER_IMPORT_ERROR")
            continue

        setup = getattr(module, "setup", None)
        if callable(setup):
            try:
                setup(_adapter_registry)
                log_debug(0, f"适配器模块注册成功: {full_module_name}", "ADAPTER_MODULE_SETUP_OK")
            except Exception as e:
                log_warn(0, f"适配器模块 setup 执行失败 {full_module_name}: {e}", "ADAPTER_SETUP_ERROR")
            continue

        log_warn(
            0,
            f"适配器模块缺少 setup()，已跳过注册: {full_module_name}",
            "ADAPTER_MODULE_SETUP_MISSING",
        )


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
        log_info(0, f" 成功注册 {registered_count} 个适配器", "ADAPTERS_REGISTERED",
                 count=registered_count,
                 protocols=list(_adapter_registry.keys()))
    else:
        log_error(0, " 没有成功注册任何适配器", "NO_ADAPTERS_REGISTERED")


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
