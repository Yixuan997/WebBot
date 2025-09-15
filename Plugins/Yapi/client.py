"""
Yapi统一请求客户端

封装所有API的Token和HTTP请求逻辑，支持连接池和性能优化
"""

from typing import Optional, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from Core.logging.file_logger import log_info, log_error


class YapiClient:
    """Yapi API客户端"""

    def __init__(self):
        """初始化客户端"""
        self.base_url = "https://api.makuo.cc"
        self.timeout = 30
        self.token = 'xxxxxx'  # 上面网址获取token

        # 创建会话对象，支持连接池
        self.session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,  # 总重试次数
            backoff_factor=1,  # 重试间隔
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
        )

        # 配置HTTP适配器
        adapter = HTTPAdapter(
            pool_connections=10,  # 连接池大小
            pool_maxsize=20,      # 最大连接数
            max_retries=retry_strategy
        )

        # 为HTTP和HTTPS设置适配器
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        log_info(0, "Yapi客户端初始化成功！", "YAPI_CLIENT_INIT")

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            'Authorization': self.token,
            'User-Agent': 'QQ-Bot-Yixuan-Plugin/1.0.0',
            'Accept': 'application/json',
            'Connection': 'keep-alive'  # 保持连接
        }



    def request_sync(self, url: str, method: str = 'GET',
                     params: Optional[Dict] = None,
                     data: Optional[Dict] = None,
                     bot_id: int = None) -> Optional[Dict]:
        """
        发送API请求

        Args:
            url: API端点URL
            method: HTTP方法
            params: URL参数
            data: 请求体数据
            bot_id: 机器人ID，用于日志记录

        Returns:
            API响应数据或None
        """
        try:
            headers = self._get_headers()

            log_info(bot_id or 0, f"发送API请求", "YAPI_REQUEST_START",
                     method=method, url=url)

            # 使用会话对象发送请求（支持连接池）
            if method.upper() == 'POST' and data:
                # POST请求使用form-data
                response = self.session.post(url, data=data, headers=headers,
                                           params=params, timeout=self.timeout)
            elif method.upper() == 'GET':
                # GET请求
                response = self.session.get(url, headers=headers,
                                          params=params, timeout=self.timeout)
            else:
                # 其他请求使用JSON
                headers['Content-Type'] = 'application/json'
                response = self.session.request(method, url, json=data, headers=headers,
                                              params=params, timeout=self.timeout)

            if response.status_code == 200:
                result = response.json()
                log_info(bot_id or 0, f"API请求成功", "YAPI_REQUEST_SUCCESS",
                         status=response.status_code, url=url)
                return result
            else:
                log_error(bot_id or 0, f"API HTTP错误: {response.status_code}",
                          "YAPI_REQUEST_HTTP_ERROR", status=response.status_code, url=url)
                return None

        except requests.exceptions.Timeout:
            log_error(bot_id or 0, f"API请求超时", "YAPI_REQUEST_TIMEOUT", url=url)
            return None
        except Exception as e:
            log_error(bot_id or 0, f"API请求异常: {str(e)}", "YAPI_REQUEST_ERROR",
                      url=url, error=str(e))
            return None

    def close(self):
        """关闭会话，释放连接池资源"""
        if hasattr(self, 'session'):
            self.session.close()
            log_info(0, "Yapi客户端连接池已关闭", "YAPI_CLIENT_CLOSE")


# 全局客户端实例
yapi_client = YapiClient()
