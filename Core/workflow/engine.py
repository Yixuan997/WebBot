"""
工作流执行引擎

负责加载工作流配置、执行节点、管理上下文
"""
import asyncio
import time
from typing import Any

from Core.logging.file_logger import log_info, log_error, log_debug
from Core.logging.utils import format_exception
from .context import WorkflowContext
from .registry import NodeRegistry
from .debug import WorkflowDebugRecorder


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, config: dict[str, Any], name: str = None, workflow_id: int = None):
        """
        初始化工作流引擎
        
        Args:
            config: 工作流配置字典
            name: 工作流名称（可选，优先使用此参数）
            workflow_id: 工作流 ID（用于调试记录）
        """
        self.config = config
        self.name = name or config.get('name', 'Unnamed Workflow')
        self.workflow_id = workflow_id
        self.workflow_steps = config.get('workflow', [])
        self.debug_recorder = None

    async def execute(self, event) -> dict[str, Any]:
        """
        执行工作流
        
        Args:
            event: BaseEvent 事件对象
            
        Returns:
            dict: {'handled': bool, 'response': BaseMessage, 'continue': bool}
        """
        start_time = time.time()

        try:
            # 1. 检查事件类型
            trigger_type = self.config.get('trigger_type', 'message')
            if trigger_type == 'message' and not hasattr(event, 'message'):
                return {'handled': False}

            # 2. 协议检查
            if not self._check_protocol(event):
                return {'handled': False}

            # 3. 初始化调试记录器
            if self.workflow_id:
                self.debug_recorder = WorkflowDebugRecorder(self.workflow_id, self.name)
                self.debug_recorder.start(event)

            # 4. 执行节点
            context = WorkflowContext(event)
            await self._run_nodes(context)

            # 5. 返回结果（并在有响应时保存调试记录）
            response = context.get_response()
            if response is not None:
                # 有响应时保存调试记录
                if self.debug_recorder:
                    self.debug_recorder.finish(success=True)
                    
                elapsed = time.time() - start_time
                log_info(0, f"[{self.name}] 处理完成 ({elapsed:.3f}s)", "WORKFLOW_SUCCESS")
                return {
                    'handled': True,
                    'response': response,
                    'continue': self.config.get('allow_continue', True)
                }
            return {'handled': False, 'response': None}

        except Exception as e:
            log_error(0, f"工作流 {self.name} 执行异常: {e}", "WORKFLOW_ERROR",
                      error=str(e), traceback=format_exception(e))
            # 记录异常
            if self.debug_recorder:
                self.debug_recorder.finish(success=False, error=str(e))
            return {'handled': False}

    async def _run_nodes(self, context: WorkflowContext):
        """执行所有节点"""
        node_index_map = {step.get('id'): idx for idx, step in enumerate(self.workflow_steps)}
        current_index = 0
        visited_nodes = set()
        loop_stack = []

        while current_index < len(self.workflow_steps):
            step_config = self.workflow_steps[current_index]
            node_type = step_config.get('type')
            node_id = step_config.get('id', f"step_{node_type}")

            # 检查循环跳转
            if node_id in visited_nodes:
                log_error(0, f"工作流 {self.name} 检测到循环跳转: {node_id}", "WORKFLOW_LOOP_DETECTED")
                break
            visited_nodes.add(node_id)

            try:
                # 执行单个节点（带调试记录）
                node_start = time.time()
                result, should_break = await self._execute_node(step_config, context)
                node_duration = int((time.time() - node_start) * 1000)

                # 记录节点执行结果
                if self.debug_recorder:
                    self.debug_recorder.record_node(
                        node_id=node_id,
                        node_type=node_type,
                        status="success",
                        output=result,
                        duration_ms=node_duration,
                        input_data=context.get_all_variables()
                    )

                if should_break:
                    break

                # 处理循环控制
                if isinstance(result, dict) and result.get('loop'):
                    jump_index = self._handle_loop_start(result, node_id, current_index, node_index_map, loop_stack, visited_nodes)
                    if jump_index is not None:
                        current_index = jump_index
                        if result.get('delay', 0) > 0:
                            await asyncio.sleep(result['delay'])
                        continue

                # 处理跳转
                if isinstance(result, dict) and 'next_node' in result:
                    next_id = result.get('next_node')
                    if next_id and next_id in node_index_map:
                        current_index = node_index_map[next_id]
                        continue
                    elif next_id:
                        log_error(0, f"节点 {node_id} 跳转到不存在的节点: {next_id}", "WORKFLOW_JUMP_ERROR")

                # 处理循环返回
                if loop_stack:
                    return_index = self._handle_loop_return(node_id, current_index, loop_stack, visited_nodes)
                    if return_index is not None:
                        current_index = return_index
                        continue

                current_index += 1

            except Exception as e:
                log_error(0, f"节点 {node_id} 执行失败: {e}", "WORKFLOW_NODE_ERROR",
                          error=str(e), node_type=node_type, traceback=format_exception(e))
                # 记录节点错误
                if self.debug_recorder:
                    self.debug_recorder.record_node(
                        node_id=node_id,
                        node_type=node_type,
                        status="error",
                        error=str(e),
                        input_data=context.get_all_variables()
                    )
                if step_config.get('on_fail'):
                    self._handle_error(step_config['on_fail'], context, e)
                current_index += 1

    async def _execute_node(self, step_config: dict, context: WorkflowContext) -> tuple[Any, bool]:
        """执行单个节点，返回 (result, should_break)"""
        node_type = step_config.get('type')
        node_id = step_config.get('id', f"step_{node_type}")

        node_class = NodeRegistry.get_node(node_type)
        if not node_class:
            log_error(0, f"未知的节点类型: {node_type}", "WORKFLOW_UNKNOWN_NODE")
            return None, False

        node = node_class(step_config.get('config', {}))
        result = await node.execute(context)

        if node.should_break(result):
            return result, True

        return result, False

    def _handle_loop_start(self, result: dict, node_id: str, current_index: int,
                           node_index_map: dict, loop_stack: list, visited_nodes: set) -> int | None:
        """处理循环开始，返回跳转索引或 None"""
        loop_body = result.get('loop_body')
        if not loop_body or loop_body not in node_index_map:
            log_error(0, f"foreach 循环体节点不存在: {loop_body}", "FOREACH_BODY_NOT_FOUND")
            return None

        loop_stack.append({
            'foreach_index': current_index,
            'foreach_id': node_id,
            'loop_body_index': node_index_map[loop_body],
            'loop_end': result.get('loop_end')
        })
        visited_nodes.discard(loop_body)
        return node_index_map[loop_body]

    def _handle_loop_return(self, node_id: str, current_index: int,
                            loop_stack: list, visited_nodes: set) -> int | None:
        """处理循环返回，返回 foreach 索引或 None"""
        loop_info = loop_stack[-1]
        loop_end_id = loop_info.get('loop_end')
        next_index = current_index + 1

        # 判断是否应返回 foreach
        if loop_end_id:
            should_return = (node_id == loop_end_id)
        else:
            next_node_type = self.workflow_steps[next_index].get('type') if next_index < len(self.workflow_steps) else None
            should_return = (
                next_index >= len(self.workflow_steps) or
                next_index <= loop_info['foreach_index'] or
                next_node_type == 'end' or
                (next_index < len(self.workflow_steps) and
                 self.workflow_steps[next_index].get('id') in visited_nodes)
            )

        if not should_return:
            return None

        loop_stack.pop()
        visited_nodes.discard(loop_info['foreach_id'])
        for idx in range(loop_info['loop_body_index'], current_index + 1):
            if idx < len(self.workflow_steps):
                visited_nodes.discard(self.workflow_steps[idx].get('id'))
        return loop_info['foreach_index']

    def _check_protocol(self, event) -> bool:
        """
        检查工作流是否支持当前协议
        
        根据工作流配置中的 protocols 字段检查当前事件的协议是否在允许列表中。
        如果 protocols 为空或未配置，则允许所有协议。
        
        Args:
            event: 事件对象，必须包含 bot.adapter
            
        Returns:
            bool: 是否支持当前协议
        """
        allowed_protocols = self.config.get('protocols')
        if not allowed_protocols:
            return True

        current_protocol = event.bot.adapter.get_protocol_name()
        return current_protocol in allowed_protocols

    def _handle_error(self, error_config: dict[str, Any], context: WorkflowContext, error: Exception):
        """
        处理错误
        
        Args:
            error_config: 错误处理配置
            context: 执行上下文
            error: 异常对象
        """
        action = error_config.get('action')
        if action == 'send_message':
            from Core.message.builder import MessageBuilder
            message = error_config.get('message', '处理失败')
            context.set_response(MessageBuilder.text(message))
