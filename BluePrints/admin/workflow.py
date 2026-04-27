"""
@Project：WebBot
@File   ：workflow.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/12/21
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import requests
from flask import render_template, request, flash, redirect, url_for, jsonify, g, Response, stream_with_context

from Core.logging.file_logger import log_info, log_error
from Core.protocols import list_protocols
from Core.workflow.registry import NodeRegistry
from Models import db, GlobalVariable
from Models.SQL.Workflow import Workflow
from utils.page_utils import adapt_pagination


AI_EDGE_FIELDS = ('next_node', 'true_branch', 'false_branch', 'loop_body')


def _clear_workflow_cache(workflow_id: Optional[int] = None, remove: bool = False):
    """刷新工作流缓存（支持全量与单条增量）"""
    try:
        from Core.workflow.cache import workflow_cache
        from Core.scheduler import scheduler_service

        # 全量重载（手动重载入口使用）
        if workflow_id is None:
            workflow_cache.reload()
            if scheduler_service.is_running():
                scheduler_service.sync_scheduled_workflows_from_cache(workflow_cache.get_all_workflows())
            return

        # 单条删除（缓存 + 调度器）
        if remove:
            workflow_cache.remove_by_id(workflow_id)
            if scheduler_service.is_running():
                scheduler_service.remove_workflow_job(workflow_id)
            return

        # 单条更新（缓存 + 调度器）
        workflow_item = workflow_cache.upsert_by_id(workflow_id)
        if scheduler_service.is_running():
            if workflow_item and workflow_item.get('trigger_type') == 'schedule':
                schedule_config = dict(workflow_item.get('config') or {})
                if workflow_item.get('name') and 'name' not in schedule_config:
                    schedule_config['name'] = workflow_item['name']
                scheduler_service.update_workflow_job(workflow_id, schedule_config)
            else:
                scheduler_service.remove_workflow_job(workflow_id)
    except Exception as e:
        log_error(0, f"重载工作流缓存失败: {e}", "WORKFLOW_CACHE_RELOAD_ERROR", error=str(e))


def _get_available_nodes() -> list[dict]:
    """获取所有可用的工作流节点
    
    Returns:
        list[dict]: 节点信息列表
    """
    available_nodes = []

    for node_type, node_class in NodeRegistry.list_all().items():
        if node_class:
            # 获取 config_schema：支持静态属性和 @property 动态属性
            config_schema = []
            try:
                # 尝试通过实例化获取（支持 @property）
                temp_instance = node_class({})
                config_schema = getattr(temp_instance, 'config_schema', [])
            except Exception:
                # 回退到类属性
                config_schema = getattr(node_class, 'config_schema', [])

            node_info = {
                'type': node_type,
                'name': getattr(node_class, 'name', node_type),
                'description': getattr(node_class, 'description', ''),
                'category': getattr(node_class, 'category', 'core'),
                'icon': getattr(node_class, 'icon', '📦'),
                'config_schema': config_schema,
                'inputs': getattr(node_class, 'inputs', []),
                'outputs': getattr(node_class, 'outputs', [])
            }
            available_nodes.append(node_info)

    return available_nodes


def _load_ai_prompt() -> str:
    """加载 AI 生成工作流的系统提示词。"""
    prompt_path = Path(__file__).resolve().parents[1] / 'docs' / 'docs' / 'workflow-ai-prompt.md'
    try:
        return prompt_path.read_text(encoding='utf-8')
    except Exception as e:
        log_error(0, f"读取 AI 提示词失败: {e}", "WORKFLOW_AI_PROMPT_LOAD_ERROR", error=str(e))
        return ""


def _extract_json_block(text: str) -> str:
    """从 AI 输出中提取 JSON 文本。"""
    raw = (text or '').strip()
    if not raw:
        return ''

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    start = raw.find('{')
    end = raw.rfind('}')
    if start >= 0 and end > start:
        return raw[start:end + 1].strip()
    return raw


def _validate_workflow_ai_config(config: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """校验 AI 生成的工作流配置是否可落库。"""
    if not isinstance(config, dict):
        return False, '工作流配置必须是 JSON 对象', {}

    name = str(config.get('name', '')).strip()
    if not name:
        return False, '工作流名称不能为空', {}

    steps = config.get('workflow')
    if not isinstance(steps, list) or not steps:
        return False, 'workflow 节点列表不能为空', {}

    node_ids: list[str] = []
    node_types: dict[str, str] = {}
    id_set = set()
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f'第 {idx + 1} 个节点格式错误', {}

        node_id = str(step.get('id', '')).strip()
        node_type = str(step.get('type', '')).strip()
        node_config = step.get('config', {})

        if not node_id or not node_type:
            return False, f'第 {idx + 1} 个节点缺少 id/type', {}
        if node_id in id_set:
            return False, f'节点 ID 重复: {node_id}', {}
        if not isinstance(node_config, dict):
            return False, f'节点 {node_id} 的 config 必须是对象', {}

        id_set.add(node_id)
        node_ids.append(node_id)
        node_types[node_id] = node_type

    if 'start' not in id_set or node_types.get('start') != 'start':
        return False, '必须包含 id=start 且 type=start 的开始节点', {}
    if 'end' not in id_set or node_types.get('end') != 'end':
        return False, '必须包含 id=end 且 type=end 的结束节点', {}

    available_node_types = set(NodeRegistry.list_all().keys())
    for node_id, node_type in node_types.items():
        if node_type not in available_node_types:
            return False, f'存在未知节点类型: {node_type} ({node_id})', {}

    refs: list[tuple[str, str, str]] = []
    for step in steps:
        node_id = str(step.get('id', '')).strip()
        node_type = str(step.get('type', '')).strip()
        cfg = step.get('config', {}) or {}
        if node_type == 'end':
            continue

        has_edge = False
        for field in AI_EDGE_FIELDS:
            target = cfg.get(field)
            if target:
                has_edge = True
                refs.append((node_id, field, str(target).strip()))
        if not has_edge:
            return False, f'节点 {node_id} 未配置显式连线（next_node/true_branch/false_branch/loop_body）', {}

    for source_id, field, target_id in refs:
        if target_id not in id_set:
            return False, f'节点 {source_id} 的 {field} 指向不存在节点: {target_id}', {}
        if source_id == target_id:
            return False, f'节点 {source_id} 的 {field} 不能指向自身', {}

    result = {
        'name': name,
        'description': str(config.get('description', '')).strip(),
        'protocols': config.get('protocols') if isinstance(config.get('protocols'), list) else [],
        'trigger_type': str(config.get('trigger_type', 'message') or 'message'),
        'allow_continue': bool(config.get('allow_continue', True)),
        'workflow': steps
    }

    if result['trigger_type'] == 'schedule':
        schedule = config.get('schedule')
        if not isinstance(schedule, dict):
            return False, '定时工作流缺少 schedule 配置', {}
        result['schedule'] = schedule

    return True, '', result


def _request_openai_compatible(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str
) -> tuple[bool, str]:
    """调用 OpenAI 兼容 HTTP API（chat/completions）。"""
    if not base_url or not api_key or not model:
        return False, '缺少 AI 配置（base_url/api_key/model）'

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    chat_url = _build_ai_url(base_url, '/chat/completions')
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
    }

    try:
        mode = 'chat'
        log_info(
            0,
            "AI 接口请求开始",
            "WORKFLOW_AI_REQUEST_START",
            base_url=base_url,
            request_url=chat_url,
            model=model,
            mode=mode,
        )

        response = requests.post(chat_url, headers=headers, json=payload, timeout=60)
        if response.status_code >= 400:
            log_error(
                0,
                "AI 接口返回非成功状态码",
                "WORKFLOW_AI_REQUEST_HTTP_ERROR",
                request_url=chat_url,
                status_code=response.status_code,
                response_body=response.text[:1200],
                model=model,
                mode=mode,
            )
            return False, f'AI 接口调用失败: HTTP {response.status_code} {response.text[:300]}'

        data = response.json()
        content = _extract_chat_message_content(data)
        if not content:
            return False, 'AI 返回内容为空（message.content 为空）'

        log_info(
            0,
            "AI 接口请求成功",
            "WORKFLOW_AI_REQUEST_SUCCESS",
            request_url=chat_url,
            model=model,
            mode=mode,
        )
        return True, str(content)
    except requests.RequestException as e:
        log_error(0, "AI 接口请求异常", "WORKFLOW_AI_REQUEST_EXCEPTION",
                  request_url=base_url, error=str(e), model=model)
        return False, f'AI 接口请求失败: {e}'
    except Exception as e:
        log_error(0, "AI 接口响应解析异常", "WORKFLOW_AI_RESPONSE_PARSE_EXCEPTION",
                  request_url=base_url, error=str(e), model=model)
        return False, f'AI 接口解析失败: {e}'


def _build_ai_url(base: str, suffix: str) -> str:
    url_base = (base or '').rstrip('/')
    if url_base.endswith(suffix):
        return url_base
    return f"{url_base}{suffix}"


def _extract_chat_message_content(data: dict[str, Any]) -> str:
    choices = data.get('choices') or []
    if not choices:
        return ''
    message = choices[0].get('message') or {}
    content = message.get('content') if isinstance(message, dict) else ''
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                txt = part.get('text')
                if isinstance(txt, str) and txt.strip():
                    text_parts.append(txt.strip())
        return "\n".join(text_parts).strip()
    return str(content or '').strip()


def _extract_chat_delta_text(chunk: dict[str, Any]) -> str:
    choices = chunk.get('choices') or []
    if not choices:
        return ''
    delta = choices[0].get('delta') or {}
    content = delta.get('content')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                txt = part.get('text')
                if isinstance(txt, str) and txt:
                    text_parts.append(txt)
        return ''.join(text_parts)
    return ''


def _sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def workflow_list():
    """工作流列表页面"""
    try:
        # 获取分页和搜索参数
        page = request.args.get('page', 1, type=int)
        search = request.args.get('search', '', type=str).strip()
        per_page = 10

        # 构建查询
        query = Workflow.query

        # 搜索过滤
        if search:
            query = query.filter(Workflow.name.ilike(f'%{search}%'))

        # 按 ID 倒序（最新创建的在前）
        pagination = query.order_by(
            Workflow.id.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        workflows = pagination.items
        
        # 使用智能分页
        page_numbers = adapt_pagination(pagination)

        protocol_options = list_protocols()
        protocol_name_map = {item['id']: item['name'] for item in protocol_options}

        return render_template('admin/workflow/list.html',
                               workflows=workflows,
                               pagination=pagination,
                               page_numbers=page_numbers,
                               search=search,
                               current_page=page,
                               protocol_options=protocol_options,
                               protocol_name_map=protocol_name_map)

    except Exception as e:
        log_error(0, f"获取工作流列表失败: {e}", "WORKFLOW_LIST_ERROR", error=str(e))
        flash('获取工作流列表失败', 'error')
        return render_template('admin/workflow/list.html', workflows=[], pagination=None,
                               protocol_options=list_protocols(), protocol_name_map={})


def workflow_ai_page():
    """AI 生成工作流页面。"""
    return render_template('admin/workflow/ai.html')


def workflow_ai_config_get():
    """读取 AI 配置（数据库）。"""
    try:
        base_url_var = GlobalVariable.get_by_key('workflow_ai_base_url')
        model_var = GlobalVariable.get_by_key('workflow_ai_model')
        api_key_var = GlobalVariable.get_by_key('workflow_ai_api_key')

        return jsonify({
            'success': True,
            'config': {
                'base_url': base_url_var.value if base_url_var else '',
                'model': model_var.value if model_var else '',
                'api_key': api_key_var.value if api_key_var else '',
            }
        })
    except Exception as e:
        log_error(0, f"读取 AI 配置失败: {e}", "WORKFLOW_AI_CONFIG_GET_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'读取配置失败: {e}'})


def workflow_ai_config_save():
    """保存 AI 配置（数据库）。"""
    try:
        data = request.get_json(silent=True) or {}
        base_url = str(data.get('base_url', '')).strip()
        model = str(data.get('model', '')).strip()
        api_key = str(data.get('api_key', '')).strip()

        GlobalVariable.set_value(
            'workflow_ai_base_url',
            base_url,
            description='AI 工作流生成接口地址',
            is_secret=False
        )
        GlobalVariable.set_value(
            'workflow_ai_model',
            model,
            description='AI 工作流生成模型',
            is_secret=False
        )
        GlobalVariable.set_value(
            'workflow_ai_api_key',
            api_key,
            description='AI 工作流生成 API Key',
            is_secret=True
        )
        return jsonify({'success': True, 'message': 'AI 配置已保存到数据库'})
    except Exception as e:
        log_error(0, f"保存 AI 配置失败: {e}", "WORKFLOW_AI_CONFIG_SAVE_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'保存配置失败: {e}'})


def workflow_ai_generate():
    """调用 AI 生成工作流，并执行结构校验后返回预览。"""
    try:
        data = request.get_json(silent=True) or {}
        base_url = str(data.get('base_url', '')).strip()
        api_key = str(data.get('api_key', '')).strip()
        model = str(data.get('model', '')).strip()
        prompt = str(data.get('prompt', '')).strip()

        if not prompt:
            return jsonify({'success': False, 'message': '需求描述不能为空'})

        system_prompt = _load_ai_prompt()
        if not system_prompt:
            return jsonify({'success': False, 'message': 'AI 提示词文件不存在或读取失败'})

        ok, ai_result = _request_openai_compatible(
            base_url=base_url,
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            user_prompt=prompt
        )
        if not ok:
            return jsonify({'success': False, 'message': ai_result})

        json_text = _extract_json_block(ai_result)
        try:
            workflow_config = json.loads(json_text)
        except json.JSONDecodeError as e:
            return jsonify({
                'success': False,
                'message': f'AI 返回不是有效 JSON: {e}',
                'raw_output': ai_result
            })

        valid, err, normalized = _validate_workflow_ai_config(workflow_config)
        if not valid:
            return jsonify({
                'success': False,
                'message': f'结构校验未通过: {err}',
                'workflow': workflow_config,
                'raw_output': ai_result
            })

        return jsonify({
            'success': True,
            'message': '生成成功，结构校验通过',
            'workflow': normalized,
            'raw_output': ai_result
        })

    except Exception as e:
        log_error(0, f"AI 生成工作流失败: {e}", "WORKFLOW_AI_GENERATE_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'AI 生成失败: {e}'})


def workflow_ai_generate_stream():
    """调用 AI 流式生成工作流（SSE）。"""
    data = request.get_json(silent=True) or {}
    base_url = str(data.get('base_url', '')).strip()
    api_key = str(data.get('api_key', '')).strip()
    model = str(data.get('model', '')).strip()
    prompt = str(data.get('prompt', '')).strip()

    @stream_with_context
    def event_stream():
        try:
            if not prompt:
                msg = '需求描述不能为空'
                yield _sse_event('error', {'message': msg})
                yield _sse_event('done', {'success': False, 'message': msg})
                return

            system_prompt = _load_ai_prompt()
            if not system_prompt:
                msg = 'AI 提示词文件不存在或读取失败'
                yield _sse_event('error', {'message': msg})
                yield _sse_event('done', {'success': False, 'message': msg})
                return

            if not base_url or not api_key or not model:
                msg = '缺少 AI 配置（base_url/api_key/model）'
                yield _sse_event('error', {'message': msg})
                yield _sse_event('done', {'success': False, 'message': msg})
                return

            chat_url = _build_ai_url(base_url, '/chat/completions')
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }
            payload = {
                'model': model,
                'stream': True,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt},
                ],
            }

            log_info(
                0,
                "AI 流式请求开始",
                "WORKFLOW_AI_STREAM_REQUEST_START",
                base_url=base_url,
                request_url=chat_url,
                model=model,
                mode='chat_stream'
            )

            parts: list[str] = []
            with requests.post(chat_url, headers=headers, json=payload, timeout=(10, 300), stream=True) as response:
                if response.status_code >= 400:
                    err_text = response.text[:300]
                    msg = f'AI 接口调用失败: HTTP {response.status_code} {err_text}'
                    log_error(
                        0,
                        "AI 流式接口返回非成功状态码",
                        "WORKFLOW_AI_STREAM_HTTP_ERROR",
                        request_url=chat_url,
                        status_code=response.status_code,
                        response_body=response.text[:1200],
                        model=model
                    )
                    yield _sse_event('error', {'message': msg})
                    yield _sse_event('done', {'success': False, 'message': msg})
                    return

                content_type = (response.headers.get('Content-Type') or '').lower()
                if 'text/event-stream' in content_type:
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        line = raw_line.strip()
                        if not line.startswith('data:'):
                            continue
                        data_str = line[5:].strip()
                        if data_str == '[DONE]':
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue
                        text = _extract_chat_delta_text(chunk)
                        if text:
                            parts.append(text)
                            yield _sse_event('delta', {'text': text})
                else:
                    # 某些兼容接口即使传 stream=true 仍返回普通 JSON，这里做兜底兼容
                    try:
                        data_json = response.json()
                        full_text = _extract_chat_message_content(data_json)
                    except Exception:
                        full_text = response.text
                    if full_text:
                        parts.append(full_text)
                        yield _sse_event('delta', {'text': full_text})

            ai_result = ''.join(parts).strip()
            if not ai_result:
                msg = 'AI 返回内容为空'
                yield _sse_event('done', {'success': False, 'message': msg, 'raw_output': ''})
                return

            json_text = _extract_json_block(ai_result)
            try:
                workflow_config = json.loads(json_text)
            except json.JSONDecodeError as e:
                yield _sse_event('done', {
                    'success': False,
                    'message': f'AI 返回不是有效 JSON: {e}',
                    'raw_output': ai_result
                })
                return

            valid, err, normalized = _validate_workflow_ai_config(workflow_config)
            if not valid:
                yield _sse_event('done', {
                    'success': False,
                    'message': f'结构校验未通过: {err}',
                    'workflow': workflow_config,
                    'raw_output': ai_result
                })
                return

            yield _sse_event('done', {
                'success': True,
                'message': '生成成功，结构校验通过',
                'workflow': normalized,
                'raw_output': ai_result
            })
        except requests.RequestException as e:
            msg = f'AI 接口请求失败: {e}'
            log_error(0, "AI 流式接口请求异常", "WORKFLOW_AI_STREAM_REQUEST_EXCEPTION", error=str(e))
            yield _sse_event('error', {'message': msg})
            yield _sse_event('done', {'success': False, 'message': msg})
        except Exception as e:
            msg = f'AI 流式生成失败: {e}'
            log_error(0, "AI 流式生成异常", "WORKFLOW_AI_STREAM_ERROR", error=str(e))
            yield _sse_event('error', {'message': msg})
            yield _sse_event('done', {'success': False, 'message': msg})

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


def workflow_ai_create():
    """将 AI 校验通过的工作流写入数据库。"""
    try:
        data = request.get_json(silent=True) or {}
        workflow_config = data.get('workflow')
        if workflow_config is None:
            return jsonify({'success': False, 'message': '缺少 workflow 数据'})

        valid, err, normalized = _validate_workflow_ai_config(workflow_config)
        if not valid:
            return jsonify({'success': False, 'message': f'结构校验未通过: {err}'})

        original_name = normalized['name']
        name = original_name
        suffix = 1
        while Workflow.query.filter_by(name=name).first():
            name = f"{original_name}_AI{suffix}"
            suffix += 1
        normalized['name'] = name

        creator_id = g.user.id if hasattr(g, 'user') else None
        created = Workflow.create_from_config(
            name=name,
            description=normalized.get('description', ''),
            config=normalized,
            creator_id=creator_id,
            enabled=False,
            priority=100
        )
        _clear_workflow_cache(created.id)

        return jsonify({
            'success': True,
            'message': '工作流创建成功',
            'workflow_id': created.id,
            'name': name,
            'renamed': name != original_name,
            'edit_url': url_for('Admin.workflow_edit', workflow_id=created.id)
        })

    except Exception as e:
        log_error(0, f"AI 工作流创建失败: {e}", "WORKFLOW_AI_CREATE_ERROR", error=str(e))
        db.session.rollback()
        return jsonify({'success': False, 'message': f'创建失败: {e}'})


def workflow_create():
    """创建工作流"""
    from Models import Bot
    
    if request.method == 'GET':
        # 显示创建表单，传递机器人列表用于定时触发配置
        bots = Bot.query.filter_by(is_active=True).all()
        return render_template('admin/workflow/create.html', bots=bots, protocol_options=list_protocols())

    # POST: 处理创建
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        enabled = request.form.get('enabled', 'false') == 'true'
        priority = int(request.form.get('priority', 100))
        trigger_type = request.form.get('trigger_type', 'message')
        
        # 解析协议限制
        protocols_str = request.form.get('protocols', '[]')
        try:
            protocols = json.loads(protocols_str)
        except json.JSONDecodeError:
            protocols = []

        # 验证必填字段
        if not name:
            return jsonify({'success': False, 'message': '工作流名称不能为空'})

        # 检查名称是否已存在
        existing = Workflow.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'message': f'工作流名称"{name}"已存在'})

        # 创建默认工作流配置（包含start和end节点）
        default_config = {
            'name': name,
            'description': description,
            'protocols': protocols,
            'allow_continue': True,  # 默认允许继续执行后续工作流
            'trigger_type': trigger_type,
            'workflow': [
                {
                    'id': 'start',
                    'type': 'start',
                    'config': {}
                },
                {
                    'id': 'end',
                    'type': 'end',
                    'config': {
                        'allow_continue': True  # 默认允许继续执行
                    }
                }
            ]
        }
        
        # 如果是定时触发，添加调度配置
        if trigger_type == 'schedule':
            schedule_type = request.form.get('schedule_type', 'cron')
            default_config['schedule'] = {
                'type': schedule_type
            }
            if schedule_type == 'cron':
                default_config['schedule']['cron'] = request.form.get('schedule_cron', '0 8 * * *')
            else:
                default_config['schedule']['interval_minutes'] = int(request.form.get('schedule_interval', 60))

        # 创建工作流
        creator_id = g.user.id if hasattr(g, 'user') else None
        workflow = Workflow.create_from_config(
            name=name,
            description=description,
            config=default_config,
            creator_id=creator_id,
            enabled=enabled,
            priority=priority
        )

        log_info(0, f"创建工作流: {name}", "WORKFLOW_CREATE",
                 workflow_id=workflow.id, creator_id=creator_id, trigger_type=trigger_type)

        _clear_workflow_cache(workflow.id)

        flash(f'工作流 {name} 创建成功', 'success')
        return redirect(url_for('Admin.workflow_edit', workflow_id=workflow.id))

    except Exception as e:
        log_error(0, f"创建工作流失败: {e}", "WORKFLOW_CREATE_ERROR", error=str(e))
        flash(f'创建失败: {str(e)}', 'danger')
        return redirect(url_for('Admin.workflow_create'))


def workflow_edit(workflow_id):
    """编辑工作流"""
    workflow = Workflow.query.get_or_404(workflow_id)

    if request.method == 'GET':
        # 显示编辑表单
        available_nodes = _get_available_nodes()
        config = workflow.get_config()

        return render_template('admin/workflow/edit.html',
                               workflow=workflow,
                               config=config,
                               available_nodes=available_nodes)

    # POST: 处理更新（仅更新工作流节点）
    try:
        # 获取工作流节点配置（JSON）
        workflow_data = request.form.get('workflow_data', '{}')
        try:
            workflow_config = json.loads(workflow_data)
        except json.JSONDecodeError:
            return jsonify({'success': False, 'message': '工作流配置格式错误'})

        # 从 End节点配置中提取allow_continue标志
        allow_continue = True  # 默认值
        workflow_nodes = workflow_config.get('workflow', [])
        for node in workflow_nodes:
            if node.get('type') == 'end':
                allow_continue = node.get('config', {}).get('allow_continue', True)
                break

        config = workflow.get_config()
        config['allow_continue'] = allow_continue
        config['workflow'] = workflow_nodes

        workflow.update_config(config)

        log_info(0, f"更新工作流节点: {workflow.name}", "WORKFLOW_UPDATE_NODES", 
                 workflow_id=workflow_id)

        _clear_workflow_cache(workflow_id)

        flash('工作流节点更新成功', 'success')
        return redirect(url_for('Admin.workflow_detail', workflow_id=workflow_id))

    except Exception as e:
        log_error(0, f"更新工作流失败: {e}", "WORKFLOW_UPDATE_ERROR",
                  workflow_id=workflow_id, error=str(e))
        flash(f'更新失败: {str(e)}', 'danger')
        return redirect(url_for('Admin.workflow_edit', workflow_id=workflow_id))


def workflow_delete(workflow_id):
    """删除工作流"""
    try:
        workflow = Workflow.query.get_or_404(workflow_id)
        workflow_name = workflow.name

        db.session.delete(workflow)
        db.session.commit()

        log_info(0, f"删除工作流: {workflow_name}", "WORKFLOW_DELETE", workflow_id=workflow_id)

        _clear_workflow_cache(workflow_id, remove=True)

        flash(f'工作流 {workflow_name} 删除成功', 'success')

    except Exception as e:
        log_error(0, f"删除工作流失败: {e}", "WORKFLOW_DELETE_ERROR",
                  workflow_id=workflow_id, error=str(e))
        db.session.rollback()
        flash(f'删除工作流失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.workflow_list'))


def workflow_toggle(workflow_id):
    """切换工作流启用状态"""
    try:
        workflow = Workflow.query.get_or_404(workflow_id)
        workflow.toggle_enabled()

        status = '启用' if workflow.enabled else '禁用'
        log_info(0, f"{status}工作流: {workflow.name}", "WORKFLOW_TOGGLE",
                 workflow_id=workflow_id, enabled=workflow.enabled)

        _clear_workflow_cache(workflow_id)

        flash(f'工作流 {workflow.name} 已{status}', 'success')

    except Exception as e:
        log_error(0, f"切换工作流状态失败: {e}", "WORKFLOW_TOGGLE_ERROR",
                  workflow_id=workflow_id, error=str(e))
        flash(f'操作失败: {str(e)}', 'danger')

    return redirect(url_for('Admin.workflow_list'))


def workflow_detail(workflow_id):
    """工作流详情页面"""
    try:
        workflow = Workflow.query.get_or_404(workflow_id)
        config = workflow.get_config()

        protocol_options = list_protocols()
        protocol_name_map = {item['id']: item['name'] for item in protocol_options}

        return render_template('admin/workflow/detail.html',
                               workflow=workflow,
                               config=config,
                               protocol_options=protocol_options,
                               protocol_name_map=protocol_name_map)

    except Exception as e:
        log_error(0, f"获取工作流详情失败: {e}", "WORKFLOW_DETAIL_ERROR",
                  workflow_id=workflow_id, error=str(e))
        flash('获取工作流详情失败', 'error')
        return redirect(url_for('Admin.workflow_list'))


def workflow_update_basic(workflow_id):
    """更新工作流基本信息（名称、描述、优先级、定时配置）"""
    try:
        workflow = Workflow.query.get_or_404(workflow_id)
        data = json.loads(request.form.get('data', '{}'))
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        priority = int(data.get('priority', 100))
        
        # 验证名称
        if not name:
            flash('工作流名称不能为空', 'warning')
            return redirect(url_for('Admin.workflow_detail', workflow_id=workflow_id))
        
        # 检查名称是否与其他工作流冲突
        existing = Workflow.query.filter(
            Workflow.name == name,
            Workflow.id != workflow_id
        ).first()
        if existing:
            flash(f'工作流名称"{name}"已被使用', 'warning')
            return redirect(url_for('Admin.workflow_detail', workflow_id=workflow_id))
        
        # 更新基本字段
        workflow.name = name
        workflow.description = description
        workflow.priority = priority
        
        # 更新 config 中的名称和描述
        config = workflow.get_config()
        config['name'] = name
        config['description'] = description
        
        # 更新协议限制
        protocols = data.get('protocols', [])
        config['protocols'] = protocols
        
        # 处理定时配置（仅定时触发类型）
        if config.get('trigger_type') == 'schedule':
            schedule_type = data.get('schedule_type', 'cron')
            config['schedule'] = {'type': schedule_type}
            
            if schedule_type == 'cron':
                config['schedule']['cron'] = data.get('schedule_cron', '0 8 * * *')
            else:
                config['schedule']['interval_minutes'] = int(data.get('schedule_interval', 60))
        
        workflow.update_config(config)
        
        log_info(0, f"更新工作流基本信息: {name}", "WORKFLOW_UPDATE_BASIC",
                 workflow_id=workflow_id)
        
        _clear_workflow_cache(workflow_id)
        
        flash('基本信息保存成功', 'success')
        return redirect(url_for('Admin.workflow_detail', workflow_id=workflow_id))
        
    except Exception as e:
        log_error(0, f"更新工作流基本信息失败: {e}", "WORKFLOW_UPDATE_BASIC_ERROR",
                  workflow_id=workflow_id, error=str(e))
        flash(f'保存失败: {str(e)}', 'danger')
        return redirect(url_for('Admin.workflow_detail', workflow_id=workflow_id))


def _parse_snippet_metadata(snippet_code: str) -> dict:
    """解析代码片段的元数据
    
    Args:
        snippet_code: Python代码片段
        
    Returns:
        dict: 包含name, description, author等元数据
    """
    metadata = {
        'name': '未命名片段',
        'description': '',
        'author': '',
        'version': '1.0.0'
    }

    # 简单的元数据解析（从注释中提取）
    lines = snippet_code.split('\n')
    for line in lines[:10]:  # 只检查前10行
        line = line.strip()
        if line.startswith('#'):
            if 'name:' in line.lower():
                metadata['name'] = line.split(':', 1)[1].strip()
            elif 'desc' in line.lower():
                metadata['description'] = line.split(':', 1)[1].strip()
            elif 'author:' in line.lower():
                metadata['author'] = line.split(':', 1)[1].strip()

    return metadata


def workflow_reload_cache():
    """手动重载工作流缓存"""
    try:
        from Core.workflow.cache import workflow_cache
        from Core.scheduler import scheduler_service

        count = workflow_cache.reload()
        scheduled_count = 0
        if scheduler_service.is_running():
            scheduled_count = scheduler_service.sync_scheduled_workflows_from_cache(
                workflow_cache.get_all_workflows()
            )

        log_info(0, f"手动重载工作流缓存", "WORKFLOW_CACHE_MANUAL_RELOAD",
                 count=count, scheduled_count=scheduled_count)

        # 获取缓存统计信息
        stats = workflow_cache.get_stats()

        return jsonify({
            'success': True,
            'message': f'缓存已重载，共 {count} 个工作流，{scheduled_count} 个定时任务已同步',
            'stats': stats
        })

    except Exception as e:
        log_error(0, f"重载工作流缓存失败: {e}", "WORKFLOW_CACHE_RELOAD_ERROR", error=str(e))
        return jsonify({
            'success': False,
            'message': f'重载失败: {str(e)}'
        })


def _validate_zip_path(entry_name: str, base_dir: str, allowed_subdirs: list[str]) -> tuple[bool, str]:
    """验证 ZIP 条目路径是否安全，防止 ZipSlip 攻击
    
    Args:
        entry_name: ZIP 条目名称
        base_dir: 基础目录
        allowed_subdirs: 允许的子目录列表，如 ['Snippets', 'Render']
        
    Returns:
        tuple[bool, str]: (是否安全, 安全的绝对路径或错误信息)
    """
    import os.path
    
    norm_base = os.path.normpath(os.path.abspath(base_dir))
    
    parts = entry_name.replace('\\', '/').split('/')
    
    if len(parts) < 2:
        return False, "无效的路径格式"
    
    subdir = parts[0]
    if subdir not in allowed_subdirs:
        return False, f"不允许的目录: {subdir}"
    
    for part in parts:
        if part in ('', '.', '..'):
            return False, "路径包含非法组件"
        if ':' in part or part.startswith('\\'):
            return False, "路径包含非法字符"
    
    safe_relative = '/'.join(parts)
    target_path = os.path.normpath(os.path.join(norm_base, safe_relative))
    
    if not target_path.startswith(norm_base + os.sep) and target_path != norm_base:
        return False, "路径越界"
    
    expected_dir = os.path.join(norm_base, subdir)
    if not target_path.startswith(expected_dir + os.sep) and target_path != expected_dir:
        return False, f"路径不在允许的目录 {subdir} 内"
    
    return True, target_path


def workflow_import():
    """导入工作流（支持 ZIP 格式，包含代码片段和渲染模板）"""
    import zipfile
    import io

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未选择文件'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'})

    if not file.filename.endswith('.workflow'):
        return jsonify({'success': False, 'message': '文件格式不正确，请选择 .workflow 文件'})

    try:
        file_content = file.read()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        try:
            zip_buffer = io.BytesIO(file_content)
            zf = zipfile.ZipFile(zip_buffer, 'r')
        except zipfile.BadZipFile:
            return jsonify({'success': False, 'message': '文件格式错误，不是有效的 ZIP 文件'})

        with zf:
            if 'workflow.json' not in zf.namelist():
                return jsonify({'success': False, 'message': '文件缺少 workflow.json'})

            data = json.loads(zf.read('workflow.json').decode('utf-8'))

            copied_files = []
            blocked_files = []
            allowed_subdirs = ['Snippets', 'Render']
            
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                
                if name == 'workflow.json':
                    continue
                    
                if not (name.startswith('Snippets/') or name.startswith('Render/')):
                    continue
                    
                is_safe, result = _validate_zip_path(name, base_dir, allowed_subdirs)
                
                if not is_safe:
                    blocked_files.append(name)
                    log_error(0, f"阻止可疑的 ZIP 条目: {name}", "ZIPSIP_BLOCKED", reason=result)
                    continue
                
                target_path = result
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                content = zf.read(name)
                if not os.path.exists(target_path):
                    with open(target_path, 'wb') as f:
                        f.write(content)
                    copied_files.append(name)
        
        # 安全策略：检测到可疑文件则中止导入，并回滚本次写入的文件
        if blocked_files:
            for copied_name in copied_files:
                copied_path = os.path.join(base_dir, copied_name)
                try:
                    if os.path.exists(copied_path):
                        os.remove(copied_path)
                except Exception as cleanup_error:
                    log_error(0, f"回滚导入文件失败: {copied_name}",
                              "WORKFLOW_IMPORT_ROLLBACK_ERROR", error=str(cleanup_error))

            return jsonify({
                'success': False,
                'message': '导入失败：检测到可疑文件，已中止导入',
                'blocked_files': blocked_files
            })

        # 校验格式
        if 'workflow' not in data:
            return jsonify({'success': False, 'message': '文件格式错误，缺少 workflow 字段'})

        workflow_data = data['workflow']
        name = workflow_data.get('name', '')
        if not name:
            return jsonify({'success': False, 'message': '工作流名称不能为空'})

        config = workflow_data.get('config', {})
        if not config.get('workflow'):
            return jsonify({'success': False, 'message': '工作流配置不完整'})

        # 检查名称是否已存在
        original_name = name
        counter = 1
        while Workflow.query.filter_by(name=name).first():
            name = f"{original_name}_导入{counter}"
            counter += 1

        # 创建工作流
        creator_id = g.user.id if hasattr(g, 'user') else None
        workflow = Workflow.create_from_config(
            name=name,
            description=config.get('description', ''),
            config=config,
            creator_id=creator_id,
            enabled=False,
            priority=workflow_data.get('priority', 100)
        )

        log_info(0, f"导入工作流: {name}", "WORKFLOW_IMPORT",
                 workflow_id=workflow.id, original_name=original_name, 
                 copied_files=copied_files, blocked_files=blocked_files)

        _clear_workflow_cache(workflow.id)

        renamed = name != original_name
        message = '工作流导入成功'
        if renamed:
            message += f'（已重命名为"{name}"）'
        if copied_files:
            message += f'，已复制 {len(copied_files)} 个文件'

        return jsonify({
            'success': True,
            'message': message,
            'workflow_id': workflow.id,
            'name': name,
            'renamed': renamed,
            'copied_files': copied_files
        })

    except json.JSONDecodeError:
        return jsonify({'success': False, 'message': '文件内容解析失败'})
    except Exception as e:
        log_error(0, f"导入工作流失败: {e}", "WORKFLOW_IMPORT_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'导入失败: {str(e)}'})


def workflow_export(workflow_id):
    """导出单个工作流（ZIP 格式，包含代码片段和渲染模板）"""
    from flask import Response
    from datetime import datetime
    from urllib.parse import quote
    import zipfile
    import io

    try:
        workflow = Workflow.query.get_or_404(workflow_id)
        config = workflow.get_config()
        workflow_steps = config.get('workflow', [])

        # 收集引用的文件
        snippets = set()
        templates = set()
        for step in workflow_steps:
            step_config = step.get('config', {})
            if step.get('type') == 'python_snippet' and step_config.get('snippet_name'):
                snippets.add(step_config['snippet_name'])
            if step.get('type') == 'html_render' and step_config.get('template_path'):
                templates.add(step_config['template_path'])

        # 构建导出数据
        export_data = {
            'version': '2.0',
            'export_time': datetime.now().isoformat(),
            'workflow': {
                'name': workflow.name,
                'priority': workflow.priority,
                'enabled': workflow.enabled,
                'config': config
            },
            'files': {
                'snippets': list(snippets),
                'templates': list(templates)
            }
        }

        # 创建 ZIP 文件
        zip_buffer = io.BytesIO()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 写入工作流配置
            zf.writestr('workflow.json', json.dumps(export_data, ensure_ascii=False, indent=2))

            # 写入代码片段
            for snippet in snippets:
                snippet_path = os.path.join(base_dir, 'Snippets', snippet)
                if os.path.exists(snippet_path):
                    zf.write(snippet_path, f'Snippets/{snippet}')

            # 写入渲染模板
            for template in templates:
                template_path = os.path.join(base_dir, 'Render', template)
                if os.path.exists(template_path):
                    zf.write(template_path, f'Render/{template}')

        zip_buffer.seek(0)

        # 生成文件名
        safe_name = workflow.name.replace(' ', '_').replace('/', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_name}_{timestamp}.workflow"
        encoded_filename = quote(filename)

        response = Response(
            zip_buffer.getvalue(),
            mimetype='application/zip',
            headers={
                'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )

        log_info(0, f"导出工作流: {workflow.name}", "WORKFLOW_EXPORT",
                 workflow_id=workflow_id, snippets=list(snippets), templates=list(templates))

        return response

    except Exception as e:
        log_error(0, f"导出工作流失败: {e}", "WORKFLOW_EXPORT_ERROR", workflow_id=workflow_id, error=str(e))
        return jsonify({'success': False, 'message': f'导出失败: {str(e)}'}), 500


def snippets_list():
    """代码片段列表"""
    import os

    try:
        snippets_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'Snippets')
        snippets = []

        # 检查目录是否存在
        if not os.path.exists(snippets_dir):
            return jsonify({
                'success': True,
                'snippets': []
            })

        # 遍历目录中的 .py 文件
        for filename in os.listdir(snippets_dir):
            if filename.endswith('.py') and not filename.startswith('_'):
                filepath = os.path.join(snippets_dir, filename)

                # 读取文件内容
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        code = f.read()

                    # 解析元数据
                    metadata = _parse_snippet_metadata(code)

                    snippets.append({
                        'filename': filename,
                        'name': metadata.get('name', filename.replace('.py', '')),
                        'description': metadata.get('description', ''),
                        'author': metadata.get('author', ''),
                        'version': metadata.get('version', '1.0.0')
                    })
                except Exception as e:
                    log_error(0, f"读取代码片段失败: {filename}", "SNIPPET_READ_ERROR", error=str(e))
                    continue

        return jsonify({
            'success': True,
            'snippets': snippets
        })

    except Exception as e:
        log_error(0, f"获取代码片段列表失败: {e}", "SNIPPETS_LIST_ERROR", error=str(e))
        return jsonify({
            'success': False,
            'message': f'获取代码片段失败: {str(e)}',
            'snippets': []
        })


def workflow_debug_record(workflow_id):
    """获取指定工作流的调试记录"""
    try:
        from Core.workflow.debug import get_debug_record
        
        record = get_debug_record(workflow_id)
        
        if record:
            return jsonify({
                'success': True,
                'record': record
            })
        else:
            return jsonify({
                'success': True,
                'record': None,
                'message': '暂无调试记录'
            })
            
    except Exception as e:
        log_error(0, f"获取工作流调试记录失败: {e}", "WORKFLOW_DEBUG_GET_ERROR",
                  workflow_id=workflow_id, error=str(e))
        return jsonify({
            'success': False,
            'message': f'获取调试记录失败: {str(e)}'
        })


def workflow_debug_clear(workflow_id):
    """清除指定工作流的调试记录"""
    try:
        from Core.workflow.debug import clear_debug_record
        
        clear_debug_record(workflow_id)
        
        return jsonify({
            'success': True,
            'message': '调试记录已清除'
        })
            
    except Exception as e:
        log_error(0, f"清除工作流调试记录失败: {e}", "WORKFLOW_DEBUG_CLEAR_ERROR",
                  workflow_id=workflow_id, error=str(e))
        return jsonify({
            'success': False,
            'message': f'清除调试记录失败: {str(e)}'
        })
