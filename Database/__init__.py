"""
@Project：WebBot 
@File   ：__init__.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/14 23:51 
"""
# 导出 Redis 的功能
from .Redis import init_redis, set_value, get_value, delete_key, get_redis
