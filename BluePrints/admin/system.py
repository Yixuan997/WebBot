"""
@Project：WebBot 
@File   ：system.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 09:55 
"""
from flask import render_template, flash, redirect, url_for, request

from Core.utils.network_proxy import (
    get_global_proxy_settings,
    save_global_proxy_settings,
    apply_global_proxy_settings,
)
from Models import System, db


def system():
    settings = System.query.first()
    proxy_settings = get_global_proxy_settings()

    if request.method == 'POST':
        if not settings:
            settings = System()

        settings.title = request.form['title']
        settings.des = request.form['des']
        settings.key = request.form['key']
        settings.email = request.form['email']
        settings.icp = request.form['icp']
        settings.cop = request.form['cop']

        proxy_enabled = request.form.get('proxy_enabled') == 'on'
        proxy_url = (request.form.get('proxy_url') or '').strip()
        proxy_no_proxy = (request.form.get('proxy_no_proxy') or '').strip()

        if proxy_enabled and not proxy_url:
            flash('开启全局代理时必须填写代理地址', 'error')
            proxy_settings = {
                'enabled': proxy_enabled,
                'proxy_url': proxy_url,
                'no_proxy': proxy_no_proxy,
            }
            return render_template('admin/system.html', settings=settings, proxy_settings=proxy_settings)

        try:
            db.session.add(settings)
            save_global_proxy_settings(proxy_enabled, proxy_url, proxy_no_proxy, commit=False)
            db.session.commit()
            apply_global_proxy_settings()
            flash('系统设置已更新', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'更新系统设置失败: {str(e)}', 'error')

        return redirect(url_for('Admin.system'))

    return render_template('admin/system.html', settings=settings, proxy_settings=proxy_settings)
