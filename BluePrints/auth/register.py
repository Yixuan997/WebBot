"""
@Project：WebBot
@File   ：register.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/7 00:10

用户注册功能
"""
from flask import render_template, request, flash, redirect, url_for
from werkzeug.security import generate_password_hash

from Database.Redis import get_value, get_redis, delete_key
from Models import User, db, time_format


# 注册
def register():
    if request.method == 'POST':
        # 获取表单数据
        name = request.form.get('name')  # 用户名
        email = request.form.get('email')  # 邮箱
        password = request.form.get('password')  # 密码
        qq = request.form.get('qq')  # qq
        captcha = request.form.get('code', '').lower()  # 验证码
        captcha_id = request.form.get('captcha_id')  # 验证码ID
        email_code = request.form.get('email_code')  # 邮箱验证码

        # 验证验证码
        try:
            # 从Redis获取存储的验证码
            stored_captcha = get_value(f'captcha:{captcha_id}')
            if stored_captcha:
                # 统一转换为小写进行比较
                stored_captcha = stored_captcha.decode().lower() if isinstance(stored_captcha,
                                                                               bytes) else stored_captcha.lower()
                # 验证完成后立即删除验证码，防止重复使用
                with get_redis() as redis:
                    redis.delete(f'captcha:{captcha_id}')
            else:
                # 验证码不存在或已过期
                flash('验证码已过期，请重新获取', 'warning')
                return render_template('auth/register.html')

            # 验证码匹配检查
            if captcha != stored_captcha:
                flash('验证码错误！', 'danger')
                return render_template('auth/register.html')
        except Exception:
            # Redis服务异常处理
            flash('验证码服务暂时不可用，请稍后重试', 'warning')
            return render_template('auth/register.html')

        # 验证邮箱验证码
        try:
            # 从Redis获取邮箱验证码
            email_verification_key = f'email_verification:register:{email}'
            stored_email_code = get_value(email_verification_key)

            if not stored_email_code:
                flash('邮箱验证码已过期，请重新获取', 'warning')
                return render_template('auth/register.html')

            # 处理bytes类型
            if isinstance(stored_email_code, bytes):
                stored_email_code = stored_email_code.decode()

            if email_code != str(stored_email_code):
                flash('邮箱验证码错误！', 'danger')
                return render_template('auth/register.html')

            # 验证成功，删除验证码
            delete_key(email_verification_key)

        except Exception as e:
            flash('邮箱验证码验证失败，请重试', 'warning')
            return render_template('auth/register.html')

        # 表单数据验证
        if not all([name, email, password, qq, email_code]):
            flash('请填写所有必填字段！', 'warning')
            return render_template('auth/register.html')

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')  # 使用正确的哈希方法

        # 检查用户名是否已存在
        existing_user_name = User.query.filter_by(username=name).first()
        if existing_user_name:
            flash('用户名已存在！', 'warning')
            return render_template('auth/register.html')

        # 检查邮箱是否已存在
        existing_user_email = User.query.filter_by(email=email).first()
        if existing_user_email:
            flash('邮箱已注册！', 'warning')
            return render_template('auth/register.html')

        # 检查QQ号是否已存在
        existing_user_qq = User.query.filter_by(qq=qq).first()
        if existing_user_qq:
            flash('QQ号已注册！', 'warning')
            return render_template('auth/register.html')

        # 创建新用户实例
        try:
            new_user = User(
                username=name,
                email=email,
                password=hashed_password,
                qq=qq,
                vip=False,
                registered_on=time_format()
            )

        except Exception as e:
            flash('注册失败！', 'danger')
            return render_template('auth/register.html')

        try:
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功！', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('注册失败！', 'danger')
            return render_template('auth/register.html')
    else:
        return render_template('auth/register.html')
