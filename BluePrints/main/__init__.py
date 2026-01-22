"""
主页蓝图

处理主页和通用页面
"""

from flask import Blueprint

from .install import install_index, check_env, test_redis, save_config, run_install

main_bp = Blueprint('main', __name__)

# 安装向导路由
main_bp.add_url_rule('/install', view_func=install_index, methods=['GET'])
main_bp.add_url_rule('/install/check-env', view_func=check_env, methods=['GET'])
main_bp.add_url_rule('/install/test-redis', view_func=test_redis, methods=['POST'])
main_bp.add_url_rule('/install/save-config', view_func=save_config, methods=['POST'])
main_bp.add_url_rule('/install/run', view_func=run_install, methods=['POST'])
