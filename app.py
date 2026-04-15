"""
QQ机器人管理系统
"""

# 第三方库导入
from flask import Flask

# 本地应用导入
from Core.bot.manager import BotManager
from config import config
from extensions import init_extensions, register_middleware, register_routes


def _log_init_error(error: Exception, stage: str) -> None:
    """记录初始化阶段错误，不阻止应用继续启动。"""
    message = f"{stage} 初始化失败: {error}"
    try:
        from Core.logging.file_logger import log_error
        log_error(0, message, "APP_INIT_ERROR", stage=stage, error=str(error))
    except Exception:
        import logging
        logging.error(message)


def _init_scheduler():
    """初始化定时调度器。"""
    try:
        from Core.scheduler import scheduler_service
        scheduler_service.start()
        return scheduler_service
    except Exception as error:
        _log_init_error(error, "scheduler")
        return None


def _init_workflow_cache():
    """初始化工作流缓存。"""
    try:
        from Core.logging.file_logger import log_info
        from Core.workflow.cache import workflow_cache
        count = workflow_cache.reload()
        log_info(0, f"工作流缓存初始化完成: {count} 个工作流", "WORKFLOW_CACHE_INIT", count=count)
        return workflow_cache
    except Exception as error:
        _log_init_error(error, "workflow_cache")
        return None


def _init_global_variables() -> None:
    """初始化全局变量缓存。"""
    try:
        from Core.logging.file_logger import log_info
        from Core.workflow.globals import global_variables
        globals_count = global_variables.load()
        log_info(0, f"全局变量缓存初始化完成: {globals_count} 个变量", "GLOBALS_CACHE_INIT", count=globals_count)
    except Exception as error:
        _log_init_error(error, "global_variables")


def _init_global_proxy() -> None:
    """初始化全局网络代理环境变量。"""
    try:
        from Core.utils.network_proxy import apply_global_proxy_settings
        apply_global_proxy_settings()
    except Exception as error:
        _log_init_error(error, "network_proxy")


def _sync_scheduler_from_cache(scheduler_service, workflow_cache) -> None:
    """从工作流缓存同步定时任务。"""
    if not scheduler_service or not workflow_cache:
        return

    try:
        from Core.logging.file_logger import log_info
        scheduled_count = scheduler_service.sync_scheduled_workflows_from_cache(
            workflow_cache.get_all_workflows()
        )
        log_info(0, f"定时调度器初始化完成: {scheduled_count} 个定时任务", "SCHEDULER_INIT", count=scheduled_count)
    except Exception as error:
        _log_init_error(error, "scheduler_sync")


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
        _init_global_variables()
        _init_global_proxy()
        scheduler_service = _init_scheduler()
        workflow_cache = _init_workflow_cache()
        _sync_scheduler_from_cache(scheduler_service, workflow_cache)

    # 注册启动后的自动恢复任务
    def auto_recover_bot_status_delayed():
        """自动恢复机器人状态"""
        import threading

        def recovery_task():
            try:
                with flask_app.app_context():
                    from Core.logging.file_logger import log_warn
                    from Core.scheduler import scheduler_service

                    db_ready = config.ensure_database_exists(flask_app)
                    scheduler_ready = scheduler_service.is_running()
                    if not (db_ready and scheduler_ready):
                        log_warn(0, "自动恢复跳过：依赖未就绪", "AUTO_RECOVERY_SKIP_NOT_READY")
                        return

                    # 自动恢复机器人状态
                    BotManager.auto_recover_bot_status_on_startup()
            except Exception as e:
                # 记录恢复错误但不影响应用
                try:
                    from Core.logging.file_logger import log_error
                    log_error(0, f"自动恢复机器人状态失败: {e}", "AUTO_RECOVERY_ERROR", error=str(e))
                except Exception:
                    import logging
                    logging.error(f"自动恢复机器人状态失败: {e}")

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
