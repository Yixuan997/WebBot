"""
@Project：WebBot 
@File   ：logout.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 00:10 

用户登出功能
"""

from flask import flash, redirect, url_for, session, g


def logout():
    """用户登出"""
    username = None
    if hasattr(g, 'user') and g.user is not None:
        username = g.user.username

    # 清除会话
    session.pop('user_id', None)

    if username:
        flash(f'再见，{username}！', 'info')
    else:
        flash('您已登出', 'info')

    return redirect(url_for('index'))
