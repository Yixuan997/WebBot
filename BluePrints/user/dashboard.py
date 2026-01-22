"""
@Project：WebBot 
@File   ：dashboard.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 15:00
"""

from flask import render_template, session, redirect, url_for

from Models import User, Bot, System, UserWorkflow


def dashboard():
    """用户中心概览仪表盘"""
    # 获取当前用户
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    # 获取用户的机器人统计
    user_bots = Bot.query.filter_by(owner_id=user_id).all()
    bot_count = len(user_bots)

    # 统计机器人状态
    running_bots = sum(1 for bot in user_bots if bot.is_running)
    stopped_bots = sum(1 for bot in user_bots if not bot.is_running)

    # 获取系统信息
    system = System.query.first()

    # 统计用户订阅的工作流数量
    workflows_count = UserWorkflow.query.filter_by(
        user_id=user_id,
        enabled=True
    ).count()

    # 准备统计数据
    stats = {
        'total_bots': bot_count,
        'running_bots': running_bots,
        'stopped_bots': stopped_bots,
        'workflows_count': workflows_count,
    }

    return render_template('user/dashboard.html',
                           user=user,
                           stats=stats,
                           recent_bots=user_bots[:5],  # 最近的5个机器人
                           system=system)
