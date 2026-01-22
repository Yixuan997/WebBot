"""
@Project：WebBot 
@File   ：users.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 09:57 
"""
from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import or_

from Models import User, db
from utils.page_utils import adapt_pagination


# 用户列表
def users():
    # 列出所有用户
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('search', '')

    query = User.query
    if search:
        query = query.filter(or_(
            User.username.contains(search),
            User.email.contains(search),
            User.qq.contains(search)
        ))

    pagination = query.order_by(User.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    users_list = pagination.items

    # 使用我们的智能分页适配器
    page_numbers = adapt_pagination(pagination)

    return render_template('admin/users.html',
                           users=users_list,
                           pagination=pagination,
                           page_numbers=page_numbers,
                           current_page=pagination.page,
                           total_pages=pagination.pages,
                           search=search)


# 编辑用户
def edit_user(user_id):
    user = User.query.get(session['user_id'])
    edit_user = User.query.get_or_404(user_id)

    if request.method == 'GET':
        return render_template('admin/edit_user.html', edit_user=edit_user, user=user)

    elif request.method == 'POST':
        # 更新用户信息
        edit_user.username = request.form['username']
        edit_user.email = request.form['email']
        edit_user.qq = request.form['qq']
        edit_user.role = request.form['role']
        edit_user.vip = 'vip' in request.form

        # 如果提供了新密码，则更新密码
        new_password = request.form.get('password', '').strip()
        if new_password:
            from werkzeug.security import generate_password_hash
            edit_user.password = generate_password_hash(new_password)

        try:
            db.session.commit()
            flash('用户信息已更新', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'更新用户信息失败: {str(e)}', 'error')

        return redirect(url_for('Admin.users'))
    return None


# 删除用户
def delete_user(user_id):
    if request.method == 'DELETE':
        try:
            delete_user = User.query.get_or_404(user_id)
            username = delete_user.username  # 保存用户名用于消息显示
            db.session.delete(delete_user)
            db.session.commit()
            flash(f'用户 {username} 已成功删除', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'删除用户失败: {str(e)}', 'danger')
        return redirect(url_for('Admin.users'))

    flash('请求的操作不存在', 'danger')
    return redirect(url_for('Admin.users'))
