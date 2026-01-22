"""
@Project：WebBot
@File   ：login.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/7 00:10
"""
from flask import render_template, request, flash, session, redirect, url_for, g
from werkzeug.security import check_password_hash

from Database.Redis import get_value, get_redis
from Models import User, db, time_format


def login():
    """用户登录"""
    # 检查是否已经登录
    if hasattr(g, 'user') and g.user is not None:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        captcha = request.form.get('code', '').lower().strip()
        captcha_id = request.form.get('captcha_id', '').strip()

        # 验证验证码
        if not captcha or not captcha_id:
            flash('请输入验证码', 'warning')
            return render_template('auth/login.html')

        try:
            # 从Redis获取存储的验证码
            stored_captcha = get_value(f'captcha:{captcha_id}')
            if not stored_captcha:
                flash('验证码已过期，请重新获取', 'warning')
                return render_template('auth/login.html')

            # 统一转换为小写进行比较
            stored_captcha = stored_captcha.decode().lower() if isinstance(stored_captcha,
                                                                           bytes) else stored_captcha.lower()

            # 验证码匹配检查
            if captcha != stored_captcha:
                flash('验证码错误！', 'danger')
                return render_template('auth/login.html')

            # 验证成功后立即删除验证码，防止重复使用
            with get_redis() as redis:
                redis.delete(f'captcha:{captcha_id}')

        except Exception:
            # Redis服务异常处理
            flash('验证码服务暂时不可用，请稍后重试', 'warning')
            return render_template('auth/login.html')

        # 先验证输入是否为空
        if not username or not password:
            flash('请输入用户名和密码', 'warning')
            return render_template('auth/login.html')

        # 验证用户身份
        try:
            user = User.query.filter_by(username=username).first()
            if not user or not check_password_hash(user.password, password):
                flash('用户名或密码错误！', 'warning')
                return render_template('auth/login.html'), 401
        except Exception:
            flash('登录验证失败，请稍后重试', 'error')
            return render_template('auth/login.html'), 500

        try:
            # 设置新的会话数据（不要用 session.clear()，会导致 Flask-Session 丢失数据）
            # 先移除旧的用户数据
            session.pop('user_id', None)
            session.pop('user_role', None)

            # 设置新数据
            session['user_id'] = user.id
            session['user_role'] = user.role
            session.permanent = True  # 设置为永久会话，使用配置的会话时长
            session.modified = True  # 强制标记为已修改

            # 更新用户最后登录时间
            user.last_login = time_format()
            db.session.commit()

            flash('登录成功！', 'success')

            # 根据用户角色重定向到不同页面
            target = url_for('Admin.dashboard') if user.role == 'admin' else url_for('user.dashboard')
            return redirect(target)
        except Exception:
            # 数据库操作异常处理
            db.session.rollback()
            flash('登录过程中出现错误，请重试', 'danger')
            return render_template('auth/login.html')

    return render_template('auth/login.html')


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
