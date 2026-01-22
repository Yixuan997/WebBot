"""
@Project：WebBot 
@File   ：Extensions.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:51 
"""
from datetime import datetime, timezone

import pytz
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# 将UTC时间转换为本地时间并格式化
def time_format(timestamp=None, target_timezone_str='Asia/Shanghai', format_str='%Y-%m-%d %H:%M:%S'):
    """
    将给定的timestamp转换为目标时区并格式化为字符串。

    :param timestamp: 原始的datetime对象（最好是UTC时间）
    :param target_timezone_str: 目标时区的字符串标识符，默认为'Asia/Shanghai'
    :param format_str: 格式化字符串，默认为'%Y-%m-%d %H:%M:%S'，即年月日时分秒
    :return: 转换时区并格式化后的时间字符串
    """
    if timestamp is None:
        # 使用 datetime.now(timezone.utc) 而不是废弃的 datetime.utcnow()
        timestamp = datetime.now(timezone.utc).replace(tzinfo=None)

    # 将UTC时间转换为目标时区
    target_timezone = pytz.timezone(target_timezone_str)
    local_time = timestamp.replace(tzinfo=pytz.utc).astimezone(target_timezone)

    # 去除微秒以确保精度到秒
    local_time = local_time.replace(microsecond=0)

    return local_time


def get_current_time(timezone_str='Asia/Shanghai'):
    """
    获取当前本地时间

    :param timezone_str: 时区字符串标识符，默认为'Asia/Shanghai'
    :return: 当前本地时间的datetime对象
    """
    target_timezone = pytz.timezone(timezone_str)
    # 使用 datetime.now(timezone.utc) 而不是废弃的 datetime.utcnow()
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    local_time = utc_now.replace(tzinfo=pytz.utc).astimezone(target_timezone)
    # 去除时区信息，返回naive datetime对象，与数据库兼容
    return local_time.replace(tzinfo=None)
