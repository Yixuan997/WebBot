"""
邮件服务系统

提供邮件发送功能：
- 发送验证码邮件
- 验证邮箱验证码
- 发送通知邮件
"""
from flask import Blueprint

from .service import send_email_service, verify_code, send_verification_code

# 创建邮件服务蓝图
email_bp = Blueprint('email', __name__, url_prefix='/email')

# 添加路由
email_bp.add_url_rule('/send', view_func=send_email_service, methods=['POST'], endpoint='send')
email_bp.add_url_rule('/verify', view_func=verify_code, methods=['POST'], endpoint='verify')
email_bp.add_url_rule('/send-code', view_func=send_verification_code, methods=['POST'],
                      endpoint='send_verification_code')
