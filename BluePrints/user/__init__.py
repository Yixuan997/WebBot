"""
@Project：WebBot 
@File   ：__init__.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/15 15:00
"""
from flask import Blueprint

from .bots import user_bots, create_bot, edit_bot, delete_bot, bot_action
from .dashboard import dashboard
from .profile import profile, update_profile, change_password
from .workflows import user_workflows, toggle_workflow_subscription
from ..utils import role_required

# 创建用户中心蓝图
user_bp = Blueprint('user', __name__, url_prefix='/user')

# 概览仪表盘
user_bp.add_url_rule('/dashboard', view_func=role_required('user')(dashboard), methods=['GET'], endpoint='dashboard')

# 个人资料
user_bp.add_url_rule('/profile', view_func=role_required('user')(profile), methods=['GET'], endpoint='profile')
user_bp.add_url_rule('/profile/update', view_func=role_required('user')(update_profile), methods=['POST'],
                     endpoint='update_profile')
user_bp.add_url_rule('/profile/password', view_func=role_required('user')(change_password), methods=['POST'],
                     endpoint='change_password')

# 机器人管理
user_bp.add_url_rule('/bots', view_func=role_required('user')(user_bots), methods=['GET'], endpoint='bots')
user_bp.add_url_rule('/bots/create', view_func=role_required('user')(create_bot), methods=['GET', 'POST'],
                     endpoint='create_bot')
user_bp.add_url_rule('/bots/<int:bot_id>/edit', view_func=role_required('user')(edit_bot), methods=['GET', 'POST'],
                     endpoint='edit_bot')
user_bp.add_url_rule('/bots/<int:bot_id>/delete', view_func=role_required('user')(delete_bot), methods=['DELETE'],
                     endpoint='delete_bot')
user_bp.add_url_rule('/bots/<int:bot_id>/<action>', view_func=role_required('user')(bot_action), methods=['POST'],
                     endpoint='bot_action')

# 工作流管理
user_bp.add_url_rule('/workflows', view_func=role_required('user')(user_workflows), methods=['GET'],
                     endpoint='workflows')
user_bp.add_url_rule('/workflows/<int:workflow_id>/toggle',
                     view_func=role_required('user')(toggle_workflow_subscription),
                     methods=['POST'], endpoint='toggle_workflow')
