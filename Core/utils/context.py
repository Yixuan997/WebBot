"""
Flask 应用上下文管理工具

统一管理 app context，避免重复代码
"""
from functools import wraps
from contextlib import contextmanager
from typing import Optional, Any, Callable

# 全局 Flask app 引用
_app = None


def init_app(app) -> None:
    """
    初始化 app 引用
    
    在 Flask app 创建后调用此函数
    
    Args:
        app: Flask 应用实例
    """
    global _app
    _app = app


def get_app():
    """
    获取 Flask app 实例
    
    Returns:
        Flask app 或 None
    """
    return _app


@contextmanager
def app_context():
    """
    上下文管理器：自动管理 app context
    
    Usage:
        with app_context():
            result = UserWorkflow.query.filter_by(...).all()
    
    如果 app 未初始化，直接执行不推入上下文
    """
    global _app
    
    if _app is None:
        # 尝试从 app 模块导入
        try:
            from app import app as flask_app
            _app = flask_app
        except ImportError:
            pass
    
    if _app:
        ctx = _app.app_context()
        ctx.push()
        try:
            yield _app
        finally:
            ctx.pop()
    else:
        yield None


def with_app_context(func: Callable) -> Callable:
    """
    装饰器：自动管理 app context（同步函数）
    
    Usage:
        @with_app_context
        def my_func():
            return UserWorkflow.query.all()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with app_context():
            return func(*args, **kwargs)
    return wrapper


def with_app_context_async(func: Callable) -> Callable:
    """
    装饰器：自动管理 app context（异步函数）
    
    Usage:
        @with_app_context_async
        async def my_async_func():
            return UserWorkflow.query.all()
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        with app_context():
            return await func(*args, **kwargs)
    return wrapper


def run_with_context(func: Callable, *args, **kwargs) -> Any:
    """
    在 app context 中执行函数
    
    Args:
        func: 要执行的函数
        *args: 位置参数
        **kwargs: 关键字参数
        
    Returns:
        函数返回值
    """
    with app_context():
        return func(*args, **kwargs)
