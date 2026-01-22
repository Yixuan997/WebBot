"""
@Project：WebBot 
@File   ：bots.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 15:00
"""

from flask import render_template, request, flash, redirect, url_for, session

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
    return render_template('user/bots/list.html', user=user, bots=bots, system=system)


def create_bot():
    """创建机器人"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'GET':
        system = System.query.first()
        return render_template('user/bots/create.html', user=user, system=system)

    try:
        import json

        # 获取表单数据
        name = request.form.get('name', '').strip()
        protocol = request.form.get('protocol', 'qq').strip()
        description = request.form.get('description', '').strip()

        # 验证数据
        if not name:
            flash('机器人名称不能为空', 'danger')
            return redirect(url_for('user.create_bot'))

        if protocol == 'qq':
            # QQ协议
            app_id = request.form.get('app_id', '').strip()
            app_secret = request.form.get('app_secret', '').strip()

            if not app_id:
                flash('App ID不能为空', 'danger')
                return redirect(url_for('user.create_bot'))

            if not app_secret:
                flash('App Secret不能为空', 'danger')
                return redirect(url_for('user.create_bot'))

            # 检查App ID是否已存在
            qq_bots = Bot.query.filter_by(protocol='qq').all()
            for existing_bot in qq_bots:
                existing_config = existing_bot.get_config()
                if existing_config.get('app_id') == app_id:
                    flash('该App ID已被使用', 'danger')
                    return redirect(url_for('user.create_bot'))

            config = {
                'app_id': app_id,
                'app_secret': app_secret,
                'token': None
            }

        elif protocol == 'onebot':
            # OneBot协议
            ws_host = request.form.get('ws_host', '127.0.0.1').strip()
            ws_port = request.form.get('ws_port', '5700').strip()
            access_token = request.form.get('access_token', '').strip()
            self_trigger = request.form.get('self_trigger') == 'on'

            if not ws_host:
                flash('OneBot地址不能为空', 'danger')
                return redirect(url_for('user.create_bot'))

            if not ws_port:
                flash('OneBot端口不能为空', 'danger')
                return redirect(url_for('user.create_bot'))

            try:
                ws_port = int(ws_port)
            except ValueError:
                flash('OneBot端口必须是数字', 'danger')
                return redirect(url_for('user.create_bot'))

            config = {
                'ws_host': ws_host,
                'ws_port': ws_port,
                'access_token': access_token if access_token else None,
                'self_trigger': self_trigger
            }
        else:
            flash('不支持的协议类型', 'danger')
            return redirect(url_for('user.create_bot'))

        bot = Bot(
            name=name,
            protocol=protocol,
            config=json.dumps(config),
            description=description,
            owner_id=user_id
        )

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
        return render_template('user/bots/edit.html', user=user, bot=bot, system=system, is_running=is_running)

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
        import json
        config_data = {}

        if bot.protocol == 'qq':
            app_id = request.form.get('app_id', '').strip()
            app_secret = request.form.get('app_secret', '').strip()

            if not all([app_id, app_secret]):
                flash('QQ协议需要填写AppID和AppSecret', 'danger')
                return redirect(url_for('user.edit_bot', bot_id=bot_id))

            # 保留原有token
            old_config = bot.get_config()
            old_token = old_config.get('token') if old_config else None

            config_data = {
                'app_id': app_id,
                'app_secret': app_secret,
                'token': old_token
            }
        elif bot.protocol == 'onebot':
            ws_host = request.form.get('ws_host', '').strip()
            ws_port = request.form.get('ws_port', '').strip()
            access_token = request.form.get('access_token', '').strip()

            if not all([ws_host, ws_port]):
                flash('OneBot协议需要填写WebSocket主机和端口', 'danger')
                return redirect(url_for('user.edit_bot', bot_id=bot_id))

            try:
                ws_port = int(ws_port)
            except ValueError:
                flash('WebSocket端口必须是数字', 'danger')
                return redirect(url_for('user.edit_bot', bot_id=bot_id))

            config_data = {
                'ws_host': ws_host,
                'ws_port': ws_port,
                'access_token': access_token if access_token else None
            }

        # 更新配置
        bot.config = json.dumps(config_data, ensure_ascii=False)

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
