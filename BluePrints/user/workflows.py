"""
@Project：WebBot 
@File   ：workflows.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2026/1/2

用户工作流订阅管理
"""

from flask import render_template, flash, redirect, url_for, session, request

from Models import User, System, Workflow, UserWorkflow, db
from utils.page_utils import adapt_pagination


def user_workflows():
    """用户工作流订阅管理"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    try:
        # 获取分页参数
        page = request.args.get('page', 1, type=int)
        per_page = 10  # 每页显示10条
        search = request.args.get('search', '')
        
        # 构建查询
        query = Workflow.query.filter_by(enabled=True)
        
        # 搜索功能
        if search:
            query = query.filter(Workflow.name.contains(search))
        
        # 按ID倒序（最新创建的在前）
        query = query.order_by(Workflow.id.desc())
        
        # 分页
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        workflows = pagination.items

        # 为每个工作流添加用户的订阅状态
        for workflow in workflows:
            subscription = UserWorkflow.query.filter_by(
                user_id=user_id,
                workflow_id=workflow.id
            ).first()

            # 如果有订阅记录，使用记录的状态；否则默认为未订阅
            workflow.user_subscribed = subscription.enabled if subscription else False
        
        # 使用智能分页
        page_numbers = adapt_pagination(pagination)

        system = System.query.first()
        return render_template('user/workflows/list.html',
                               user=user,
                               workflows=workflows,
                               pagination=pagination,
                               page_numbers=page_numbers,
                               current_page=page,
                               search=search,
                               system=system)

    except Exception as e:
        flash(f'获取工作流列表失败: {str(e)}', 'danger')
        return render_template('user/workflows/list.html',
                               user=user,
                               workflows=[],
                               pagination=None,
                               current_page=1,
                               search='',
                               system=System.query.first())


def toggle_workflow_subscription(workflow_id):
    """切换工作流订阅状态"""
    user_id = session.get('user_id')
    user = User.query.get(user_id)

    if not user:
        return redirect(url_for('auth.login'))

    try:
        # 验证工作流是否存在且全局启用
        workflow = Workflow.query.filter_by(id=workflow_id, enabled=True).first()
        if not workflow:
            flash('工作流不存在或已被禁用', 'danger')
            return redirect(url_for('user.workflows'))

        # 查询或创建订阅记录
        subscription = UserWorkflow.query.filter_by(
            user_id=user_id,
            workflow_id=workflow_id
        ).first()

        if subscription:
            # 已有订阅记录，切换状态
            subscription.enabled = not subscription.enabled
            message = f'工作流「{workflow.name}」已{"启用" if subscription.enabled else "禁用"}'
        else:
            # 首次订阅，创建记录
            subscription = UserWorkflow(
                user_id=user_id,
                workflow_id=workflow_id,
                enabled=True
            )
            db.session.add(subscription)
            message = f'工作流「{workflow.name}」已启用'

        db.session.commit()
        flash(message, 'success')
        return redirect(url_for('user.workflows'))

    except Exception as e:
        db.session.rollback()
        flash(f'操作失败：{str(e)}', 'danger')
        return redirect(url_for('user.workflows'))
