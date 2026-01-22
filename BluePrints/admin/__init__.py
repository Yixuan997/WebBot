"""
@Project：WebBot 
@File   ：__init__.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:55 
"""
from flask import Blueprint

from .bots import (admin_bots, admin_create_bot, admin_edit_bot, admin_bot_detail, admin_delete_bot,
                   admin_start_bot, admin_stop_bot, admin_restart_bot, admin_bot_status, admin_bot_logs,
                   admin_bot_log_files, admin_bot_log_content, admin_log_stats)
from .browser import (browser_status, restart_browser, start_browser, stop_browser)
from .dashboard import dashboard
from .email import email, test_email
from .globals import globals_list, globals_create, globals_update, globals_delete, globals_get, globals_reload
from .system import system
from .update import update, check_update, get_latest_release_content, download_and_apply_update, restart_application
from .users import users, edit_user, delete_user
from .workflow import (workflow_list, workflow_create, workflow_edit, workflow_delete,
                       workflow_toggle, workflow_detail, workflow_update_basic, snippets_list,
                       workflow_reload_cache, workflow_export, workflow_import,
                       workflow_debug_record, workflow_debug_clear)
from ..utils import role_required

# 创建admin蓝图
Admin_bp = Blueprint('Admin', __name__, url_prefix='/admin')

# 添加路由
Admin_bp.add_url_rule('/dashboard', view_func=role_required('admin')(dashboard), methods=['GET'],
                      endpoint='dashboard')  # 后台仪表盘

# 系统管理
Admin_bp.add_url_rule('/system', view_func=role_required('admin')(system), methods=['GET', 'POST'],
                      endpoint='system')  # 系统设置
Admin_bp.add_url_rule('/update', view_func=role_required('admin')(update), methods=['GET'],
                      endpoint='update')  # 系统更新
Admin_bp.add_url_rule('/update/check', view_func=role_required('admin')(check_update), methods=['GET'],
                      endpoint='check_update')  # 检查更新
Admin_bp.add_url_rule('/update/release', view_func=role_required('admin')(get_latest_release_content), methods=['GET'],
                      endpoint='get_latest_release')  # 获取最新Release内容
Admin_bp.add_url_rule('/update/apply', view_func=role_required('admin')(download_and_apply_update), methods=['POST'],
                      endpoint='apply_update')  # 应用更新
Admin_bp.add_url_rule('/update/restart', view_func=role_required('admin')(restart_application), methods=['POST'],
                      endpoint='restart_app')  # 重启应用
Admin_bp.add_url_rule('/email', view_func=role_required('admin')(email), methods=['GET', 'POST'],
                      endpoint='email')  # 邮件设置
Admin_bp.add_url_rule('/email/test', view_func=role_required('admin')(test_email), methods=['POST'],
                      endpoint='test_email')  # 测试邮件

# 用户管理
Admin_bp.add_url_rule('/users', view_func=role_required('admin')(users), methods=['GET'], endpoint='users')  # 用户管理
Admin_bp.add_url_rule('/users/<int:user_id>/edit', view_func=role_required('admin')(edit_user), methods=['GET', 'POST'],
                      endpoint='edit_user')  # 编辑用户
Admin_bp.add_url_rule('/users/<int:user_id>/delete', view_func=role_required('admin')(delete_user), methods=['DELETE'],
                      endpoint='delete_user')  # 删除用户

# 机器人管理
Admin_bp.add_url_rule('/bots', view_func=role_required('admin')(admin_bots), methods=['GET'],
                      endpoint='admin_bots')  # 机器人列表
Admin_bp.add_url_rule('/bots/create', view_func=role_required('admin')(admin_create_bot), methods=['GET', 'POST'],
                      endpoint='admin_create_bot')  # 创建机器人
Admin_bp.add_url_rule('/bots/<int:bot_id>', view_func=role_required('admin')(admin_bot_detail), methods=['GET'],
                      endpoint='admin_bot_detail')  # 机器人详情
Admin_bp.add_url_rule('/bots/<int:bot_id>/edit', view_func=role_required('admin')(admin_edit_bot),
                      methods=['GET', 'POST'],
                      endpoint='admin_edit_bot')  # 编辑机器人
Admin_bp.add_url_rule('/bots/<int:bot_id>/delete', view_func=role_required('admin')(admin_delete_bot),
                      methods=['DELETE'],
                      endpoint='admin_delete_bot')  # 删除机器人

# 机器人控制
Admin_bp.add_url_rule('/bots/<int:bot_id>/start', view_func=role_required('admin')(admin_start_bot), methods=['POST'],
                      endpoint='admin_start_bot')  # 启动机器人
Admin_bp.add_url_rule('/bots/<int:bot_id>/stop', view_func=role_required('admin')(admin_stop_bot), methods=['POST'],
                      endpoint='admin_stop_bot')  # 停止机器人
Admin_bp.add_url_rule('/bots/<int:bot_id>/restart', view_func=role_required('admin')(admin_restart_bot),
                      methods=['POST'],
                      endpoint='admin_restart_bot')  # 重启机器人
Admin_bp.add_url_rule('/bots/<int:bot_id>/status', view_func=role_required('admin')(admin_bot_status), methods=['GET'],
                      endpoint='admin_bot_status')  # 机器人状态
Admin_bp.add_url_rule('/bots/<int:bot_id>/logs', view_func=role_required('admin')(admin_bot_logs), methods=['GET'],
                      endpoint='admin_bot_logs')  # 机器人日志
Admin_bp.add_url_rule('/bots/<int:bot_id>/log-files', view_func=role_required('admin')(admin_bot_log_files),
                      methods=['GET'],
                      endpoint='admin_bot_log_files')  # 机器人日志文件列表
Admin_bp.add_url_rule('/bots/<int:bot_id>/log-content', view_func=role_required('admin')(admin_bot_log_content),
                      methods=['GET'],
                      endpoint='admin_bot_log_content')  # 机器人日志内容
Admin_bp.add_url_rule('/logs/stats', view_func=role_required('admin')(admin_log_stats), methods=['GET'],
                      endpoint='admin_log_stats')  # 日志统计

# 浏览器管理

Admin_bp.add_url_rule('/browser/status', view_func=role_required('admin')(browser_status), methods=['GET'],
                      endpoint='browser_status')  # 浏览器状态API
Admin_bp.add_url_rule('/browser/start', view_func=role_required('admin')(start_browser), methods=['POST'],
                      endpoint='start_browser')  # 启动浏览器
Admin_bp.add_url_rule('/browser/stop', view_func=role_required('admin')(stop_browser), methods=['POST'],
                      endpoint='stop_browser')  # 停止浏览器
Admin_bp.add_url_rule('/browser/restart', view_func=role_required('admin')(restart_browser), methods=['POST'],
                      endpoint='restart_browser')  # 重启浏览器

# 工作流管理
Admin_bp.add_url_rule('/workflows', view_func=role_required('admin')(workflow_list), methods=['GET'],
                      endpoint='workflow_list')  # 工作流列表
Admin_bp.add_url_rule('/workflows/create', view_func=role_required('admin')(workflow_create), methods=['GET', 'POST'],
                      endpoint='workflow_create')  # 创建工作流
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/edit', view_func=role_required('admin')(workflow_edit),
                      methods=['GET', 'POST'],
                      endpoint='workflow_edit')  # 编辑工作流
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/delete', view_func=role_required('admin')(workflow_delete),
                      methods=['POST'],
                      endpoint='workflow_delete')  # 删除工作流
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/toggle', view_func=role_required('admin')(workflow_toggle),
                      methods=['POST'],
                      endpoint='workflow_toggle')  # 切换工作流状态
Admin_bp.add_url_rule('/workflows/<int:workflow_id>', view_func=role_required('admin')(workflow_detail),
                      methods=['GET'],
                      endpoint='workflow_detail')  # 工作流详情
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/update-basic', view_func=role_required('admin')(workflow_update_basic),
                      methods=['POST'],
                      endpoint='workflow_update_basic')  # 更新工作流基本信息
Admin_bp.add_url_rule('/workflows/snippets', view_func=role_required('admin')(snippets_list), methods=['GET'],
                      endpoint='snippets_list')  # 代码片段列表
Admin_bp.add_url_rule('/workflows/reload', view_func=role_required('admin')(workflow_reload_cache), methods=['POST'],
                      endpoint='workflow_reload_cache')  # 重载工作流缓存
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/export', view_func=role_required('admin')(workflow_export),
                      methods=['GET'],
                      endpoint='workflow_export')  # 导出工作流
Admin_bp.add_url_rule('/workflows/import', view_func=role_required('admin')(workflow_import),
                      methods=['POST'],
                      endpoint='workflow_import')  # 导入工作流
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/debug', view_func=role_required('admin')(workflow_debug_record),
                      methods=['GET'],
                      endpoint='workflow_debug_record')  # 获取工作流调试记录
Admin_bp.add_url_rule('/workflows/<int:workflow_id>/debug/clear', view_func=role_required('admin')(workflow_debug_clear),
                      methods=['POST'],
                      endpoint='workflow_debug_clear')  # 清除工作流调试记录

# 全局变量管理
Admin_bp.add_url_rule('/globals', view_func=role_required('admin')(globals_list), methods=['GET'],
                      endpoint='globals_list')  # 全局变量列表
Admin_bp.add_url_rule('/globals/create', view_func=role_required('admin')(globals_create), methods=['POST'],
                      endpoint='globals_create')  # 创建全局变量
Admin_bp.add_url_rule('/globals/<int:var_id>', view_func=role_required('admin')(globals_get), methods=['GET'],
                      endpoint='globals_get')  # 获取单个全局变量
Admin_bp.add_url_rule('/globals/<int:var_id>', view_func=role_required('admin')(globals_update), methods=['PUT'],
                      endpoint='globals_update')  # 更新全局变量
Admin_bp.add_url_rule('/globals/<int:var_id>', view_func=role_required('admin')(globals_delete), methods=['DELETE'],
                      endpoint='globals_delete')  # 删除全局变量
Admin_bp.add_url_rule('/globals/reload', view_func=role_required('admin')(globals_reload), methods=['POST'],
                      endpoint='globals_reload')  # 重载全局变量缓存
