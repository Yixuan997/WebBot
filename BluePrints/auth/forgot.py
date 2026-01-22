"""
@Project：WebBot
@File   ：forgot.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/15 13:00
"""

from flask import render_template, request, flash, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash

from Database.Redis import get_value, delete_key
from Models import User, db


def forgot_password():
    """找回密码页面"""
    if request.method == 'GET':
        return render_template('auth/forgot.html')

    elif request.method == 'POST':
        # 获取表单数据
        email = request.form.get('email')
        email_code = request.form.get('email_code')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        captcha = request.form.get('code', '').lower()
        captcha_id = request.form.get('captcha_id')

        # 表单数据验证
        if not all([email, email_code, new_password, confirm_password, captcha]):
            flash('请填写所有必填字段！', 'warning')
            return render_template('auth/forgot.html')

        # 验证图片验证码
        try:
            stored_captcha = get_value(f'captcha:{captcha_id}')
            if not stored_captcha:
                flash('验证码已过期，请重新获取', 'warning')
                return render_template('auth/forgot.html')

            stored_captcha = stored_captcha.decode() if isinstance(stored_captcha, bytes) else stored_captcha

            if captcha != str(stored_captcha).lower():
                flash('图片验证码错误！', 'danger')
                return render_template('auth/forgot.html')

            # 验证成功，删除验证码
            delete_key(f'captcha:{captcha_id}')

        except Exception:
            flash('验证码服务暂时不可用，请稍后重试', 'warning')
            return render_template('auth/forgot.html')

        # 验证邮箱验证码
        try:
            email_verification_key = f'email_verification:reset_password:{email}'
            stored_email_code = get_value(email_verification_key)

            if not stored_email_code:
                flash('邮箱验证码已过期，请重新获取', 'warning')
                return render_template('auth/forgot.html')

            if isinstance(stored_email_code, bytes):
                stored_email_code = stored_email_code.decode()

            if email_code != str(stored_email_code):
                flash('邮箱验证码错误！', 'danger')
                return render_template('auth/forgot.html')

            # 验证成功，删除验证码
            delete_key(email_verification_key)

        except Exception:
            flash('邮箱验证码验证失败，请重试', 'warning')
            return render_template('auth/forgot.html')

        # 验证密码
        if new_password != confirm_password:
            flash('两次输入的密码不一致！', 'danger')
            return render_template('auth/forgot.html')

        if len(new_password) < 6:
            flash('密码长度不能少于6位！', 'warning')
            return render_template('auth/forgot.html')

        # 检查用户是否存在
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('该邮箱未注册！', 'danger')
            return render_template('auth/forgot.html')

        try:
            # 更新密码
            user.password = generate_password_hash(new_password)
            db.session.commit()

            flash('密码重置成功！请使用新密码登录。', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('密码重置失败，请重试！', 'danger')
            return render_template('auth/forgot.html')


def check_email_exists():
    """检查邮箱是否存在"""
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return jsonify({'success': False, 'message': '邮箱地址不能为空'})

        # 检查邮箱是否存在
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'success': False, 'message': '该邮箱未注册'})

        return jsonify({'success': True, 'message': '邮箱验证通过', 'username': user.username})

    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败：{str(e)}'})
