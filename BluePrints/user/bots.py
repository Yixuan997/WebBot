"""
@Project：WebBot 
@File   ：bots.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 15:00
"""

from flask import render_template, request, flash, redirect, url_for, session

from Core.protocols import (
    get_default_protocol_id,
    list_protocols,
    parse_protocol_config_from_form,
    validate_protocol_config,
    validate_protocol_config_uniqueness,
)
from Models import User, Bot, db, System


def user_bots():
    """用户机器人列表"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    # 获取用户的所有机器人
    bots = Bot.query.filter_by(owner_id=user_id).order_by(Bot.created_at.desc()).all()

    # 获取实时运行状态并添加到机器人对象（与后台保持一致）
    try:
        from BluePrints.admin.bots import get_bot_manager
        bot_manager = get_bot_manager()
        running_bots = bot_manager.list_running_bots()
        for bot in bots:
            # 添加实时运行状态
            bot.real_is_running = bot.id in running_bots
    except Exception as e:
        # 如果获取运行状态失败，使用数据库状态作为备用
        for bot in bots:
            bot.real_is_running = bot.is_running

    system = System.query.first()
    protocol_name_map = {item['id']: item['name'] for item in list_protocols()}
    return render_template('user/bots/list.html', user=user, bots=bots, system=system,
                           protocol_name_map=protocol_name_map)


def create_bot():
    """创建机器人"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        system = System.query.first()
        return render_template('user/bots/create.html', user=user, system=system, protocol_options=list_protocols())

    try:
        # 获取表单数据
        name = request.form.get('name', '').strip()
        protocol = request.form.get('protocol', get_default_protocol_id()).strip()
        description = request.form.get('description', '').strip()

        # 验证数据
        if not name:
            flash('机器人名称不能为空', 'danger')
            return redirect(url_for('user.create_bot'))

        try:
            config = parse_protocol_config_from_form(protocol, request.form, existing_config={})
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('user.create_bot'))

        config_ok, config_error = validate_protocol_config(protocol, config)
        if not config_ok:
            flash(config_error, 'danger')
            return redirect(url_for('user.create_bot'))

        unique_ok, unique_error = validate_protocol_config_uniqueness(protocol, config)
        if not unique_ok:
            flash(unique_error, 'danger')
            return redirect(url_for('user.create_bot'))

        bot = Bot(
            name=name,
            protocol=protocol,
            description=description,
            owner_id=user_id
        )
        bot.set_config(config)

        db.session.add(bot)
        db.session.commit()

        flash('机器人创建成功', 'success')
        return redirect(url_for('user.bots'))

    except Exception as e:
        db.session.rollback()
        flash(f'创建失败：{str(e)}', 'danger')
        return redirect(url_for('user.create_bot'))


def edit_bot(bot_id):
    """编辑机器人"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    # 获取机器人（确保是当前用户的）
    bot = Bot.query.filter_by(id=bot_id, owner_id=user_id).first()
    if not bot:
        flash('机器人不存在或无权限访问', 'danger')
        return redirect(url_for('user.bots'))

    if request.method == 'GET':
        # 获取运行状态
        try:
            from BluePrints.admin.bots import get_bot_manager
            bot_manager = get_bot_manager()
            running_bots = bot_manager.list_running_bots()
            is_running = bot.id in running_bots
        except:
            is_running = bot.is_running

        system = System.query.first()
        return render_template('user/bots/edit.html', user=user, bot=bot, system=system, is_running=is_running,
                               protocol_options=list_protocols())

    try:
        # 检查机器人是否运行中
        from BluePrints.admin.bots import get_bot_manager
        bot_manager = get_bot_manager()
        running_bots = bot_manager.list_running_bots()
        is_running = bot.id in running_bots

        if is_running:
            flash('机器人运行中，请先停止机器人后再修改配置！', 'danger')
            return redirect(url_for('user.edit_bot', bot_id=bot_id))

        # 获取表单数据
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        # 验证数据
        if not name:
            flash('机器人名称不能为空', 'danger')
            return redirect(url_for('user.edit_bot', bot_id=bot_id))

        # 更新机器人信息
        bot.name = name
        bot.description = description

        # 根据协议类型更新配置
        existing_config = bot.get_config()
        try:
            config_data = parse_protocol_config_from_form(bot.protocol, request.form, existing_config=existing_config)
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('user.edit_bot', bot_id=bot_id))

        config_ok, config_error = validate_protocol_config(bot.protocol, config_data)
        if not config_ok:
            flash(config_error, 'danger')
            return redirect(url_for('user.edit_bot', bot_id=bot_id))

        unique_ok, unique_error = validate_protocol_config_uniqueness(
            bot.protocol,
            config_data,
            exclude_bot_id=bot.id
        )
        if not unique_ok:
            flash(unique_error, 'danger')
            return redirect(url_for('user.edit_bot', bot_id=bot_id))

        # 更新配置
        bot.set_config(config_data)

        db.session.commit()

        flash('机器人信息更新成功', 'success')
        return redirect(url_for('user.bots'))

    except Exception as e:
        db.session.rollback()
        flash(f'更新失败：{str(e)}', 'danger')
        return redirect(url_for('user.edit_bot', bot_id=bot_id))


def delete_bot(bot_id):
    """删除机器人"""
    if request.method == 'DELETE':
        user_id = session.get('user_id')

        # 获取机器人（确保是当前用户的）
        bot = Bot.query.filter_by(id=bot_id, owner_id=user_id).first()
        if not bot:
            flash('机器人不存在或无权限访问', 'danger')
            return redirect(url_for('user.bots'))

        try:
            bot_name = bot.name
            db.session.delete(bot)
            db.session.commit()

            flash(f'机器人 {bot_name} 删除成功', 'success')
            return redirect(url_for('user.bots'))

        except Exception as e:
            db.session.rollback()
            flash(f'删除失败：{str(e)}', 'danger')
            return redirect(url_for('user.bots'))

    flash('请求的操作不存在', 'danger')
    return redirect(url_for('user.bots'))


def bot_action(bot_id, action):
    """机器人操作（启动/停止）"""
    user_id = session.get('user_id')

    # 获取机器人（确保是当前用户的）
    bot = Bot.query.filter_by(id=bot_id, owner_id=user_id).first()
    if not bot:
        flash('机器人不存在或无权限访问', 'danger')
        return redirect(url_for('user.bots'))

    try:
        # 导入机器人管理器（使用 admin 的单例方法）
        from BluePrints.admin.bots import get_bot_manager
        bot_manager = get_bot_manager()

        if action == 'start':
            # 调用真正的机器人启动逻辑
            result = bot_manager.start_bot(bot_id)
            if result['success']:
                flash(f'机器人 {bot.name} 启动成功', 'success')
            else:
                flash(f'机器人 {bot.name} 启动失败：{result["message"]}', 'danger')

        elif action == 'stop':
            # 调用真正的机器人停止逻辑
            result = bot_manager.stop_bot(bot_id)
            if result['success']:
                flash(f'机器人 {bot.name} 停止成功', 'success')
            else:
                flash(f'机器人 {bot.name} 停止失败：{result["message"]}', 'danger')

        else:
            flash('无效的操作', 'danger')
            return redirect(url_for('user.bots'))

        return redirect(url_for('user.bots'))

    except Exception as e:
        flash(f'操作失败：{str(e)}', 'danger')
        return redirect(url_for('user.bots'))
