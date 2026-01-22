"""
日志工具函数
"""
import traceback


def format_exception(e: Exception) -> str:
    """
    格式化异常信息为字符串
    
    Args:
        e: 异常对象
        
    Returns:
        str: 格式化后的异常堆栈信息
    """
    return ''.join(traceback.format_exception(type(e), e, e.__traceback__))
