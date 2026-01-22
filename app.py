"""
QQ机器人管理系统
"""

# 第三方库导入
from flask import Flask

# 本地应用导入
from Core.bot.manager import BotManager
from config import config
from extensions import init_extensions, register_middleware, register_routes


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
    
    # 初始化全局上下文管理器
    from Core.utils.context import init_app as init_context
    init_context(flask_app)

    # 注册路由和蓝图
    register_routes(flask_app)

    # 注册中间件
    register_middleware(flask_app)

    # 初始化各组件（在应用上下文中）
    with flask_app.app_context():
        try:
            from Core.logging.file_logger import log_info
            
            # 初始化工作流缓存
            from Core.workflow.cache import workflow_cache
            count = workflow_cache.reload()
            log_info(0, f"工作流缓存初始化完成: {count} 个工作流", "WORKFLOW_CACHE_INIT", count=count)
            
            # 初始化全局变量缓存
            from Core.workflow.globals import global_variables
            globals_count = global_variables.load()
            log_info(0, f"全局变量缓存初始化完成: {globals_count} 个变量", "GLOBALS_CACHE_INIT", count=globals_count)
            
            # 初始化定时调度器
            from Core.scheduler import scheduler_service
            scheduler_service.start()
            scheduled_count = scheduler_service.reload_scheduled_workflows()
            log_info(0, f"定时调度器初始化完成: {scheduled_count} 个定时任务", "SCHEDULER_INIT", count=scheduled_count)

        except Exception as e:
            # 记录错误但不阻止应用启动
            try:
                from Core.logging.file_logger import log_error
                log_error(0, f"初始化失败: {e}", "APP_INIT_ERROR", error=str(e))
            except Exception:
                print(f"[ERROR] 初始化失败: {e}")

    # 注册启动后的自动恢复任务
    def auto_recover_bot_status_delayed():
        """延迟自动恢复机器人状态"""
        import threading
        import time

        def recovery_task():
            # 等待应用完全启动（2秒）
            time.sleep(2)
            try:
                with flask_app.app_context():
                    # 自动恢复机器人状态
                    BotManager.auto_recover_bot_status_on_startup()
            except Exception as e:
                # 记录恢复错误但不影响应用
                try:
                    from Core.logging.file_logger import log_error
                    log_error(0, f"自动恢复机器人状态失败: {e}", "AUTO_RECOVERY_ERROR", error=str(e))
                except Exception:
                    print(f"[ERROR] 自动恢复失败: {e}")

        # 在后台线程中执行恢复
        recovery_thread = threading.Thread(target=recovery_task, daemon=True, name="BotAutoRecovery")
        recovery_thread.start()

    # 启动延迟恢复任务
    auto_recover_bot_status_delayed()

    return flask_app


# 创建应用实例供 gunicorn 使用
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
