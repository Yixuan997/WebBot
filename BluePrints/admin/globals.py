"""
全局变量管理
"""
from flask import render_template, request, jsonify

from Core.logging.file_logger import log_info, log_error
from Core.workflow.globals import global_variables
from Models import GlobalVariable


def globals_list():
    """全局变量列表页面"""
    try:
        variables = GlobalVariable.get_all()
        return render_template('admin/globals.html', variables=variables)
    except Exception as e:
        log_error(0, f"获取全局变量列表失败: {e}", "GLOBALS_LIST_ERROR", error=str(e))
        return render_template('admin/globals.html', variables=[])


def globals_create():
    """创建全局变量"""
    try:
        data = request.get_json()
        key = data.get('key', '').strip()
        value = data.get('value', '')
        description = data.get('description', '').strip()
        is_secret = data.get('is_secret', False)

        if not key:
            return jsonify({'success': False, 'message': '变量名不能为空'})

        # 检查是否已存在
        if GlobalVariable.get_by_key(key):
            return jsonify({'success': False, 'message': f'变量 {key} 已存在'})

        # 创建变量
        global_variables.set(key, value, description, is_secret)

        log_info(0, f"创建全局变量: {key}", "GLOBALS_CREATE")
        return jsonify({'success': True, 'message': '创建成功'})

    except Exception as e:
        log_error(0, f"创建全局变量失败: {e}", "GLOBALS_CREATE_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'创建失败: {str(e)}'})


def globals_update(var_id):
    """更新全局变量"""
    try:
        var = GlobalVariable.query.get_or_404(var_id)
        data = request.get_json()

        key = data.get('key', '').strip()
        value = data.get('value', '')
        description = data.get('description', '').strip()
        is_secret = data.get('is_secret', False)

        if not key:
            return jsonify({'success': False, 'message': '变量名不能为空'})

        # 如果 key 改变，检查新 key 是否已存在
        if key != var.key and GlobalVariable.get_by_key(key):
            return jsonify({'success': False, 'message': f'变量 {key} 已存在'})

        # 如果 key 改变，需要删除旧的再创建新的
        if key != var.key:
            global_variables.delete(var.key)

        global_variables.set(key, value, description, is_secret)

        log_info(0, f"更新全局变量: {key}", "GLOBALS_UPDATE")
        return jsonify({'success': True, 'message': '更新成功'})

    except Exception as e:
        log_error(0, f"更新全局变量失败: {e}", "GLOBALS_UPDATE_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'})


def globals_delete(var_id):
    """删除全局变量"""
    try:
        var = GlobalVariable.query.get_or_404(var_id)
        key = var.key

        global_variables.delete(key)

        log_info(0, f"删除全局变量: {key}", "GLOBALS_DELETE")
        return jsonify({'success': True, 'message': '删除成功'})

    except Exception as e:
        log_error(0, f"删除全局变量失败: {e}", "GLOBALS_DELETE_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'})


def globals_get(var_id):
    """获取单个全局变量（用于编辑时获取完整值）"""
    try:
        var = GlobalVariable.query.get_or_404(var_id)
        return jsonify({
            'success': True,
            'variable': var.to_dict(hide_secret=False)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


def globals_reload():
    """重新加载全局变量缓存"""
    try:
        count = global_variables.reload()
        return jsonify({
            'success': True,
            'message': f'已重新加载 {count} 个全局变量'
        })
    except Exception as e:
        log_error(0, f"重载全局变量失败: {e}", "GLOBALS_RELOAD_ERROR", error=str(e))
        return jsonify({'success': False, 'message': f'重载失败: {str(e)}'})
