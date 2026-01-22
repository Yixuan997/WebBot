"""
@Project：WebBot 
@File   ：utils.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:59 
"""
from functools import wraps

from flask import flash, redirect, url_for, render_template, g


# 角色权限验证
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查用户是否登录
            if not hasattr(g, 'user') or g.user is None:
                flash('请先登录。', 'warning')
                return redirect(url_for('auth.login'))

            user = g.user
            if role == 'admin' and user.role != 'admin':
                return render_template('error.html', code='403', error='您没有权限访问此页面！'), 403
            elif role == 'user' and user.role not in ['user', 'admin']:
                return render_template('error.html', code='403', error='您没有权限访问此页面！'), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def login_required_with_message(message="请先登录"):
    """
    带自定义消息的登录要求装饰器

    Args:
        message (str): 自定义提示消息

    Returns:
        decorator: 装饰器函数
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查用户是否登录
            if not hasattr(g, 'user') or g.user is None:
                flash(message, 'warning')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator
