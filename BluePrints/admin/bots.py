"""
@Project：WebBot
@File   ：bots.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/8 11:30

管理后台机器人管理功能
"""

import threading
from datetime import datetime

from flask import render_template, request, flash, redirect, url_for, jsonify
from sqlalchemy import or_

from Core.bot.manager import BotManager
from Core.logging.file_logger import log_info, log_error
from Models import Bot, User, db, Workflow
from Models.Extensions import get_current_time
from utils.page_utils import adapt_pagination

_bot_manager_instance = None
_bot_manager_lock = threading.Lock()


def get_bot_manager():
    """获取机器人管理器单例 - 使用全局单例 + 线程锁"""
    global _bot_manager_instance

    # 双重检查锁定模式
    if _bot_manager_instance is None:
        with _bot_manager_lock:
            # 再次检查，防止多线程竞态条件
            if _bot_manager_instance is None:
                log_info(0, "创建新的BotManager实例", "BOT_MANAGER_CREATE",
                         thread_id=threading.get_ident())
                _bot_manager_instance = BotManager()

    return _bot_manager_instance


def _get_bot_logs(bot_id, is_running, max_lines=None):
    """读取机器人日志文件
    
    Args:
        bot_id: 机器人 ID
        is_running: 是否运行中
        max_lines: 最大行数，None 表示不限制
    """
    try:
        import os
        from datetime import datetime

        # 构建日志文件路径
        today = datetime.now().strftime('%Y-%m-%d')
        log_file_path = os.path.join('logs', f'bot_{bot_id}', f'{today}.log')

        # 如果日志文件存在，读取内容
        if os.path.exists(log_file_path):
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # 如果指定了 max_lines，只返回最后 N 行
            if max_lines is not None and len(lines) > max_lines:
                lines = lines[-max_lines:]

            # 返回日志内容，去掉换行符并过滤空行
            log_content = [line.rstrip() for line in lines if line.strip()]
            return log_content
        else:
            # 如果没有日志文件
            if is_running:
                return ["等待日志输出..."]
            else:
                return ["机器人未运行，暂无日志"]

    except Exception as e:
        return [f"读取日志文件失败: {e}"]


def admin_bots():
    """管理员机器人列表"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search = request.args.get('search', '')

    # 构建查询
    query = Bot.query
    if search:
        query = query.filter(or_(
            Bot.name.contains(search),
            Bot.description.contains(search),
            Bot.protocol.contains(search)  # 搜索协议类型
        ))

    # 分页查询
    pagination = query.order_by(Bot.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    bots_list = pagination.items

    # 获取实时运行状态并添加到机器人对象
    running_bots = get_bot_manager().list_running_bots()
    for bot in bots_list:
        # 添加实时运行状态
        bot.real_is_running = bot.id in running_bots

    # 使用智能分页适配器
    page_numbers = adapt_pagination(pagination)

    return render_template('admin/bots.html',
                           bots=bots_list,
                           pagination=pagination,
                           page_numbers=page_numbers,
                           current_page=pagination.page,
                           total_pages=pagination.pages,
                           search=search)


def admin_create_bot():
    """管理员创建机器人"""
    if request.method == 'POST':
        try:
            # 获取通用字段
            name = request.form.get('name')
            description = request.form.get('description', '')
            protocol = request.form.get('protocol', 'qq')
            owner_id = request.form.get('owner_id')

            # 验证基本必填字段
            if not all([name, owner_id]):
                flash('请填写所有必填字段', 'error')
                return render_template('admin/create_bot.html',
                                       form_data=request.form,
                                       users=User.query.all())

            # 验证用户是否存在
            owner = User.query.get(owner_id)
            if not owner:
                flash('指定的用户不存在', 'error')
                return render_template('admin/create_bot.html',
                                       form_data=request.form,
                                       users=User.query.all())

            # 根据协议类型读取配置
            config_data = {}
            if protocol == 'qq':
                app_id = request.form.get('app_id')
                app_secret = request.form.get('app_secret')

                if not all([app_id, app_secret]):
                    flash('QQ协议需要填写AppID和AppSecret', 'error')
                    return render_template('admin/create_bot.html',
                                           form_data=request.form,
                                           users=User.query.all())

                config_data = {
                    'app_id': app_id,
                    'app_secret': app_secret,
                    'token': None  # 连接成功后由QQ返回
                }
            elif protocol == 'onebot':
                ws_host = request.form.get('ws_host', '0.0.0.0')
                ws_port = request.form.get('ws_port', '8080')
                access_token = request.form.get('access_token', '')

                if not all([ws_host, ws_port]):
                    flash('OneBot协议需要填写WebSocket主机和端口', 'error')
                    return render_template('admin/create_bot.html',
                                           form_data=request.form,
                                           users=User.query.all())

                try:
                    ws_port = int(ws_port)
                except ValueError:
                    flash('WebSocket端口必须是数字', 'error')
                    return render_template('admin/create_bot.html',
                                           form_data=request.form,
                                           users=User.query.all())

                config_data = {
                    'ws_host': ws_host,
                    'ws_port': ws_port,
                    'access_token': access_token if access_token else None,
                    'self_trigger': 'self_trigger' in request.form
                }

            # 创建机器人
            bot = Bot(
                name=name,
                description=description,
                protocol=protocol,
                owner_id=owner_id,
                created_at=get_current_time(),
                is_active=True
            )

            # 设置配置
            bot.set_config(config_data)

            db.session.add(bot)
            db.session.commit()

            flash(f'机器人 {name} 创建成功！', 'success')
            return redirect(url_for('Admin.admin_bots'))

        except Exception as e:
            db.session.rollback()
            flash(f'创建机器人失败: {str(e)}', 'error')
            return render_template('admin/create_bot.html',
                                   form_data=request.form,
                                   users=User.query.all())

    # GET 请求，显示创建表单
    users = User.query.all()
    return render_template('admin/create_bot.html', users=users)


def admin_edit_bot(bot_id):
    """管理员编辑机器人"""
    bot = Bot.query.get_or_404(bot_id)

    if request.method == 'POST':
        try:
            # 检查机器人是否运行中
            bot_manager = get_bot_manager()
            is_running = bot_id in bot_manager.list_running_bots()

            if is_running:
                flash('机器人运行中，请先停止机器人后再修改配置！', 'error')
                users = User.query.all()
                return render_template('admin/edit_bot.html', bot=bot, users=users, is_running=is_running)

            # 停止状态，允许修改所有配置
            bot.name = request.form.get('name')
            bot.description = request.form.get('description', '')
            bot.protocol = request.form.get('protocol', 'qq')
            bot.owner_id = request.form.get('owner_id')
            bot.is_active = 'is_active' in request.form

            # 根据协议类型更新配置
            config_data = {}
            if bot.protocol == 'qq':
                app_id = request.form.get('app_id')
                app_secret = request.form.get('app_secret')

                if not all([app_id, app_secret]):
                    flash('QQ协议需要填写AppID和AppSecret', 'error')
                    users = User.query.all()
                    return render_template('admin/edit_bot.html', bot=bot, users=users)

                # 保留原有token（如果存在）
                old_config = bot.get_config()
                old_token = old_config.get('token') if old_config else None

                config_data = {
                    'app_id': app_id,
                    'app_secret': app_secret,
                    'token': old_token
                }
            elif bot.protocol == 'onebot':
                ws_host = request.form.get('ws_host', '0.0.0.0')
                ws_port = request.form.get('ws_port', '8080')
                access_token = request.form.get('access_token', '')

                if not all([ws_host, ws_port]):
                    flash('OneBot协议需要填写WebSocket主机和端口', 'error')
                    users = User.query.all()
                    return render_template('admin/edit_bot.html', bot=bot, users=users)

                try:
                    ws_port = int(ws_port)
                except ValueError:
                    flash('WebSocket端口必须是数字', 'error')
                    users = User.query.all()
                    return render_template('admin/edit_bot.html', bot=bot, users=users)

                config_data = {
                    'ws_host': ws_host,
                    'ws_port': ws_port,
                    'access_token': access_token if access_token else None,
                    'self_trigger': 'self_trigger' in request.form
                }

            # 设置配置（使用辅助方法，会自动同步到旧字段）
            bot.set_config(config_data)

            db.session.commit()
            flash(f'机器人 {bot.name} 更新成功！', 'success')
            return redirect(url_for('Admin.admin_bots'))

        except Exception as e:
            db.session.rollback()
            flash(f'更新机器人失败: {str(e)}', 'error')

    # GET请求，获取运行状态
    bot_manager = get_bot_manager()
    is_running = bot_id in bot_manager.list_running_bots()

    users = User.query.all()
    return render_template('admin/edit_bot.html', bot=bot, users=users, is_running=is_running)


def admin_bot_detail(bot_id):
    """机器人详情页 - 使用延迟加载优化性能"""
    bot = Bot.query.get_or_404(bot_id)

    # 从机器人管理器获取真实运行数据
    bot_manager = get_bot_manager()
    is_running = bot_id in bot_manager.list_running_bots()
    real_status = bot_manager.get_bot_status(bot_id) if is_running else None

    # 获取工作流数量
    workflows_count = Workflow.query.filter_by(enabled=True).count()

    # 构建运行时数据
    if is_running and real_status:
        # 机器人正在运行，使用真实数据
        runtime_data = {
            'uptime': real_status.get('uptime', '0秒'),
            'message_count': real_status.get('message_count', 0),
            'error_count': real_status.get('error_count', 0),
            'workflows_count': workflows_count,  # 工作流数量
            'avg_response_time': 0,  # 默认响应时间
            'last_activity': bot.updated_at or bot.created_at,
            'start_time': real_status.get('start_time', 0),
            'is_running': True,
            'status': 'running'
        }
    elif is_running:
        # 运行中但状态获取失败
        runtime_data = {
            'uptime': '运行中',
            'message_count': 0,
            'error_count': 0,
            'workflows_count': workflows_count,  # 工作流数量
            'avg_response_time': 0,
            'last_activity': bot.updated_at or bot.created_at,
            'start_time': 0,
            'is_running': True,
            'status': 'running'
        }
    else:
        # 机器人未运行
        runtime_data = {
            'uptime': '未运行',
            'message_count': 0,
            'error_count': 0,
            'workflows_count': workflows_count,  # 工作流数量
            'avg_response_time': 0,
            'last_activity': bot.updated_at or bot.created_at,
            'start_time': 0,
            'is_running': False,
            'status': 'stopped'
        }

    # 日志将通过 AJAX 异步加载

    return render_template('admin/bot_detail.html',
                           bot=bot,
                           runtime_data=runtime_data)


def admin_delete_bot(bot_id):
    """管理员删除机器人"""
    if request.method == 'DELETE':
        bot = Bot.query.get_or_404(bot_id)

        try:
            bot_name = bot.name
            db.session.delete(bot)
            db.session.commit()
            flash(f'机器人 {bot_name} 删除成功！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'删除机器人失败: {str(e)}', 'danger')
    else:
        flash('请求的操作不存在', 'danger')

    return redirect(url_for('Admin.admin_bots'))


def admin_start_bot(bot_id):
    """启动机器人"""
    try:
        bot = Bot.query.get_or_404(bot_id)

        # 记录启动请求
        log_info(bot_id, f"收到启动机器人请求: {bot.name}", "BOT_START_REQUEST")

        # 使用机器人管理器启动机器人
        result = get_bot_manager().start_bot(bot_id)

        if result['success']:
            # 更新数据库状态
            bot.is_running = True
            db.session.commit()

            log_info(bot_id, f"机器人 {bot.name} 启动成功", "BOT_START_SUCCESS")

            return jsonify({
                'success': True,
                'message': f'机器人 {bot.name} 启动成功'
            })
        else:
            log_error(bot_id, f"机器人 {bot.name} 启动失败: {result['message']}", "BOT_START_FAILED")
            return jsonify({
                'success': False,
                'message': result['message']
            })

    except Exception as e:
        log_error(bot_id if 'bot_id' in locals() else 0, f"启动机器人异常: {str(e)}", "BOT_START_EXCEPTION",
                  error=str(e))
        return jsonify({
            'success': False,
            'message': f'启动失败: {str(e)}'
        }), 500


def admin_stop_bot(bot_id):
    """停止机器人"""
    try:
        bot = Bot.query.get_or_404(bot_id)

        # 记录停止请求
        log_info(bot_id, f"收到停止机器人请求: {bot.name}", "BOT_STOP_REQUEST")

        # 使用机器人管理器停止机器人
        result = get_bot_manager().stop_bot(bot_id)

        if result['success']:
            # 更新数据库状态
            bot.is_running = False
            db.session.commit()

            log_info(bot_id, f"机器人 {bot.name} 停止成功", "BOT_STOP_SUCCESS")

            return jsonify({
                'success': True,
                'message': f'机器人 {bot.name} 已停止'
            })
        else:
            log_error(bot_id, f"机器人 {bot.name} 停止失败: {result['message']}", "BOT_STOP_FAILED")
            return jsonify({
                'success': False,
                'message': result['message']
            })

    except Exception as e:
        log_error(bot_id if 'bot_id' in locals() else 0, f"停止机器人异常: {str(e)}", "BOT_STOP_EXCEPTION",
                  error=str(e))
        return jsonify({
            'success': False,
            'message': f'停止失败: {str(e)}'
        }), 500


def admin_restart_bot(bot_id):
    """重启机器人"""
    bot = Bot.query.get_or_404(bot_id)

    try:
        # 使用机器人管理器重启机器人
        result = get_bot_manager().restart_bot(bot_id)

        if result['success']:
            # 更新数据库状态
            bot.is_running = True
            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'机器人 {bot.name} 重启成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message']
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'重启失败: {str(e)}'
        })


def admin_force_reset_all_bots():
    """强制重置所有机器人状态"""
    try:
        log_info(0, "管理员请求强制重置所有机器人状态", "ADMIN_FORCE_RESET_REQUEST")

        # 使用机器人管理器强制重置
        from Core.bot.manager import BotManager
        success = BotManager.force_reset_all_bot_status()

        if success:
            log_info(0, "管理员强制重置所有机器人状态成功", "ADMIN_FORCE_RESET_SUCCESS")
            return jsonify({
                'success': True,
                'message': '所有机器人状态已强制重置为停止'
            })
        else:
            return jsonify({
                'success': False,
                'message': '强制重置失败，请查看日志'
            })

    except Exception as e:
        log_error(0, f"管理员强制重置异常: {str(e)}", "ADMIN_FORCE_RESET_EXCEPTION", error=str(e))
        return jsonify({
            'success': False,
            'message': f'强制重置失败: {str(e)}'
        }), 500


def admin_bot_status(bot_id):
    """获取机器人实时状态API"""
    try:
        # 获取实时状态
        bot_manager = get_bot_manager()
        is_running = bot_id in bot_manager.list_running_bots()
        status = bot_manager.get_bot_status(bot_id) if is_running else None

        if is_running:
            # 获取工作流数量
            workflows_count = Workflow.query.filter_by(enabled=True).count()

            # 获取Hook系统状态
            hook_system = bot_manager.plugin_manager.hook_system
            rate_status = hook_system.get_rate_limit_status()
            active_hooks = len([k for k, v in rate_status.items() if v['calls_last_minute'] > 0])

            # 如果有状态数据，使用真实数据；否则使用默认运行数据
            if status:
                uptime = status.get('uptime', '运行中')
                message_count = status.get('message_count', 0)
                error_count = status.get('error_count', 0)
                start_time = status.get('start_time', 0)
            else:
                uptime = '运行中'
                message_count = 0
                error_count = 0
                start_time = 0

            return jsonify({
                'success': True,
                'status': {
                    'is_running': True,
                    'uptime': uptime,
                    'message_count': message_count,
                    'error_count': error_count,
                    'start_time': start_time,
                    'workflows_count': workflows_count,
                    'active_hooks': active_hooks,
                    'avg_response_time': 0,  # 默认响应时间
                    'last_update': datetime.now().timestamp()
                }
            })
        else:
            return jsonify({
                'success': True,
                'status': {
                    'is_running': False,
                    'uptime': '未运行',
                    'message_count': 0,
                    'error_count': 0,
                    'start_time': 0,
                    'workflows_count': 0,
                    'active_hooks': 0,
                    'avg_response_time': 0,
                    'last_update': datetime.now().timestamp()
                }
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取状态失败: {str(e)}'
        })


def admin_bot_logs(bot_id):
    """获取机器人完整日志API - 用于延迟加载"""
    try:
        is_running = bot_id in get_bot_manager().list_running_bots()
        # 读取完整日志文件，不限制行数
        log_lines = _get_bot_logs(bot_id, is_running, max_lines=None)

        return jsonify({
            'success': True,
            'logs': log_lines
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取日志失败: {str(e)}'
        })


def admin_bot_log_files(bot_id):
    """获取机器人日志文件列表"""
    try:
        from Core.logging.file_logger import get_file_logger

        file_logger = get_file_logger()
        log_files = file_logger.list_bot_log_files(bot_id)

        return jsonify({
            'success': True,
            'files': log_files
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取日志文件失败: {str(e)}'
        })


def admin_bot_log_content(bot_id):
    """获取指定日期的日志内容"""
    try:
        from Core.logging.file_logger import get_file_logger

        date = request.args.get('date')
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        file_logger = get_file_logger()
        log_lines = file_logger.get_bot_logs(bot_id, date, limit=500)

        return jsonify({
            'success': True,
            'date': date,
            'lines': log_lines,
            'count': len(log_lines)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取日志内容失败: {str(e)}'
        })


def admin_log_stats():
    """系统日志页面 - 显示系统日志内容"""
    try:
        # 如果是AJAX请求，返回日志内容
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('ajax'):
            # 直接读取系统日志文件
            import os

            date = request.args.get('date')
            if not date:
                date = datetime.now().strftime('%Y-%m-%d')

            # 系统日志文件路径 - 系统日志存储在 logs/system/ 目录下
            log_file_path = os.path.join('logs', 'system', f'{date}.log')

            log_lines = []
            try:
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()

                    # 返回最后500行日志
                    recent_lines = lines[-500:] if len(lines) > 500 else lines

                    # 去掉换行符并过滤空行
                    log_lines = [line.strip() for line in recent_lines if line.strip()]
                else:
                    log_lines = [f"系统日志文件不存在: {log_file_path}"]

            except Exception as e:
                log_lines = [f"读取系统日志失败: {str(e)}"]

            return jsonify({
                'success': True,
                'date': date,
                'lines': log_lines,
                'count': len(log_lines)
            })

        # 普通请求，返回页面
        return render_template('admin/system_logs.html')

    except Exception as e:
        if request.headers.get('Content-Type') == 'application/json' or request.args.get('ajax'):
            return jsonify({
                'success': False,
                'message': f'获取系统日志失败: {str(e)}'
            })
        else:
            flash(f'获取系统日志失败: {str(e)}', 'error')
            return render_template('admin/system_logs.html')
