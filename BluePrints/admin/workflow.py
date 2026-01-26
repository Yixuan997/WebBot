"""
@Project：WebBot
@File   ：workflow.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/12/21
"""

import json
import os

from flask import render_template, request, flash, redirect, url_for, jsonify, g

from Core.logging.file_logger import log_info, log_error
from Core.workflow.registry import NodeRegistry
from Models import db
from Models.SQL.Workflow import Workflow
from utils.page_utils import adapt_pagination


def _clear_workflow_cache():
    """清除并重载工作流缓存"""
    try:
        from Core.workflow.cache import workflow_cache
        from flask import current_app
        workflow_cache.reload()
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

        return render_template('admin/workflow/list.html',
                               workflows=workflows,
                               pagination=pagination,
                               page_numbers=page_numbers,
                               search=search,
                               current_page=page)

    except Exception as e:
        log_error(0, f"获取工作流列表失败: {e}", "WORKFLOW_LIST_ERROR", error=str(e))
        flash('获取工作流列表失败', 'error')
        return render_template('admin/workflow/list.html', workflows=[], pagination=None)


def workflow_create():
    """创建工作流"""
    from Models import Bot
    
    if request.method == 'GET':
        # 显示创建表单，传递机器人列表用于定时触发配置
        bots = Bot.query.filter_by(is_active=True).all()
        return render_template('admin/workflow/create.html', bots=bots)

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

        _clear_workflow_cache()

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
        config['protocols'] = workflow_config.get('protocols', config.get('protocols', []))

        workflow.update_config(config)

        log_info(0, f"更新工作流节点: {workflow.name}", "WORKFLOW_UPDATE_NODES", 
                 workflow_id=workflow_id)

        _clear_workflow_cache()

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

        _clear_workflow_cache()

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

        _clear_workflow_cache()

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

        return render_template('admin/workflow/detail.html',
                               workflow=workflow,
                               config=config)

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
        
        _clear_workflow_cache()
        
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
        from flask import current_app

        count = workflow_cache.reload()

        log_info(0, f"手动重载工作流缓存", "WORKFLOW_CACHE_MANUAL_RELOAD", count=count)

        # 获取缓存统计信息
        stats = workflow_cache.get_stats()

        return jsonify({
            'success': True,
            'message': f'缓存已重载，共 {count} 个工作流',
            'stats': stats
        })

    except Exception as e:
        log_error(0, f"重载工作流缓存失败: {e}", "WORKFLOW_CACHE_RELOAD_ERROR", error=str(e))
        return jsonify({
            'success': False,
            'message': f'重载失败: {str(e)}'
        })


def workflow_import():
    """导入工作流（支持 ZIP 格式，包含代码片段和渲染模板）"""
    import zipfile
    import io

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未选择文件'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'})

    # 检查文件后缀
    if not file.filename.endswith('.workflow'):
        return jsonify({'success': False, 'message': '文件格式不正确，请选择 .workflow 文件'})

    try:
        file_content = file.read()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

        # 解压 ZIP
        try:
            zip_buffer = io.BytesIO(file_content)
            zf = zipfile.ZipFile(zip_buffer, 'r')
        except zipfile.BadZipFile:
            return jsonify({'success': False, 'message': '文件格式错误，不是有效的 ZIP 文件'})

        with zf:
            # 读取工作流配置
            if 'workflow.json' not in zf.namelist():
                return jsonify({'success': False, 'message': '文件缺少 workflow.json'})

            data = json.loads(zf.read('workflow.json').decode('utf-8'))

            # 提取代码片段和模板文件
            copied_files = []
            for name in zf.namelist():
                if name.startswith('Snippets/') and name != 'Snippets/':
                    target_path = os.path.join(base_dir, name)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    content = zf.read(name)
                    if not os.path.exists(target_path):
                        with open(target_path, 'wb') as f:
                            f.write(content)
                        copied_files.append(name)
                elif name.startswith('Render/') and name != 'Render/':
                    target_path = os.path.join(base_dir, name)
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    content = zf.read(name)
                    if not os.path.exists(target_path):
                        with open(target_path, 'wb') as f:
                            f.write(content)
                        copied_files.append(name)

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
                 workflow_id=workflow.id, original_name=original_name, copied_files=copied_files)

        _clear_workflow_cache()

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
