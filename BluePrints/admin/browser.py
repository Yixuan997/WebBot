"""
@Project：WebBot 
@File   ：browser.py
@IDE    ：PyCharm 
@Author ：系统
@Date   ：2025/7/25
@Desc   ：浏览器管理器控制接口
"""
from http_json import fail_api, success_api, table_api


def browser_status():
    """获取浏览器管理器状态（简化版）"""
    try:
        from Core.tools.browser import browser
        return table_api('请求成功', status=browser.get_status())
    except Exception as e:
        return fail_api(str(e))


def restart_browser():
    """重启浏览器管理器"""
    try:
        from Core.tools.browser import browser

        # 使用新的重启方法
        success = browser.restart()

        if success:
            return success_api('浏览器管理器重启成功')
        return fail_api('浏览器管理器重启失败')

    except Exception as e:
        return fail_api(str(e))


def start_browser():
    """启动浏览器管理器"""
    try:
        from Core.tools.browser import browser

        if browser.is_running:
            return fail_api('浏览器管理器已在运行')

        browser.start()

        if browser.is_running:
            return success_api('浏览器管理器启动成功')
        return fail_api('浏览器管理器启动失败')

    except Exception as e:
        return fail_api(str(e))


def stop_browser():
    """停止浏览器管理器"""
    try:
        from Core.tools.browser import browser

        if not browser.is_running:
            return fail_api('浏览器管理器未在运行')

        browser.stop()

        if not browser.is_running:
            return success_api('浏览器管理器停止成功')
        return fail_api('浏览器管理器停止失败')

    except Exception as e:
        return fail_api(str(e))
