"""
@Project：WebBot 
@File   email.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:55 
"""

from datetime import datetime

from flask import render_template, request, flash, redirect, url_for
from flask_mail import Message

from Models import Email, db
from extensions import mail


# 邮件设置
def email():
    email_config = Email.query.first()

    if request.method == 'POST':
        if not email_config:
            email_config = Email()

        email_config.server = request.form['server']
        email_config.port = int(request.form['port'])
        email_config.user = request.form['user']
        email_config.password = request.form['password']
        email_config.use_tls = 'use_tls' in request.form

        try:
            db.session.add(email_config)
            db.session.commit()
            flash('邮件设置已更新', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'更新邮件设置失败: {str(e)}', 'error')

        return redirect(url_for('Admin.email'))

    return render_template('admin/email.html', email_config=email_config)


# 测试邮件发送
def test_email():
    """测试邮件发送功能"""
    if request.method == 'POST':
        try:
            email_config = Email.query.first()
            if not email_config:
                flash('请先配置邮件服务器', 'warning')
                return redirect(url_for('Admin.email'))

            # 获取测试邮箱
            test_email = request.form.get('test_email')
            if not test_email:
                flash('请输入测试邮箱地址', 'warning')
                return redirect(url_for('Admin.email'))

            # 临时配置Flask-Mail
            from flask import current_app

            # 根据端口自动判断加密方式
            port = email_config.port
            use_ssl = port == 465  # 465端口使用SSL
            use_tls = email_config.use_tls and port != 465  # 587端口使用TLS

            current_app.config.update({
                'MAIL_SERVER': email_config.server,
                'MAIL_PORT': port,
                'MAIL_USE_TLS': use_tls,
                'MAIL_USE_SSL': use_ssl,
                'MAIL_USERNAME': email_config.user,
                'MAIL_PASSWORD': email_config.password,
                'MAIL_DEFAULT_SENDER': email_config.user
            })

            # 重新初始化mail
            mail.init_app(current_app)

            # 发送测试邮件
            msg = Message(
                subject='QQ机器人管理系统 - 邮件测试',
                recipients=[test_email],
                body='这是一封测试邮件，如果您收到此邮件，说明邮件服务器配置正确！',
                html='''
                <h2>QQ机器人管理系统</h2>
                <p>这是一封测试邮件，如果您收到此邮件，说明邮件服务器配置正确！</p>
                <p>发送时间：{}</p>
                <hr>
                <p><small>此邮件由QQ机器人管理系统自动发送</small></p>
                '''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )

            mail.send(msg)
            flash(f'测试邮件发送成功！已发送到 {test_email}，请检查收件箱。', 'success')
            return redirect(url_for('Admin.email'))

        except Exception as e:
            import traceback

            # 根据错误类型提供更具体的建议
            error_msg = str(e)
            if "Connection unexpectedly closed" in error_msg:
                suggestion = "建议检查：1) QQ邮箱使用465端口+SSL 2) 163邮箱使用465端口+SSL 3) Gmail使用587端口+TLS 4) 确保使用授权码而非登录密码"
            elif "Authentication failed" in error_msg or "535" in error_msg:
                suggestion = "认证失败，请检查用户名和密码（授权码）是否正确"
            elif "Connection refused" in error_msg:
                suggestion = "连接被拒绝，请检查SMTP服务器地址和端口是否正确"
            elif "timeout" in error_msg.lower():
                suggestion = "连接超时，请检查网络连接或尝试其他端口"
            else:
                suggestion = "请检查邮件服务器配置是否正确"

            flash(f'邮件发送失败：{error_msg}。{suggestion}', 'danger')
            return redirect(url_for('Admin.email'))

    flash('请求方法错误', 'danger')
    return redirect(url_for('Admin.email'))
