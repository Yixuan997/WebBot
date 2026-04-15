"""
定时工作流调度器服务

使用 APScheduler 实现定时任务调度
"""

import asyncio
import threading
from typing import Dict, Any, Optional, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from Core.logging.file_logger import log_info, log_error, log_debug, log_warn


class SchedulerService:
    """定时调度器服务（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化调度器"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._scheduler: Optional[BackgroundScheduler] = None
            self._jobs: Dict[int, str] = {}  # workflow_id -> job_id 映射
            log_info(0, "定时调度器服务初始化", "SCHEDULER_SERVICE_INIT")

    def start(self):
        """启动调度器"""
        if self._scheduler and self._scheduler.running:
            log_debug(0, "调度器已在运行", "SCHEDULER_ALREADY_RUNNING")
            return

        self._scheduler = BackgroundScheduler(
            timezone='Asia/Shanghai',
            job_defaults={
                'coalesce': True,  # 如果多个任务堆积，只执行最后一个
                'max_instances': 1,  # 同一任务最多并发1个实例
                'misfire_grace_time': 60  # 任务错过执行时间后60秒内仍可执行
            }
        )
        self._scheduler.start()
        log_info(0, "定时调度器已启动", "SCHEDULER_STARTED")

    def stop(self):
        """停止调度器"""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log_info(0, "定时调度器已停止", "SCHEDULER_STOPPED")

    def is_running(self) -> bool:
        """调度器是否处于运行状态"""
        return bool(self._scheduler and self._scheduler.running)

    def add_workflow_job(self, workflow_id: int, config: Dict[str, Any]) -> bool:
        """
        添加定时工作流任务
        
        Args:
            workflow_id: 工作流ID
            config: 工作流配置，包含 schedule 和 target 字段
            
        Returns:
            bool: 是否添加成功
        """
        if not self._scheduler or not self._scheduler.running:
            log_error(0, "调度器未运行，无法添加任务", "SCHEDULER_NOT_RUNNING")
            return False

        try:
            # 移除已存在的任务
            self.remove_workflow_job(workflow_id)

            schedule_config = config.get('schedule', {})
            schedule_type = schedule_config.get('type', 'cron')
            
            job_id = f"workflow_{workflow_id}"

            if schedule_type == 'cron':
                cron_expr = schedule_config.get('cron', '0 8 * * *')
                trigger = self._parse_cron(cron_expr)
                if not trigger:
                    log_error(0, f"无效的 cron 表达式: {cron_expr}", "INVALID_CRON",
                              workflow_id=workflow_id)
                    return False
            elif schedule_type == 'interval':
                interval_minutes = schedule_config.get('interval_minutes', 60)
                trigger = IntervalTrigger(minutes=interval_minutes)
            else:
                log_error(0, f"未知的调度类型: {schedule_type}", "UNKNOWN_SCHEDULE_TYPE",
                          workflow_id=workflow_id)
                return False

            # 添加任务
            self._scheduler.add_job(
                func=self._execute_scheduled_workflow,
                trigger=trigger,
                args=[workflow_id, config],
                id=job_id,
                name=f"Workflow: {config.get('name', workflow_id)}",
                replace_existing=True
            )

            self._jobs[workflow_id] = job_id
            
            # 生成调度描述
            schedule_desc = self._get_schedule_description(schedule_config)
            log_info(0, f"添加定时任务: {config.get('name', workflow_id)} ({schedule_desc})",
                     "SCHEDULER_JOB_ADDED",
                     workflow_id=workflow_id, schedule=schedule_desc)
            return True

        except Exception as e:
            log_error(0, f"添加定时任务失败: {e}", "SCHEDULER_ADD_JOB_ERROR",
                      workflow_id=workflow_id, error=str(e))
            return False

    def remove_workflow_job(self, workflow_id: int) -> bool:
        """
        移除定时工作流任务
        
        Args:
            workflow_id: 工作流ID
            
        Returns:
            bool: 是否移除成功
        """
        if not self._scheduler:
            return False

        job_id = self._jobs.get(workflow_id)
        if job_id:
            try:
                self._scheduler.remove_job(job_id)
                del self._jobs[workflow_id]
                log_info(0, f"移除定时任务: workflow_id={workflow_id}", "SCHEDULER_JOB_REMOVED")
                return True
            except Exception as e:
                log_debug(0, f"移除任务时出错（可能不存在）: {e}", "SCHEDULER_REMOVE_JOB_ERROR")
        return False

    def update_workflow_job(self, workflow_id: int, config: Dict[str, Any]) -> bool:
        """
        更新定时工作流任务
        
        Args:
            workflow_id: 工作流ID
            config: 新的工作流配置
            
        Returns:
            bool: 是否更新成功
        """
        # 简单地移除再添加
        self.remove_workflow_job(workflow_id)
        return self.add_workflow_job(workflow_id, config)

    def _parse_cron(self, cron_expr: str) -> Optional[CronTrigger]:
        """
        解析 cron 表达式
        
        支持 5 字段格式: 分 时 日 月 周
        
        Args:
            cron_expr: cron 表达式
            
        Returns:
            CronTrigger 或 None
        """
        try:
            parts = cron_expr.strip().split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
                return CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week
                )
            else:
                log_error(0, f"cron 表达式格式错误，需要5个字段: {cron_expr}", "INVALID_CRON_FORMAT")
                return None
        except Exception as e:
            log_error(0, f"解析 cron 表达式失败: {e}", "CRON_PARSE_ERROR", cron=cron_expr)
            return None

    def _get_schedule_description(self, schedule_config: Dict[str, Any]) -> str:
        """
        生成调度描述文本
        
        Args:
            schedule_config: 调度配置
            
        Returns:
            str: 描述文本，如 "每天 08:00" 或 "每 60 分钟"
        """
        schedule_type = schedule_config.get('type', 'cron')
        
        if schedule_type == 'interval':
            minutes = schedule_config.get('interval_minutes', 60)
            if minutes < 60:
                return f"每 {minutes} 分钟"
            elif minutes == 60:
                return "每小时"
            elif minutes % 60 == 0:
                return f"每 {minutes // 60} 小时"
            else:
                return f"每 {minutes} 分钟"
        else:
            cron = schedule_config.get('cron', '0 8 * * *')
            return self._cron_to_description(cron)

    def _cron_to_description(self, cron_expr: str) -> str:
        """
        将 cron 表达式转换为人类可读描述
        
        Args:
            cron_expr: cron 表达式
            
        Returns:
            str: 描述文本
        """
        try:
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                return cron_expr
                
            minute, hour, day, month, day_of_week = parts
            
            # 简单场景的描述
            if day == '*' and month == '*':
                if day_of_week == '*':
                    # 每天
                    if hour != '*' and minute != '*':
                        return f"每天 {hour.zfill(2)}:{minute.zfill(2)}"
                    elif hour != '*':
                        return f"每天 {hour.zfill(2)} 点"
                else:
                    # 每周特定天
                    weekdays = {'0': '周日', '1': '周一', '2': '周二', '3': '周三', 
                               '4': '周四', '5': '周五', '6': '周六', '7': '周日'}
                    day_name = weekdays.get(day_of_week, day_of_week)
                    if hour != '*' and minute != '*':
                        return f"每{day_name} {hour.zfill(2)}:{minute.zfill(2)}"
            
            # 复杂场景直接返回 cron
            return f"cron: {cron_expr}"
            
        except Exception:
            return cron_expr

    def _execute_scheduled_workflow(self, workflow_id: int, config: Dict[str, Any]):
        """
        执行定时工作流
        
        在后台线程中调用，需要处理异步执行
        
        Args:
            workflow_id: 工作流ID
            config: 工作流配置
        """
        from Core.utils.context import app_context
        
        with app_context():
            try:
                log_info(0, f"开始执行定时工作流: {config.get('name', workflow_id)}",
                         "SCHEDULED_WORKFLOW_START", workflow_id=workflow_id)
                # 在新的事件循环中执行异步任务
                asyncio.run(self._async_execute_workflow(workflow_id, config))
            except Exception as e:
                log_error(0, f"定时工作流执行失败: {e}", "SCHEDULED_WORKFLOW_ERROR",
                          workflow_id=workflow_id, error=str(e))

    async def _async_execute_workflow(self, workflow_id: int, config: Dict[str, Any]):
        """
        异步执行定时工作流
        
        只对订阅了该工作流的用户的活跃 bot 执行。
        注意: 调用者已经在同步入口推入了 app context
        
        Args:
            workflow_id: 工作流ID
            config: 工作流配置
        """
        from Core.workflow.engine import WorkflowEngine
        from Adapters import get_adapter_manager
        from Models.SQL.UserWorkflow import UserWorkflow
        from Models import Bot as BotModel
        
        # 获取订阅了该工作流的用户ID列表
        subscribed_user_ids = set()
        try:
            subscriptions = UserWorkflow.query.filter_by(
                workflow_id=workflow_id,
                enabled=True
            ).all()
            subscribed_user_ids = {sub.user_id for sub in subscriptions}
        except Exception as e:
            log_error(0, f"获取工作流订阅列表失败: {e}", "SCHEDULED_GET_SUBSCRIPTIONS_ERROR")
            
        if not subscribed_user_ids:
            log_debug(0, f"定时工作流无订阅用户: {config.get('name')}",
                      "SCHEDULED_WORKFLOW_NO_SUBSCRIBERS", workflow_id=workflow_id)
            return
        
        # 获取订阅用户的活跃 bot
        active_bots = []
        try:
            adapter_manager = get_adapter_manager()
            running_adapters = adapter_manager.running_adapters
            
            # 通过数据库查询订阅用户的 bot
            subscribed_bots = BotModel.query.filter(
                BotModel.owner_id.in_(subscribed_user_ids),
                BotModel.is_active == True
            ).all()
            subscribed_bot_ids = {b.id for b in subscribed_bots}
            
            # 过滤出订阅用户的活跃 bot
            for bot_id, adapter in running_adapters.items():
                if bot_id in subscribed_bot_ids:
                    bot = adapter.bot if hasattr(adapter, 'bot') else None
                    if bot:
                        active_bots.append(bot)
                    
        except Exception as e:
            log_error(0, f"获取订阅用户的活跃 bot 失败: {e}", "SCHEDULED_GET_BOTS_ERROR")
        
        if not active_bots:
            log_debug(0, f"定时工作流无活跃的订阅 bot: {config.get('name')}",
                      "SCHEDULED_WORKFLOW_NO_BOTS", workflow_id=workflow_id)
            return
        
        # 对每个订阅的 bot 执行工作流
        handled_count = 0
        for bot in active_bots:
            event = ScheduledEvent(
                workflow_name=config.get('name', str(workflow_id)),
                bot=bot
            )

            engine = WorkflowEngine(config, name=config.get('name'))
            try:
                result = await engine.execute(event)
            except Exception as e:
                log_error(0, f"工作流执行异常: {e}", "SCHEDULED_WORKFLOW_EXECUTE_ERROR",
                          workflow_id=workflow_id, bot_id=bot.self_id)
                result = {}

            if result.get('handled'):
                handled_count += 1
        
        if handled_count > 0:
            log_info(0, f"定时工作流执行完成: {config.get('name')} ({handled_count}/{len(active_bots)} bot)",
                     "SCHEDULED_WORKFLOW_DONE", workflow_id=workflow_id, handled=handled_count)
        else:
            log_debug(0, f"定时工作流未产生处理结果: {config.get('name')}",
                      "SCHEDULED_WORKFLOW_NO_RESPONSE", workflow_id=workflow_id)

    def sync_scheduled_workflows_from_cache(self, workflows: List[Dict[str, Any]]) -> int:
        """
        从工作流缓存同步定时任务

        Args:
            workflows: 工作流缓存列表

        Returns:
            int: 成功同步的定时任务数量
        """
        if not self.is_running():
            log_warn(0, "调度器未运行，跳过缓存同步", "SCHEDULER_SYNC_SKIPPED")
            return 0

        # 先清空现有任务映射（避免逐条 remove 产生噪音日志）
        for workflow_id, job_id in list(self._jobs.items()):
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        self._jobs.clear()

        scheduled_count = 0
        for workflow_item in workflows or []:
            if not workflow_item.get('enabled', True):
                continue

            workflow_id = workflow_item.get('id')
            config = dict(workflow_item.get('config') or {})
            trigger_type = workflow_item.get('trigger_type', config.get('trigger_type', 'message'))

            if trigger_type != 'schedule':
                continue

            if workflow_item.get('name') and 'name' not in config:
                config['name'] = workflow_item['name']

            if self.add_workflow_job(workflow_id, config):
                scheduled_count += 1

        log_info(0, f"定时任务缓存同步完成: {scheduled_count} 个任务",
                 "SCHEDULER_SYNC_FROM_CACHE_DONE", count=scheduled_count)
        return scheduled_count

    def get_jobs_info(self) -> List[Dict[str, Any]]:
        """
        获取所有任务信息
        
        Returns:
            List[Dict]: 任务信息列表
        """
        if not self._scheduler:
            return []

        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        return jobs


class ScheduledEvent:
    """
    定时工作流使用的模拟事件对象
    
    提供工作流执行所需的基本接口。
    定时工作流没有实际的消息来源，用户需要在工作流节点中自行配置发送目标。
    """

    def __init__(self, workflow_name: str, bot=None):
        """
        初始化定时事件
        
        Args:
            workflow_name: 工作流名称
            bot: 当前执行的 bot 实例
        """
        self.workflow_name = workflow_name
        
        # bot 实例由调度器传入
        self.bot = bot
        self.bot_id = bot.self_id if bot else None
        self.target_type = None
        self.target_id = None
        
        # 模拟消息属性（定时工作流没有实际消息）
        self.message = f"[定时任务: {workflow_name}]"
        self.message_id = None
        self.user_id = None
        self.group_id = None
        
        # 标记这是一个定时事件
        self.is_scheduled = True

    def get_target(self) -> str:
        """获取目标字符串（定时工作流无默认目标）"""
        return ""


# 全局单例实例
scheduler_service = SchedulerService()
