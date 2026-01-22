"""
@Project：WebBot 
@File   ：http_json.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 10:24 
"""
from flask import jsonify

from Models.Extensions import time_format


def success_api(msg: str = "获取成功！"):
    # 成功响应 默认值 '成功'
    res = {
        'code': 200,
        'msg': msg,
        'time': time_format(None),
    }
    return jsonify(res)


def fail_api(msg: str = "获取失败，请联系管理员！"):
    # 失败 默认值 '失败'
    res = {
        'code': 500,
        'msg': msg,
        'time': time_format(None),
    }
    return jsonify(res)


def table_api(msg: str = "请求成功！", data=None, **kwargs):
    # 动态表格渲染响应
    res = {
        'code': 200,
        'msg': msg,
        'time': time_format(None),
    }

    # 处理data参数
    if data is not None:
        res['data'] = data

    # 将kwargs中的所有字段添加到响应中
    for key, value in kwargs.items():
        res[key] = value

    return jsonify(res)
