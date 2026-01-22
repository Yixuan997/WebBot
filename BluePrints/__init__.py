"""
@Project ：WebBot
@File    ：__init__.py
@IDE     ：PyCharm
@Author  ：杨逸轩
@Date    ：2025-6-6 14:17
"""
from .admin import Admin_bp
from .auth import auth_bp
from .bots import bots_bp
from .docs import docs_bp
from .email import email_bp
from .main import main_bp
from .user import user_bp
from .webhook import webhook_bp


def register_blueprints(app):
    # 注册蓝图
    app.register_blueprint(auth_bp)  # 权限
    app.register_blueprint(bots_bp)  # 主
    app.register_blueprint(Admin_bp)  # 后台管理
    app.register_blueprint(main_bp)  # 主页面
    app.register_blueprint(docs_bp)  # 文档系统
    app.register_blueprint(webhook_bp)  # Webhook
    app.register_blueprint(email_bp)  # 邮件服务
    app.register_blueprint(user_bp)  # 用户中心
