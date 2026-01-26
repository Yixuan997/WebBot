"""
QQ机器人管理系统版本信息
"""

# 版本信息
__version__ = "2.0.1"
__author__ = "Yixuan997"
__email__ = "93653142@qq.com"
__description__ = "QQ机器人管理系统"
__name__ = "WebBot"
# GitHub仓库配置
GITHUB_REPO = "Yixuan997/WebBot"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}"

# 更新相关URL
RELEASES_URL = f"{GITHUB_URL}/releases"
LATEST_RELEASE_API = f"{GITHUB_API_URL}/releases/latest"
DOWNLOAD_URL_TEMPLATE = f"{GITHUB_URL}/archive/refs/tags/v{{version}}.zip"


def get_version_info():
    """获取版本信息"""
    return {
        "version": __version__,
        "name": __name__,
        "github_repo": GITHUB_REPO,
        "github_url": GITHUB_URL,
        "releases_url": RELEASES_URL
    }


def get_version_string():
    """获取版本字符串"""
    return f"{__name__} v{__version__}"
