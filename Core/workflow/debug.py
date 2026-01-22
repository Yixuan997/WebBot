"""
工作流调试记录模块

保存和读取工作流执行的调试信息到 Redis
"""
import json
import time
from typing import Any

from Core.logging.file_logger import log_error

# Redis key 前缀
DEBUG_KEY_PREFIX = "workflow_debug:"
# 调试记录过期时间（秒），默认 1 小时
DEBUG_EXPIRE_SECONDS = 3600


class WorkflowDebugRecorder:
    """工作流调试记录器"""

    def __init__(self, workflow_id: int, workflow_name: str):
        """
        初始化调试记录器
        
        Args:
            workflow_id: 工作流 ID
            workflow_name: 工作流名称
        """
        self.workflow_id = workflow_id
        self.workflow_name = workflow_name
        self.nodes = []
        self.trigger_time = None
        self.trigger_message = None
        self.user_id = None
        self.group_id = None
        self.status = "running"
        self.error = None

    def start(self, event):
        """
        开始记录，提取触发信息
        
        Args:
            event: 事件对象
        """
        self.trigger_time = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 提取消息内容
        if hasattr(event, 'message') and event.message:
            self.trigger_message = str(event.message)
        else:
            self.trigger_message = "(非消息事件)"
        
        # 提取用户和群信息
        if hasattr(event, 'user_id'):
            self.user_id = event.user_id
        if hasattr(event, 'group_id'):
            self.group_id = event.group_id

    def record_node(self, node_id: str, node_type: str, status: str,
                    output: Any = None, error: str = None, duration_ms: int = 0,
                    input_data: dict = None):
        """
        记录节点执行结果
        
        Args:
            node_id: 节点 ID
            node_type: 节点类型
            status: 执行状态 (success/error/skipped)
            output: 输出数据（会被截断）
            error: 错误信息
            duration_ms: 执行时长（毫秒）
            input_data: 输入数据（上下文变量）
        """
        # 处理 output，确保可序列化且不过长
        output_str = self._serialize_data(output)
        input_str = self._serialize_data(input_data)

        self.nodes.append({
            "id": node_id,
            "type": node_type,
            "status": status,
            "input": input_str,
            "output": output_str,
            "error": error[:500] if error else None,
            "duration_ms": duration_ms
        })
    
    def _serialize_data(self, data: Any) -> Any:
        """序列化数据"""
        if data is None:
            return None
        try:
            serialized = json.dumps(data, ensure_ascii=False, default=str)
            return json.loads(serialized)
        except Exception as e:
            return f"(序列化失败: {str(e)[:100]})"

    def finish(self, success: bool, error: str = None):
        """
        结束记录并保存到 Redis
        
        Args:
            success: 是否成功
            error: 错误信息
        """
        self.status = "success" if success else "error"
        self.error = error[:500] if error else None
        
        # 保存到 Redis
        self._save_to_redis()

    def _save_to_redis(self):
        """保存调试记录到 Redis（按 workflow_id 分开存储）"""
        try:
            from Database.Redis.client import set_value
            
            record = {
                "workflow_id": self.workflow_id,
                "workflow_name": self.workflow_name,
                "trigger_time": self.trigger_time,
                "trigger_message": self.trigger_message,
                "user_id": self.user_id,
                "group_id": self.group_id,
                "status": self.status,
                "error": self.error,
                "nodes": self.nodes
            }
            
            key = f"{DEBUG_KEY_PREFIX}{self.workflow_id}"
            value = json.dumps(record, ensure_ascii=False)
            set_value(key, value, expire_seconds=DEBUG_EXPIRE_SECONDS)
            
        except Exception as e:
            log_error(0, f"保存工作流调试记录失败: {e}", "WORKFLOW_DEBUG_SAVE_ERROR",
                      workflow_id=self.workflow_id, error=str(e))


def get_debug_record(workflow_id: int) -> dict | None:
    """
    获取指定工作流的调试记录
    
    Args:
        workflow_id: 工作流 ID
        
    Returns:
        调试记录字典，如果不存在返回 None
    """
    try:
        from Database.Redis.client import get_value
        
        key = f"{DEBUG_KEY_PREFIX}{workflow_id}"
        value = get_value(key)
        
        if value:
            if isinstance(value, bytes):
                value = value.decode('utf-8')
            return json.loads(value)
        return None
        
    except Exception as e:
        log_error(0, f"获取工作流调试记录失败: {e}", "WORKFLOW_DEBUG_GET_ERROR",
                  workflow_id=workflow_id, error=str(e))
        return None


def clear_debug_record(workflow_id: int):
    """清除指定工作流的调试记录"""
    try:
        from Database.Redis.client import delete_key
        key = f"{DEBUG_KEY_PREFIX}{workflow_id}"
        delete_key(key)
    except Exception as e:
        log_error(0, f"清除工作流调试记录失败: {e}", "WORKFLOW_DEBUG_CLEAR_ERROR",
                  workflow_id=workflow_id, error=str(e))
