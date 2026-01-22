"""
系统级浏览器管理器
高性能HTML转图片服务，集成Jinja2模板引擎
"""

import asyncio
import atexit
import base64
import threading
import time
from typing import Optional, Dict, Any

from jinja2 import Environment, FileSystemLoader


class BrowserManager:
    """系统级浏览器管理器"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        # 浏览器实例
        self.playwright = None
        self.browser = None
        self.context = None

        # 线程管理
        self.browser_thread = None
        self.browser_loop = None
        self.is_running = False

        # Jinja2 模板引擎 - 从 Render 目录加载
        template_dirs = ['Render']  # 从 Render 目录加载
        self.jinja_env = Environment(
            loader=FileSystemLoader(template_dirs),
            autoescape=True,
            cache_size=50
        )

        # 初始化标志
        self._initialized = True

        # 统计信息
        self._render_count = 0
        self._start_time = None

        # 注册退出清理
        atexit.register(self.cleanup_sync)

    def start(self):
        """启动浏览器管理器（异步，不阻塞）"""
        if self.is_running or self.browser_thread:
            return

        # 在独立线程中运行浏览器，不等待启动完成
        self.browser_thread = threading.Thread(
            target=self._run_browser_loop,
            name="browser-manager",
            daemon=True
        )
        self.browser_thread.start()
        # 不再阻塞等待，让浏览器在后台启动
        # 第一次调用 render() 时会自动等待浏览器就绪

    def _run_browser_loop(self):
        """在独立线程中运行浏览器事件循环"""
        try:
            self.browser_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.browser_loop)
            self.browser_loop.run_until_complete(self._init_browser())
            self.is_running = True
            self._start_time = time.time()
            self.browser_loop.run_forever()
        except:
            pass
        finally:
            self.is_running = False
            self.browser_loop = None

    async def _init_browser(self):
        """初始化浏览器实例"""
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-background-networking',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--disable-gpu',
                '--single-process'  # 单进程模式，更快启动
            ]
        )

        # 创建持久上下文
        self.context = await self.browser.new_context(
            viewport={'width': 500, 'height': 600},  # 默认视口
            device_scale_factor=2,  # 2倍缩放提高清晰度
            has_touch=False,
            is_mobile=False,
            java_script_enabled=False  # 禁用JS提高性能
        )

    def render(self, template_path: str, data: Dict[str, Any], width: int = 800, height: int = None) -> Optional[str]:
        """
        渲染模板为图片

        Args:
            template_path: 模板文件路径（如 'SlaveMarket/templates/user_profile.html'）
            data: 模板数据字典
            width: 图片宽度，None为自适应
            height: 图片高度，None为自适应

        Returns:
            纯base64图片数据（不包含data:image/png;base64,前缀），失败返回None
        """
        if not self.is_running:
            return None

        if not self._check_browser_health():
            if not self._restart_browser():
                return None

        try:
            template = self.jinja_env.get_template(template_path)
            html_content = template.render(**data)

            future = asyncio.run_coroutine_threadsafe(
                self._render_html_async(html_content, width, height),
                self.browser_loop
            )

            image_bytes = future.result(timeout=15)

            if image_bytes:
                self._render_count += 1
                return base64.b64encode(image_bytes).decode('utf-8')

        except:
            self._restart_browser()

        return None

    async def _render_html_async(self, html_content: str, width: int = None, height: int = None) -> Optional[bytes]:
        """异步渲染HTML（高性能版本）"""

        if not self.context:
            return None

        page = None
        try:
            # 创建新页面
            page = await self.context.new_page()

            # 设置初始视口（使用默认值或自适应）
            initial_width = width or 800
            initial_height = height or 600
            await page.set_viewport_size({"width": initial_width, "height": initial_height})

            # 设置HTML内容（优化等待策略）
            await page.set_content(html_content, wait_until="domcontentloaded")

            # 减少等待时间
            await page.wait_for_timeout(200)

            # 获取实际尺寸并调整视口
            actual_width = initial_width
            actual_height = initial_height

            if width is None or height is None:
                # 获取内容的实际尺寸
                dimensions = await page.evaluate("""
                    () => {
                        const body = document.body;
                        const html = document.documentElement;
                        return {
                            width: Math.max(body.scrollWidth, body.offsetWidth, html.clientWidth, html.scrollWidth, html.offsetWidth),
                            height: Math.max(body.scrollHeight, body.offsetHeight, html.clientHeight, html.scrollHeight, html.offsetHeight)
                        };
                    }
                """)

                if width is None:
                    actual_width = min(dimensions['width'], 800)  # 限制最大宽度
                if height is None:
                    actual_height = min(dimensions['height'], 10000)  # 限制最大高度

                # 重新设置视口
                await page.set_viewport_size({"width": actual_width, "height": actual_height})

            # 高质量截图
            screenshot = await page.screenshot(
                type="png",
                full_page=True
            )

            return screenshot

        except Exception:
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    def stop(self):
        """停止浏览器管理器"""
        if not self.is_running:
            return

        try:
            # 在浏览器线程中执行清理
            if self.browser_loop and self.browser_loop.is_running():
                try:
                    cleanup_future = asyncio.run_coroutine_threadsafe(
                        self._cleanup_browser(),
                        self.browser_loop
                    )
                    cleanup_future.result(timeout=5)  # 减少超时时间
                except Exception:
                    pass

            # 停止事件循环
            if self.browser_loop and self.browser_loop.is_running():
                try:
                    self.browser_loop.call_soon_threadsafe(self.browser_loop.stop)
                except Exception:
                    pass

            # 等待线程结束
            if self.browser_thread and self.browser_thread.is_alive():
                try:
                    self.browser_thread.join(timeout=3)
                except Exception:
                    pass

        except Exception:
            pass
        finally:
            self.is_running = False

    async def _cleanup_browser(self):
        """清理浏览器资源"""
        # 清理上下文
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            finally:
                self.context = None

        # 清理浏览器
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            finally:
                self.browser = None

        # 清理 Playwright
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            finally:
                self.playwright = None

    def cleanup_sync(self):
        """同步清理（用于atexit）"""
        if self.is_running:
            self.stop()

    def _check_browser_health(self) -> bool:
        """检查浏览器健康状态"""
        try:
            if not self.browser:
                return False
            if not self.browser.is_connected():
                return False
            if not self.browser_thread or not self.browser_thread.is_alive():
                return False
            if not self.browser_loop or not self.browser_loop.is_running():
                return False
            return True
        except Exception:
            return False

    def _restart_browser(self) -> bool:
        """重启浏览器"""
        try:
            # 停止当前浏览器
            self.stop()

            # 重新启动
            self.start()

            # 等待浏览器真正启动完成（最多 5 秒）
            for _ in range(50):
                if self.is_running and self.browser_loop:
                    return True
                time.sleep(0.1)

            return False
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取浏览器管理器状态"""
        uptime = "未知"
        if self.is_running and hasattr(self, '_start_time'):
            uptime_seconds = int(time.time() - self._start_time)
            hours = uptime_seconds // 3600
            minutes = (uptime_seconds % 3600) // 60
            uptime = f"{hours}小时{minutes}分钟"

        return {
            "is_running": self.is_running,
            "browser_connected": self.browser.is_connected() if self.browser else False,
            "thread_alive": self.browser_thread.is_alive() if self.browser_thread else False,
            "loop_running": self.browser_loop.is_running() if self.browser_loop else False,
            "render_count": getattr(self, '_render_count', 0),
            "uptime": uptime
        }

    def restart(self) -> bool:
        """手动重启浏览器管理器"""
        return self._restart_browser()


# 全局实例
browser = BrowserManager()
