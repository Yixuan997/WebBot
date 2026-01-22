"""
@Project：WebBot
@File   ：__init__.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/7 00:15

机器人蓝图
"""

from flask import Blueprint

from .detail import bot_detail
from .list import list_bots
from .manage import start_bot, stop_bot
from ..utils import login_required_with_message

# 创建bots蓝图
bots_bp = Blueprint('bots', __name__, url_prefix='/bots')

# 添加路由
bots_bp.add_url_rule('/', view_func=login_required_with_message()(list_bots), methods=['GET'], endpoint='list_bots')
bots_bp.add_url_rule('/<int:bot_id>', view_func=login_required_with_message()(bot_detail), methods=['GET'],
                     endpoint='bot_detail')
bots_bp.add_url_rule('/<int:bot_id>/start', view_func=login_required_with_message()(start_bot), methods=['POST'],
                     endpoint='start_bot')
bots_bp.add_url_rule('/<int:bot_id>/stop', view_func=login_required_with_message()(stop_bot), methods=['POST'],
                     endpoint='stop_bot')
