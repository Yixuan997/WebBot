"""
@Project：WebBot 
@File   ：dashboard.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:55 
"""
import platform
import threading
import time
from datetime import datetime

import psutil
import pytz
from flask import render_template, __version__

from Database.Redis.client import get_redis_info, get_redis_stats, get_redis_keys_info
from Models import User, db
from Models.SQL.Bot import Bot

# 全局变量
cpu_usage_global = 0
CPU_UPDATE_INTERVAL = 5  # CPU更新间隔（秒）
last_cpu_update = 0  # 上次更新时间


def update_cpu_usage():
    """
    后台更新 CPU 使用率
    这个函数在一个单独的线程中运行，每5秒更新一次 CPU 使用率
    同时实现了平滑处理，避免数值跳动过大
    """
    global cpu_usage_global, last_cpu_update

    def get_smoothed_cpu_usage():
        """获取平滑处理后的CPU使用率"""
        # 收集3次样本取平均值
        samples = []
        for _ in range(3):
            samples.append(psutil.cpu_percent(interval=0.5))
        return sum(samples) / len(samples)

    while True:
        try:
            current_time = time.time()
            if current_time - last_cpu_update >= CPU_UPDATE_INTERVAL:
                cpu_usage_global = get_smoothed_cpu_usage()
                last_cpu_update = current_time
            time.sleep(1)  # 短暂休眠避免CPU占用
        except Exception as e:
            time.sleep(CPU_UPDATE_INTERVAL)


# 启动后台线程来持续更新 CPU 使用率
cpu_monitor_thread = threading.Thread(
    target=update_cpu_usage,
    daemon=True,
    name="CPUMonitor"
)
cpu_monitor_thread.start()


def get_uptime():
    """
    获取系统运行时间
    :return: 格式化的运行时间字符串，如 "3天5小时"
    """
    boot_time = psutil.boot_time()
    uptime = datetime.now() - datetime.fromtimestamp(boot_time)
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    return f"{days}天{hours}小时"


def dashboard():
    """管理员仪表盘"""
    # 获取用户统计
    user_count = User.query.count()

    # 获取北京时间的今天0点
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.now(beijing_tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 统计今天新增的用户
    new_users_today = User.query.filter(
        User.registered_on >= today_start
    ).count()

    # 获取机器人数据
    bots = Bot.query.order_by(Bot.created_at.desc()).all()

    # 统计机器人状态（使用数据库中的is_running字段）
    running_bots_count = Bot.query.filter_by(is_running=True).count()

    # 系统资源使用情况
    memory = psutil.virtual_memory()
    memory_usage = memory.percent

    # 根据操作系统选择磁盘路径
    import os
    disk_path = 'C:\\' if os.name == 'nt' else '/'
    disk = psutil.disk_usage(disk_path)
    disk_usage = disk.percent
    uptime = get_uptime()

    # 版本信息
    python_version = platform.python_version()
    flask_version = __version__

    # 数据库连接状态
    db_engine = db.engine
    db_active_connections = db_engine.pool.checkedout() if hasattr(db_engine, 'pool') else 0
    db_max_connections = db_engine.pool.size() if hasattr(db_engine, 'pool') else 1
    db_usage_percent = (db_active_connections / db_max_connections * 100) if db_max_connections else 0

    # 获取Redis信息
    redis_info = get_redis_info()
    redis_stats = get_redis_stats()
    redis_keys = get_redis_keys_info()

    # 使用连接池配置的最大连接数
    redis_max_connections = redis_info['pool_max_connections']
    redis_current_connections = redis_info.get('connected_clients', 0)
    redis_server_max_clients = redis_info['max_clients']

    # 计算连接池使用率
    redis_usage_percent = min((redis_current_connections / redis_max_connections * 100), 100)

    # 获取浏览器管理器状态
    browser_status = None
    try:
        from Core.tools.browser import browser
        browser_status = browser.get_status()
    except Exception as e:
        browser_status = {
            'is_running': False,
            'render_count': 0,
            'uptime': '未知',
            'error': str(e)
        }

    return render_template(
        'admin/dashboard.html',
        user_count=user_count,
        new_users_today=new_users_today,
        bots=bots,  # 添加机器人数据
        running_bots_count=running_bots_count,  # 运行中的机器人数量
        cpu_usage=round(cpu_usage_global, 2),
        memory_usage=round(memory_usage, 2),
        disk_usage=round(disk_usage, 2),
        uptime=uptime,
        python_version=python_version,
        flask_version=flask_version,
        db_active_connections=db_active_connections,
        db_max_connections=db_max_connections,
        db_usage_percent=round(db_usage_percent, 2),
        redis_info=redis_info,
        redis_stats=redis_stats,
        redis_keys=redis_keys,
        redis_current_connections=redis_current_connections,
        redis_max_connections=redis_max_connections,
        redis_usage_percent=round(redis_usage_percent, 2),
        browser_status=browser_status,  # 添加浏览器状态

    )
