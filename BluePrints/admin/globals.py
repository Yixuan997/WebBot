"""
全局变量管理
"""
from flask import flash, redirect, render_template, request, url_for

from Core.workflow.globals import global_variables
from Models import GlobalVariable
from sqlalchemy import or_
from utils.page_utils import adapt_pagination


def globals_list():
    """全局变量列表页面"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        search = request.args.get('search', '').strip()

        query = GlobalVariable.query
        if search:
            query = query.filter(or_(
                GlobalVariable.key.contains(search),
                GlobalVariable.value.contains(search),
                GlobalVariable.description.contains(search)
            ))

        pagination = query.order_by(
            GlobalVariable.updated_at.desc(),
            GlobalVariable.id.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        variables = pagination.items
        page_numbers = adapt_pagination(pagination)

        return render_template('admin/globals.html',
                               variables=variables,
                               pagination=pagination,
                               page_numbers=page_numbers,
                               current_page=pagination.page,
                               total_pages=pagination.pages,
                               search=search)
    except Exception:
        flash('获取全局变量列表失败', 'danger')
        pagination = GlobalVariable.query.filter(False).paginate(page=1, per_page=10, error_out=False)
        return render_template('admin/globals.html',
                               variables=[],
                               pagination=pagination,
                               page_numbers=[],
                               current_page=1,
                               total_pages=0,
                               search='')


def globals_create():
    """创建全局变量"""
    try:
        key = request.form.get('key', '').strip()
        value = request.form.get('value', '')
        description = request.form.get('description', '').strip()
        is_secret = request.form.get('is_secret') == 'on'

        if not key:
            flash('变量名不能为空', 'warning')
            return redirect(url_for('Admin.globals_list'))

        # 检查是否已存在
        if GlobalVariable.query.filter_by(key=key).first():
            flash(f'变量 {key} 已存在', 'warning')
            return redirect(url_for('Admin.globals_list'))

        # 创建变量
        global_variables.set(key, value, description, is_secret)

        flash('创建成功', 'success')

    except Exception as e:
        flash(f'创建失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.globals_list'))


def globals_update(var_id):
    """更新全局变量"""
    try:
        var = GlobalVariable.query.get_or_404(var_id)

        key = request.form.get('key', '').strip()
        value = request.form.get('value', '')
        description = request.form.get('description', '').strip()
        is_secret = request.form.get('is_secret') == 'on'

        if not key:
            flash('变量名不能为空', 'warning')
            return redirect(url_for('Admin.globals_list'))

        # 如果 key 改变，检查新 key 是否已存在
        if key != var.key and GlobalVariable.query.filter_by(key=key).first():
            flash(f'变量 {key} 已存在', 'warning')
            return redirect(url_for('Admin.globals_list'))

        # 如果 key 改变，需要删除旧的再创建新的
        if key != var.key:
            global_variables.delete(var.key)

        global_variables.set(key, value, description, is_secret)

        flash('更新成功', 'success')

    except Exception as e:
        flash(f'更新失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.globals_list'))


def globals_delete(var_id):
    """删除全局变量"""
    try:
        var = GlobalVariable.query.get_or_404(var_id)
        key = var.key

        global_variables.delete(key)

        flash('删除成功', 'success')

    except Exception as e:
        flash(f'删除失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.globals_list'))


def globals_reload():
    """重新加载全局变量缓存"""
    try:
        count = global_variables.reload()
        flash(f'已重新加载 {count} 个全局变量', 'success')
    except Exception as e:
        flash(f'重载失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.globals_list'))
