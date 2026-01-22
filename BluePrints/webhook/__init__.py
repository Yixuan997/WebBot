"""
多协议Webhook蓝图
支持QQ、微信、钉钉等多种协议的Webhook回调
"""

from flask import Blueprint

from .qq import handle_qq_webhook

# 创建webhook蓝图
webhook_bp = Blueprint('webhook', __name__, url_prefix='/webhook')

# QQ协议路由
webhook_bp.add_url_rule('/qq', view_func=handle_qq_webhook, methods=['POST'], endpoint='qq_webhook')
