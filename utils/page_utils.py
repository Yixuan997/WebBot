"""
@Project：Yapi 
@File   ：page_utils.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/5/12 18:48 
"""


def generate_pagination(current_page, total_pages, neighbors=2):
    """
    生成智能分页列表

    参数:
        current_page: 当前页码
        total_pages: 总页数
        neighbors: 当前页左右各显示几个相邻页码

    返回:
        包含要显示的页码和分隔符的列表
    """
    # 如果总页数少于等于10页，显示所有页码
    if total_pages <= 10:
        return list(range(1, total_pages + 1))

    # 初始化结果列表，始终包含第一页
    pagination = [1]

    # 确定显示的页码范围
    start_page = max(2, current_page - neighbors)
    end_page = min(total_pages - 1, current_page + neighbors)

    # 处理第一页与起始页之间的间隔
    if start_page > 2:
        pagination.append('...')

    # 添加中间页码范围
    pagination.extend(range(start_page, end_page + 1))

    # 处理结束页与最后页之间的间隔
    if end_page < total_pages - 1:
        pagination.append('...')

    # 添加最后一页（如果不是已经添加）
    if total_pages > 1:  # 确保有最后一页
        pagination.append(total_pages)

    return pagination


def adapt_pagination(pagination, neighbors=2):
    """
    将SQLAlchemy的分页对象适配为我们的智能分页格式

    参数:
        pagination: SQLAlchemy的分页对象
        neighbors: 当前页左右各显示几个相邻页码

    返回:
        包含要显示的页码和分隔符的列表
    """
    # 从SQLAlchemy分页对象中获取必要的信息
    current_page = pagination.page
    total_pages = pagination.pages

    # 使用我们的智能分页生成器
    return generate_pagination(current_page, total_pages, neighbors)
