"""
多协议Webhook蓝图
支持按协议适配器自动注册Webhook回调路由。
"""

import importlib

from flask import Blueprint

from Adapters import get_adapter_manager

# 创建 webhook 蓝图
webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')


def _import_callable(path: str):
    """
    从完整路径导入可调用对象

    例: "BluePrints.webhook.qq.handle_qq_webhook"
    """
    if not path or "." not in path:
        raise ValueError(f"无效的 callable 路径: {path}")
    module_path, attr_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    view_func = getattr(module, attr_name)
    if not callable(view_func):
        raise ValueError(f"目标不是可调用对象: {path}")
    return view_func


def _register_webhook_routes():
    """按适配器元数据自动注册 webhook 路由"""
    manager = get_adapter_manager()
    for protocol, adapter_class in manager.adapters.items():
        webhook_path = adapter_class.get_webhook_path()
        webhook_handler = adapter_class.get_webhook_handler()

        if not webhook_path or not webhook_handler:
            continue

        view_func = _import_callable(webhook_handler)
        endpoint = f"{protocol}_webhook"
        webhook_bp.add_url_rule(
            f"/{webhook_path}",
            view_func=view_func,
            methods=['POST'],
            endpoint=endpoint
        )


_register_webhook_routes()

