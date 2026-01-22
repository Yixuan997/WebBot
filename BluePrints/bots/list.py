"""
@Project：WebBot 
@File   ：list.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 00:15 

机器人列表功能
"""

from flask import render_template, g

from Models import Bot


def list_bots():
    """机器人列表"""
    bots = Bot.query.filter_by(owner_id=g.user.id).all()
    return render_template('bots/list.html', bots=bots)
