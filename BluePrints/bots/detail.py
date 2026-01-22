"""
@Project：WebBot 
@File   ：detail.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 00:15 

机器人详情功能
"""

from flask import render_template, abort, g

from Models import Bot


def bot_detail(bot_id):
    """机器人详情"""
    bot = Bot.query.filter_by(id=bot_id, owner_id=g.user.id).first()
    if not bot:
        abort(404)
    return render_template('bots/detail.html', bot=bot)
