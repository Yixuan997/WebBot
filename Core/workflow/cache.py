"""
工作流缓存管理器

提供内存缓存，避免每次消息都查询数据库
预编译工作流引擎，提高执行效率
"""
import threading
from collections import Counter
from typing import List, Dict, Any, Optional

from Core.logging.file_logger import log_info, log_debug, log_error


class WorkflowCache:
    """工作流缓存管理器（单例）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化缓存"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._workflows: List[Dict[str, Any]] = []  # 工作流列表
            self._lock = threading.RLock()
            log_info(0, "工作流缓存管理器初始化", "WORKFLOW_CACHE_INIT")

    def _build_cached_workflow(self, workflow) -> Dict[str, Any]:
        """构建缓存项（含预编译引擎）"""
        config = workflow.get_config()
        trigger_type = config.get('trigger_type', 'message')
        return {
            'id': workflow.id,
            'name': workflow.name,
            'priority': workflow.priority,
            'config': config,
            'enabled': workflow.enabled,
            'trigger_type': trigger_type,
            'engine': self._precompile_engine(workflow.id, workflow.name, config),
        }

    def reload(self) -> int:
        """
        从数据库重新加载工作流到缓存
            
        Returns:
            int: 加载的工作流数量
        """
        from Core.utils.context import app_context
        
        with self._lock:
            try:
                with app_context():
                    from Models.SQL.Workflow import Workflow

                    # 查询所有启用的工作流，按优先级排序
                    workflows = Workflow.query.filter_by(enabled=True).order_by(
                        Workflow.priority.asc()
                    ).all()

                    # 清空现有缓存
                    self._workflows.clear()

                    # 加载工作流并预编译引擎
                    type_counter = Counter()
                    for workflow in workflows:
                        cached_workflow = self._build_cached_workflow(workflow)
                        trigger_type = cached_workflow['trigger_type']
                        type_counter[trigger_type] += 1
                        self._workflows.append(cached_workflow)

                    log_info(0, f"工作流缓存已重载: {len(self._workflows)} 个工作流 "
                             f"(消息: {type_counter['message']}, 定时: {type_counter['schedule']}, "
                             f"通知: {type_counter['notice']}, 请求: {type_counter['request']})",
                             "WORKFLOW_CACHE_RELOAD",
                             count=len(self._workflows), **{f'{k}_count': v for k, v in type_counter.items()})
                    
                    return len(self._workflows)

            except Exception as e:
                log_error(0, f"重载工作流缓存失败: {e}", "WORKFLOW_CACHE_RELOAD_ERROR", error=str(e))
                return 0

    def upsert_by_id(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        """
        按 ID 增量刷新单个工作流缓存

        Args:
            workflow_id: 工作流 ID

        Returns:
            Optional[Dict[str, Any]]: 缓存项；若工作流不存在或未启用，返回 None
        """
        from Core.utils.context import app_context

        with self._lock:
            try:
                with app_context():
                    from Models.SQL.Workflow import Workflow

                    workflow = Workflow.query.get(workflow_id)

                    # 先移除旧缓存，再按当前状态决定是否回填
                    self._workflows = [w for w in self._workflows if w['id'] != workflow_id]

                    if not workflow or not workflow.enabled:
                        log_debug(0, "增量刷新工作流缓存：工作流不存在或未启用",
                                  "WORKFLOW_CACHE_UPSERT_SKIPPED", workflow_id=workflow_id)
                        return None

                    cached_workflow = self._build_cached_workflow(workflow)
                    self._workflows.append(cached_workflow)
                    self._workflows.sort(key=lambda item: item.get('priority', 100))

                    log_debug(0, "增量刷新工作流缓存成功", "WORKFLOW_CACHE_UPSERT_OK",
                              workflow_id=workflow_id, trigger_type=cached_workflow.get('trigger_type'))
                    return cached_workflow
            except Exception as e:
                log_error(0, f"增量刷新工作流缓存失败: {e}",
                          "WORKFLOW_CACHE_UPSERT_ERROR", workflow_id=workflow_id, error=str(e))
                return None

    def remove_by_id(self, workflow_id: int) -> bool:
        """
        按 ID 从缓存移除工作流

        Args:
            workflow_id: 工作流 ID

        Returns:
            bool: 是否有缓存项被移除
        """
        with self._lock:
            before_count = len(self._workflows)
            self._workflows = [w for w in self._workflows if w['id'] != workflow_id]
            removed = len(self._workflows) < before_count
            if removed:
                log_debug(0, "已从缓存移除工作流", "WORKFLOW_CACHE_REMOVE_BY_ID",
                          workflow_id=workflow_id)
            return removed

    def _precompile_engine(self, workflow_id: int, workflow_name: str, config: Dict[str, Any]):
        """
        预编译工作流引擎
        
        Args:
            workflow_id: 工作流 ID
            workflow_name: 工作流名称
            config: 工作流配置
            
        Returns:
            WorkflowEngine: 预编译好的引擎实例，失败返回None
        """
        try:
            from Core.workflow.engine import WorkflowEngine

            # 创建引擎实例（传入 workflow_id 用于调试记录）
            engine = WorkflowEngine(config, name=workflow_name, workflow_id=workflow_id)

            log_debug(0, f"预编译工作流引擎: {workflow_name}", "WORKFLOW_PRECOMPILE_SUCCESS",
                      workflow=workflow_name,
                      steps_count=len(config.get('workflow', [])))

            return engine

        except Exception as e:
            log_error(0, f"预编译工作流 {workflow_name} 失败: {e}",
                      "WORKFLOW_PRECOMPILE_ERROR",
                      workflow=workflow_name,
                      error=str(e))
            return None

    def _get_subscribed_workflow_ids(self, user_id: Optional[int]) -> set:
        """获取用户订阅的工作流ID集合"""
        if not user_id:
            return set()
        try:
            from Models.SQL.UserWorkflow import UserWorkflow
            subscriptions = UserWorkflow.query.filter_by(
                user_id=user_id,
                enabled=True
            ).all()
            return {sub.workflow_id for sub in subscriptions}
        except Exception as e:
            log_error(0, f"获取用户订阅列表失败: {e}", "WORKFLOW_GET_SUBSCRIPTIONS_ERROR")
            return set()

    def get_workflows_by_trigger(self, trigger_type: str, protocol: Optional[str] = None,
                                  user_id: Optional[int] = None, event_name: str = '') -> List[Dict[str, Any]]:
        """
        根据触发类型获取工作流
        
        Args:
            trigger_type: 触发类型 ('message', 'notice', 'request')
            protocol: 协议类型（可选）
            user_id: 用户ID（bot 所有者），用于订阅过滤
            event_name: 具体事件名称（notice/request 时用，如 'group_increase'）
            
        Returns:
            List[Dict]: 匹配的工作流列表
        """
        from Core.utils.context import app_context
        
        with app_context():
            with self._lock:
                subscribed_ids = self._get_subscribed_workflow_ids(user_id)
                
                result = []
                for workflow in self._workflows:
                    wf_trigger = workflow.get('trigger_type', 'message')
                    if wf_trigger != trigger_type:
                        continue
                    
                    config = workflow.get('config', {})
                    
                    # 事件名称过滤（notice/request 事件）
                    if event_name:
                        event_filter = config.get('event_filter', [])
                        if event_filter and event_name not in event_filter:
                            continue
                    
                    # 订阅过滤
                    if user_id and workflow['id'] not in subscribed_ids:
                        continue
                    
                    # 协议过滤
                    if protocol:
                        allowed = config.get('protocols', [])
                        if allowed and protocol not in allowed:
                            continue
                    
                    result.append(workflow)
                
                return result

    def get_all_workflows(self) -> List[Dict[str, Any]]:
        """获取所有缓存的工作流"""
        with self._lock:
            return list(self._workflows)

    def get_workflow_by_id(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取工作流"""
        with self._lock:
            for workflow in self._workflows:
                if workflow['id'] == workflow_id:
                    return workflow
            return None

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._workflows.clear()
            log_info(0, "工作流缓存已清空", "WORKFLOW_CACHE_CLEAR")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self._lock:
            return {
                'total_workflows': len(self._workflows),
                'workflows': [
                    {
                        'id': w['id'],
                        'name': w['name'],
                        'priority': w['priority']
                    }
                    for w in self._workflows
                ]
            }


# 全局单例实例
workflow_cache = WorkflowCache()
