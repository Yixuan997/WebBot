"""
@Project：WebBot 
@File   ：system.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 09:55 
"""
from flask import render_template, flash, redirect, url_for, request

from Models import System, db


def system():
    settings = System.query.first()

    if request.method == 'POST':
        if not settings:
            settings = System()

        settings.title = request.form['title']
        settings.des = request.form['des']
        settings.key = request.form['key']
        settings.email = request.form['email']
        settings.icp = request.form['icp']
        settings.cop = request.form['cop']

        try:
            db.session.add(settings)
            db.session.commit()
            flash('系统设置已更新', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'更新系统设置失败: {str(e)}', 'error')

        return redirect(url_for('Admin.system'))

    return render_template('admin/system.html', settings=settings)
