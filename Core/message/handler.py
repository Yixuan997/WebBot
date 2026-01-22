"""
消息处理器
"""
import asyncio
from Core.utils.context import app_context


class MessageHandler:
    """消息处理器"""

    async def _async_process_message(self, event, bot_id=None):
        """
        异步处理消息
        
        Args:
            event: BaseEvent对象
            bot_id: 机器人 id
        """
        try:
            from Core.logging.file_logger import log_error, log_info, log_debug
            from Core.message.builder import MessageBuilder
            
            # 跳过元事件（心跳、生命周期等），这些不需要工作流处理
            # 保留 Notice、Request、Message 事件
            event_type = type(event).__name__
            if 'Meta' in event_type:
                return

            # 设置当前 event
            MessageBuilder.set_current_event(event)

            # 从event中获取信息
            if not bot_id and hasattr(event, 'bot'):
                bot_id = event.bot.adapter.bot_id

            # 从缓存获取匹配的工作流
            from Core.workflow.cache import workflow_cache
            from Models import Bot as BotModel

            # 获取协议类型
            protocol = event.bot.adapter.get_protocol_name() if hasattr(event, 'bot') else None
            
            # 获取 bot 所有者的用户ID
            owner_id = None
            if hasattr(event, 'bot') and event.bot:
                with app_context():
                    try:
                        db_bot_id = event.bot.adapter.bot_id
                        bot_db = BotModel.query.get(db_bot_id)
                        if bot_db:
                            owner_id = bot_db.owner_id
                    except Exception as e:
                        log_debug(0, f"获取 owner_id 失败: {e}", "GET_OWNER_ID_ERROR")

            # 根据事件类型获取工作流
            post_type = getattr(event, 'post_type', 'message')
            
            if post_type == 'notice':
                # 通知事件（群成员增减、管理员变动等）
                notice_type = getattr(event, 'notice_type', '')
                log_info(0, f"通知事件: {notice_type}", "NOTICE_EVENT_RECEIVED",
                         notice_type=notice_type,
                         group_id=getattr(event, 'group_id', None),
                         user_id=getattr(event, 'user_id', None))
                workflows = workflow_cache.get_workflows_by_trigger('notice', protocol, owner_id, notice_type)
                
            elif post_type == 'request':
                # 请求事件（好友申请、入群申请等）
                request_type = getattr(event, 'request_type', '')
                log_info(0, f"请求事件: {request_type}", "REQUEST_EVENT_RECEIVED",
                         request_type=request_type,
                         user_id=getattr(event, 'user_id', None),
                         comment=getattr(event, 'comment', ''))
                workflows = workflow_cache.get_workflows_by_trigger('request', protocol, owner_id, request_type)
                
            else:
                # 消息事件
                content = event.get_plaintext().strip()
                
                # 记录消息摘要
                group_id = getattr(event, 'group_id', None)
                user_id = getattr(event, 'user_id', None)
                msg_summary = f"群{group_id}" if group_id else "私聊"
                msg_summary += f" 用户{user_id}" if user_id else ""
                msg_summary += f": \"{content[:20]}{'...' if len(content) > 20 else ''}\""
                log_info(0, msg_summary, "MESSAGE_RECEIVED")
                
                workflows = workflow_cache.get_workflows_by_trigger('message', protocol, owner_id)

            # 如果没有匹配的工作流，静默返回（不记录日志）
            if not workflows:
                return

            message_handled = False

            # 创建所有工作流的任务，使用 dict 映射 task -> workflow_data
            task_to_workflow = {}
            for workflow_data in workflows:
                # 在当前事件循环中创建异步任务
                loop = asyncio.get_event_loop()
                task = loop.create_task(
                    self._async_execute_workflow(workflow_data, event)
                )
                task_to_workflow[task] = workflow_data

            # 使用 asyncio.wait 实现即时响应

            pending = set(task_to_workflow.keys())

            while pending:
                # 等待任意一个任务完成
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    workflow_data = task_to_workflow[task]
                    workflow_name = workflow_data['name']
                    workflow_priority = workflow_data['priority']

                    try:
                        result = task.result()

                        if result.get('handled'):
                            # 发送响应（仅当是 BaseMessage 时）
                            response = result.get('response')
                            if response:
                                from Adapters.base.message import BaseMessage
                                if isinstance(response, BaseMessage):
                                    await self._async_send_response(event, response)

                            message_handled = True

                    except Exception as e:
                        log_error(bot_id, f"工作流 {workflow_name} 执行异常: {e}",
                                  "WORKFLOW_EXECUTION_ERROR", error=str(e), workflow=workflow_name)

        except Exception as e:
            import traceback
            from Core.logging.file_logger import log_error
            log_error(bot_id or 0, f"异步消息处理异常: {e}", "ASYNC_MESSAGE_HANDLER_ERROR", error=str(e))
            log_error(bot_id or 0, f"异步消息处理异常堆栈", "ASYNC_MESSAGE_HANDLER_TRACEBACK",
                      traceback=traceback.format_exc())

        finally:
            # 清除 current_event
            from Core.message.builder import MessageBuilder
            MessageBuilder.clear_current_event()

    async def _async_execute_workflow(self, workflow_data, event):
        """
        异步执行工作流
        
        Args:
            workflow_data: 工作流数据字典
            event: BaseEvent对象
            
        Returns:
            dict: 工作流执行结果
        """
        from Core.workflow.engine import WorkflowEngine

        with app_context():
            # 优先使用预编译的引擎
            engine = workflow_data.get('engine')

            if not engine:
                # 降级方案：动态创建引擎（如果预编译失败）
                from Core.logging.file_logger import log_debug
                workflow_config = workflow_data['config']
                workflow_name = workflow_data['name']
                workflow_id = workflow_data.get('id')

                log_debug(0, f"预编译引擎不存在，动态创建: {workflow_name}",
                          "WORKFLOW_FALLBACK_CREATE")

                engine = WorkflowEngine(workflow_config, name=workflow_name, workflow_id=workflow_id)

            # 异步执行工作流
            result = await engine.execute(event)
            return result

    async def _async_send_response(self, event, response, timeout=30):
        """
        异步发送响应
        
        Args:
            event: BaseEvent对象
            response: BaseMessage对象
            timeout: 超时时间（秒）
        """
        try:
            from Core.logging.file_logger import log_debug, log_error
            from Adapters.base.message import BaseMessage

            # 验证是 BaseMessage 对象
            if not isinstance(response, BaseMessage):
                log_error(event.bot.adapter.bot_id,
                          f"响应必须是 BaseMessage 对象，得到: {type(response)}",
                          "INVALID_RESPONSE_TYPE")
                return

            # 异步发送消息（带超时）
            try:
                await asyncio.wait_for(
                    event.bot.send(event, response),
                    timeout=timeout
                )

            except asyncio.TimeoutError:
                log_error(event.bot.adapter.bot_id,
                          f"发送消息超时({timeout}秒)",
                          "ASYNC_SEND_TIMEOUT")
            except Exception as e:
                log_error(event.bot.adapter.bot_id,
                          f"异步发送消息失败: {e}",
                          "ASYNC_SEND_ERROR", error=str(e))

        except Exception as e:
            from Core.logging.file_logger import log_error
            log_error(0, f"发送响应失败: {e}", "SEND_RESPONSE_ERROR", error=str(e))
