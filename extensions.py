"""
@Project：WebBot 
@File   ：extensions.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/6 23:45 
"""
import os.path
import traceback
from http import HTTPStatus
from typing import Dict, Any, Union, Tuple

from flask import Flask, g, session, Response, render_template, request, redirect
from flask_mail import Mail
from flask_migrate import Migrate
from flask_session import Session
from werkzeug.exceptions import HTTPException

from Core.tools.browser import browser
from Database import init_redis
# 导入模型
from Models import db, User, System
from http_json import fail_api

# 初始化扩展实例
mail = Mail()
migrate = Migrate()
flask_session = Session()


def init_browser():
    """初始化浏览器管理器"""
    try:
        # 启动浏览器管理器
        browser.start()
    except Exception as e:
        # 浏览器管理器启动失败不阻止应用启动（可选功能）
        import logging
        logging.warning(f"浏览器管理器启动失败: {e}")


def init_extensions(app: Flask) -> None:
    """
    初始化Flask扩展

    参数:
        app: Flask应用实例
    """
    # 核心扩展（必须同步初始化）
    flask_session.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db)
    init_redis(app)

    # 邮件系统
    mail.init_app(app)

    # 浏览器管理器（可选功能）
    init_browser()


def register_middleware(app: Flask) -> None:
    """
        注册所有中间件

        参数:
            app: Flask应用实例
        """

    # 安装检查 - 设置标记供其他中间件判断
    @app.before_request
    def check_install():
        """检查是否已安装，未安装则跳转到安装页面"""
        # 跳过安装相关路由和静态文件
        if request.path.startswith('/install') or request.path.startswith('/static'):
            g.is_installed = False  # 标记为未安装状态
            return None

        # 检查数据库是否存在
        from config import config
        if not config.ensure_database_exists(app):
            g.is_installed = False
            return redirect('/install')

        g.is_installed = True
        return None

    # 数据库连接清理
    @app.teardown_appcontext
    def teardown_db(exception):
        """请求结束时清理数据库连接"""
        try:
            # 如果有异常，回滚事务
            if exception:
                db.session.rollback()
            # 移除数据库会话，释放连接回连接池
            db.session.remove()
        except Exception as e:
            # 如果清理过程中出现异常，尝试强制关闭
            try:
                db.session.close()
            except Exception:
                # 最后的异常只能静默失败，但至少记录
                import logging
                logging.error(f"Database teardown failed: {e}")

    # Redis连接清理
    @app.teardown_appcontext
    def teardown_redis(exception):
        """请求结束时清理 Redis 连接"""
        redis_client = g.pop('redis', None)
        if redis_client is not None:
            # Redis连接池会自动管理连接，我们只需要清理引用
            pass

    # 用户加载
    @app.before_request
    def load_user() -> None:
        """加载用户信息到 g 对象"""
        # 未安装时跳过
        if not getattr(g, 'is_installed', False):
            g.user = None
            return

        user_id = session.get('user_id')

        if user_id:
            # 检查是否已经加载过用户（避免重复查询）
            if hasattr(g, 'user') and g.user and g.user.id == user_id:
                return

            try:
                user = User.query.get(user_id)
                if not user:
                    session.clear()
                    g.user = None
                else:
                    g.user = user
            except Exception as e:
                # 数据库查询失败，清除 session
                import logging
                logging.warning(f"Failed to load user {user_id}: {e}")
                session.clear()
                g.user = None
        else:
            g.user = None

    # 安全响应头
    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """添加安全响应头"""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    # 上下文处理器
    @app.context_processor
    def inject_context_variables() -> Dict[str, Any]:
        """注入模板上下文变量"""

        # 未安装时返回空数据
        if not getattr(g, 'is_installed', False):
            return {
                'system': {},
                'user': None,
                'debug_mode': app.debug,
                'version': {}
            }

        # 缓存系统数据（避免每次请求都查询数据库）
        if not hasattr(g, 'cached_system_data'):
            try:
                system = System.query.first()
                g.cached_system_data = vars(system) if system else {}
            except Exception as e:
                # 数据库查询失败时使用空字典
                import logging
                logging.warning(f"Failed to load system data: {e}")
                g.cached_system_data = {}

        # 缓存版本信息（避免重复计算）
        if not hasattr(g, 'cached_version_info'):
            from version import get_version_info
            g.cached_version_info = get_version_info()

        return {
            'system': g.cached_system_data,
            'user': getattr(g, 'user', None),
            'debug_mode': app.debug,
            'version': g.cached_version_info
        }


def register_error_handlers(app: Flask) -> None:
    """
    注册错误处理器

    参数:
        app: Flask应用实例
    """

    @app.errorhandler(Exception)
    def handle_error(error: Union[Exception, HTTPException]) -> Response:
        """全局异常处理"""
        error_code = getattr(error, 'code', 500)
        tb = traceback.extract_tb(error.__traceback__)
        file_path, line_number, _, _ = tb[-1]
        file_name = os.path.basename(file_path)
        error_type = error.__class__.__name__
        error_msg = str(error)

        msg = f'文件 {file_name} 发生 {error_type} 错误，请联系管理员！'
        return fail_api(msg=msg)

    @app.errorhandler(404)
    @app.errorhandler(405)
    def handle_http_error(error: HTTPException) -> Tuple[str, int]:
        """HTTP 错误处理"""
        if error.code == HTTPStatus.METHOD_NOT_ALLOWED:
            return render_template('error.html', code=error.code, error='请求方法不允许！'), error.code
        return render_template('error.html', code=error.code, error='您访问的页面不存在！'), error.code


def register_routes(app: Flask) -> None:
    """
    注册路由和蓝图

    参数:
        app: Flask应用实例
    """
    # 导入蓝图注册函数
    from BluePrints import register_blueprints

    # 注册蓝图
    register_blueprints(app)

    @app.route('/')
    def index() -> str:
        """首页路由"""
        return render_template('index.html')
