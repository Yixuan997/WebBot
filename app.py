"""
QQ机器人管理系统
"""

# 第三方库导入
from flask import Flask

# 移到顶部，避免延迟导入导致模块重新加载
from Core.bot.manager import BotManager
# 本地应用导入
from config import config
from extensions import init_extensions, init_extensions, register_middleware, register_routes


def create_app() -> Flask:
    """
    工厂函数 - 创建 Flask 应用实例

    返回值：
        Flask: 配置完成的 Flask 应用实例
    """
    flask_app = Flask(__name__)

    # 配置应用 - 使用配置类
    flask_app.config.from_object(config)

    # 使用配置对象的实例方法初始化额外配置
    config.init_app(flask_app)

    # 并行初始化扩展
    init_extensions(flask_app)

    # 注册路由和蓝图
    register_routes(flask_app)

    # 注册中间件
    register_middleware(flask_app)

    # # 注册错误处理
    # register_error_handlers(flask_app)

    # 注册启动后的自动恢复任务（开发环境每次都执行）
    def auto_recover_bot_status_delayed():
        """延迟自动恢复机器人状态"""
        import threading
        import time

        def recovery_task():
            # 等待应用完全启动
            time.sleep(2)
            try:
                with flask_app.app_context():
                    # 自动恢复机器人状态
                    BotManager.auto_recover_bot_status_on_startup()
            except Exception as e:
                pass  # 静默处理启动错误

        # 在后台线程中执行恢复
        recovery_thread = threading.Thread(target=recovery_task, daemon=True)
        recovery_thread.start()

    # 启动延迟恢复任务
    auto_recover_bot_status_delayed()

    return flask_app


# 创建应用实例供 gunicorn 使用
app = create_app()

# 检查并创建数据库 - 使用配置类的统一方法
config.ensure_database_exists(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
