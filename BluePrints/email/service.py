"""
@Project：WebBot 
@File   ：mail_service.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 12:30
"""
import random
import string
from datetime import datetime

from flask import request, jsonify, render_template
from flask_mail import Message

from Database.Redis import set_value, get_value, delete_key
from Models import Email


def get_email_config():
    """获取邮件配置"""
    email_config = Email.query.first()
    if not email_config:
        return None
    return email_config


def get_mail_config():
    """获取邮件配置，返回配置字典"""
    email_config = get_email_config()
    if not email_config:
        return None

    # 🔧 修复：根据端口自动判断加密方式（与后台测试邮件保持一致）
    port = email_config.port
    use_ssl = port == 465  # 465端口使用SSL
    use_tls = email_config.use_tls and port != 465  # 587端口使用TLS

    return {
        'MAIL_SERVER': email_config.server,
        'MAIL_PORT': port,
        'MAIL_USE_TLS': use_tls,
        'MAIL_USE_SSL': use_ssl,
        'MAIL_USERNAME': email_config.user,
        'MAIL_PASSWORD': email_config.password,
        'MAIL_DEFAULT_SENDER': email_config.user
    }


def generate_verification_code(length=6):
    """生成验证码"""
    return ''.join(random.choices(string.digits, k=length))


def send_email(to_email, subject, body, html=None):
    """发送邮件的通用方法"""
    try:
        # 🔧 获取邮件配置
        mail_config = get_mail_config()
        if not mail_config:
            return False, "邮件服务未配置"

        # 🔧 使用临时配置覆盖发送邮件
        from flask import current_app

        # 保存当前配置
        original_config = {}
        for key in mail_config:
            original_config[key] = current_app.config.get(key)

        try:
            # 临时更新配置
            current_app.config.update(mail_config)

            # 创建新的Mail实例用于发送
            from flask_mail import Mail
            temp_mail = Mail()
            temp_mail.init_app(current_app)

            msg = Message(
                subject=subject,
                recipients=[to_email],
                body=body,
                html=html
            )

            temp_mail.send(msg)
            return True, "邮件发送成功"

        finally:
            # 恢复原始配置
            current_app.config.update(original_config)

    except Exception as e:
        return False, f"邮件发送失败：{str(e)}"


def send_email_service():
    """统一的邮件发送服务"""
    try:
        data = request.get_json()
        email = data.get('email')
        email_type = data.get('type')  # verification, notification

        if not email:
            return jsonify({'success': False, 'message': '邮箱地址不能为空'})

        if not email_type:
            return jsonify({'success': False, 'message': '邮件类型不能为空'})

        # 检查邮件配置
        if not get_email_config():
            return jsonify({'success': False, 'message': '邮件服务未配置，请联系管理员'})

        if email_type == 'verification':
            return _send_verification_email(email, data)
        elif email_type == 'notification':
            return _send_notification_email(email, data)
        else:
            return jsonify({'success': False, 'message': '未知的邮件类型'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'发送失败：{str(e)}'})


def send_verification_code():
    """发送验证码 - 仅支持Ajax请求"""
    try:
        if request.method == 'POST':
            # 从JSON获取数据
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'message': '请求数据格式错误'})

            email = data.get('email')
            purpose = data.get('purpose', 'register')

            if not email:
                return jsonify({'success': False, 'message': '邮箱地址不能为空'})

            # 简单的邮箱格式验证
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_regex, email):
                return jsonify({'success': False, 'message': '请输入正确的邮箱格式'})

            # 检查邮件配置
            if not get_email_config():
                return jsonify({'success': False, 'message': '邮件服务未配置，请联系管理员'})

            # 发送验证码
            data = {'purpose': purpose}
            result = _send_verification_email(email, data)
            return result

    except Exception as e:
        return jsonify({'success': False, 'message': f'发送失败：{str(e)}'})


def _send_verification_email(email, data):
    """发送验证码邮件"""
    purpose = data.get('purpose', 'register')  # register, reset_password, change_email

    # 生成验证码
    code = generate_verification_code()

    # 存储到Redis，5分钟过期
    redis_key = f"email_verification:{purpose}:{email}"
    set_value(redis_key, code, 300)

    # 根据用途选择邮件模板
    templates = {
        'register': {
            'subject': 'QQ机器人管理系统 - 注册验证码',
            'title_color': '#059669',
            'bg_color': '#f0fdf4',
            'border_color': '#bbf7d0',
            'title': '注册验证码',
            'description': '您正在注册QQ机器人管理系统账户，请使用以下验证码完成注册：'
        },
        'reset_password': {
            'subject': 'QQ机器人管理系统 - 密码重置验证码',
            'title_color': '#d97706',
            'bg_color': '#fffbeb',
            'border_color': '#fed7aa',
            'title': '密码重置验证码',
            'description': '您正在重置QQ机器人管理系统账户密码，请使用以下验证码完成重置：'
        },
        'change_email': {
            'subject': 'QQ机器人管理系统 - 邮箱变更验证码',
            'title_color': '#2563eb',
            'bg_color': '#eff6ff',
            'border_color': '#bfdbfe',
            'title': '邮箱变更验证码',
            'description': '您正在变更QQ机器人管理系统账户邮箱，请使用以下验证码完成变更：'
        }
    }

    if purpose not in templates:
        return jsonify({'success': False, 'message': '未知的验证码用途'})

    template = templates[purpose]
    subject = template['subject']
    body = f'您的{template["title"]}是：{code}，5分钟内有效。'

    # 使用Tabler风格的HTML模板
    html = render_template('email/verification_code.html',
                           title=template['title'],
                           description=template['description'],
                           code=code,
                           purpose=purpose,
                           title_color=template['title_color'],
                           bg_color=template['bg_color'],
                           border_color=template['border_color'],
                           send_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                           show_button=False
                           )

    # 发送邮件
    success, message = send_email(email, subject, body, html)

    if success:
        return jsonify({
            'success': True,
            'message': '验证码已发送到您的邮箱，请查收',
            'expires_in': 300  # 5分钟
        })
    else:
        return jsonify({'success': False, 'message': message})


def _send_notification_email(email, data):
    """发送通知邮件"""
    subject = data.get('subject')
    content = data.get('content')
    notification_type = data.get('notification_type', 'info')  # info, warning, error, success
    sender = data.get('sender', '系统管理员')
    priority = data.get('priority', '普通')
    actions = data.get('actions', [])  # 操作按钮列表

    if not subject or not content:
        return jsonify({'success': False, 'message': '主题和内容不能为空'})

    # 根据通知类型选择颜色和背景
    type_configs = {
        'info': {
            'color': '#3b82f6',
            'bg_color': '#eff6ff',
            'name': '系统通知'
        },
        'success': {
            'color': '#059669',
            'bg_color': '#f0fdf4',
            'name': '成功通知'
        },
        'warning': {
            'color': '#d97706',
            'bg_color': '#fffbeb',
            'name': '警告通知'
        },
        'error': {
            'color': '#dc2626',
            'bg_color': '#fef2f2',
            'name': '错误通知'
        }
    }

    config = type_configs.get(notification_type, type_configs['info'])

    # 使用Tabler风格的HTML模板
    html = render_template('email/notification.html',
                           subject=subject,
                           content=content,
                           notification_type=notification_type,
                           type_color=config['color'],
                           bg_color=config['bg_color'],
                           type_name=config['name'],
                           sender=sender,
                           priority=priority,
                           actions=actions,
                           send_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                           )

    # 发送邮件
    success, message = send_email(email, f"QQ机器人管理系统 - {subject}", content, html)

    if success:
        return jsonify({'success': True, 'message': '通知邮件发送成功'})
    else:
        return jsonify({'success': False, 'message': message})


def verify_code():
    """验证邮箱验证码"""
    try:
        data = request.get_json()
        email = data.get('email')
        code = data.get('code')
        purpose = data.get('purpose', 'register')

        if not email or not code:
            return jsonify({'success': False, 'message': '邮箱和验证码不能为空'})

        # 从Redis获取验证码
        redis_key = f"email_verification:{purpose}:{email}"
        stored_code = get_value(redis_key)

        if not stored_code:
            return jsonify({'success': False, 'message': '验证码已过期或不存在'})

        # 处理bytes类型
        if isinstance(stored_code, bytes):
            stored_code = stored_code.decode()

        if str(stored_code) != str(code):
            return jsonify({'success': False, 'message': '验证码错误'})

        # 验证成功，删除验证码
        delete_key(redis_key)

        return jsonify({'success': True, 'message': '验证码验证成功'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败：{str(e)}'})
