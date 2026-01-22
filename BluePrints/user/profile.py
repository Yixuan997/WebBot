"""
@Project：WebBot 
@File   ：profile.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 15:00
"""

from flask import render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from Models import User, System, db


def profile():
    """个人资料页面"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    system = System.query.first()
    return render_template('user/profile.html', user=user, system=system)


def update_profile():
    """更新个人资料"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        flash('用户未登录', 'danger')
        return redirect(url_for('auth.login'))

    try:
        # 获取表单数据
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        qq = request.form.get('qq', '').strip()

        # 验证数据
        if not username:
            flash('用户名不能为空', 'warning')
            return redirect(url_for('user.profile'))

        if not email:
            flash('邮箱不能为空', 'warning')
            return redirect(url_for('user.profile'))

        # 检查用户名是否被其他用户使用
        existing_user = User.query.filter(User.username == username, User.id != user_id).first()
        if existing_user:
            flash('用户名已被使用', 'warning')
            return redirect(url_for('user.profile'))

        # 检查邮箱是否被其他用户使用
        existing_email = User.query.filter(User.email == email, User.id != user_id).first()
        if existing_email:
            flash('邮箱已被使用', 'warning')
            return redirect(url_for('user.profile'))

        # 更新用户信息
        user.username = username
        user.email = email
        if qq:
            user.qq = qq

        db.session.commit()

        flash('个人资料更新成功', 'success')
        return redirect(url_for('user.profile'))

    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'danger')
        return redirect(url_for('user.profile'))


def change_password():
    """修改密码"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        flash('用户未登录', 'danger')
        return redirect(url_for('auth.login'))

    try:
        # 获取表单数据
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # 验证当前密码
        if not check_password_hash(user.password, current_password):
            flash('当前密码错误', 'warning')
            return redirect(url_for('user.profile'))

        # 验证新密码
        if len(new_password) < 6:
            flash('新密码长度不能少于6位', 'warning')
            return redirect(url_for('user.profile'))

        if new_password != confirm_password:
            flash('两次输入的密码不一致', 'warning')
            return redirect(url_for('user.profile'))

        # 更新密码
        user.password = generate_password_hash(new_password)
        db.session.commit()

        flash('密码修改成功', 'success')
        return redirect(url_for('user.profile'))

    except Exception as e:
        db.session.rollback()
        flash(f'修改失败：{str(e)}', 'danger')
        return redirect(url_for('user.profile'))
