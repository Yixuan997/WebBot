"""
@Project：WebBot
@File   ：__init__.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/7 00:10

认证蓝图
"""

from flask import Blueprint

from .captcha import generate_captcha
from .forgot import forgot_password, check_email_exists
from .login import login
from .logout import logout
from .register import register

# 创建auth蓝图
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 添加路由
auth_bp.add_url_rule('/login', view_func=login, methods=['GET', 'POST'], endpoint='login')
auth_bp.add_url_rule('/register', view_func=register, methods=['GET', 'POST'], endpoint='register')
auth_bp.add_url_rule('/logout', view_func=logout, methods=['GET', 'POST'], endpoint='logout')
auth_bp.add_url_rule('/captcha', view_func=generate_captcha, methods=['GET'], endpoint='captcha')
auth_bp.add_url_rule('/forgot', view_func=forgot_password, methods=['GET', 'POST'], endpoint='forgot')
auth_bp.add_url_rule('/check_email', view_func=check_email_exists, methods=['POST'], endpoint='check_email')
