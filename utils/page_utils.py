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
    # 边界检查
    if total_pages <= 0:
        return []
    
    if current_page < 1:
        current_page = 1
    elif current_page > total_pages:
        current_page = total_pages
    
    # 如果总页数少于等于10页，显示所有页码
    if total_pages <= 10:
        return list(range(1, total_pages + 1))

    # 初始化结果列表
    pagination = []
    
    # 始终包含第一页
    pagination.append(1)
    
    # 计算中间部分的起止页码
    start_page = max(2, current_page - neighbors)
    end_page = min(total_pages - 1, current_page + neighbors)
    
    # 特殊处理：当前页接近首页时，多显示一些后续页
    if current_page <= neighbors + 1:
        end_page = min(total_pages - 1, 2 * neighbors + 2)
    
    # 特殊处理：当前页接近尾页时，多显示一些前置页
    if current_page >= total_pages - neighbors:
        start_page = max(2, total_pages - 2 * neighbors - 1)
    
    # 添加首页后的省略号
    if start_page > 2:
        pagination.append('...')
    
    # 添加中间页码
    for page in range(start_page, end_page + 1):
        pagination.append(page)
    
    # 添加尾页前的省略号
    if end_page < total_pages - 1:
        pagination.append('...')
    
    # 始终包含最后一页（如果总页数大于1）
    if total_pages > 1:
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
