"""
@Project：WebBot
@File   ：update.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/9/14 11:45
"""
import hashlib
import os
import sys
import threading
import zipfile
from pathlib import Path

import requests
from flask import render_template, flash, redirect, url_for, jsonify

from version import __version__, LATEST_RELEASE_API, DOWNLOAD_URL_TEMPLATE, get_version_info

# 简单的更新状态管理
_update_in_progress = False
_update_lock = threading.Lock()


def is_update_in_progress():
    """检查是否有更新在进行"""
    return _update_in_progress


def set_update_status(status):
    """设置更新状态"""
    global _update_in_progress
    with _update_lock:
        _update_in_progress = status


# GitHub代理列表 (按可用性排序)
PROXIES = [
    "https://git.yylx.win",
    "https://gh-proxy.com",
    "https://ghfile.geekertao.top",
    "https://github.tbedu.top",
    "https://ghm.078465.xyz",
    "https://ghfast.top",
    "https://gh-proxy.net",
]


def test_proxy_connection(proxy, test_url, timeout=10):
    """测试单个代理的连接性"""
    try:
        # 修复URL拼接问题，避免双斜杠
        proxy_clean = proxy.rstrip('/')
        test_url_clean = test_url.lstrip('/')
        proxied_url = f"{proxy_clean}/{test_url_clean}"

        response = requests.get(proxied_url, timeout=timeout)

        if response.status_code == 200:
            return True, response
        else:
            return False, None
    except Exception:
        return False, None


def get_release_history():
    """获取Release历史"""
    from version import GITHUB_API_URL
    releases_api = f"{GITHUB_API_URL}/releases"

    # 尝试代理
    for proxy in PROXIES:
        success, response = test_proxy_connection(proxy, releases_api, timeout=10)

        if success:
            try:
                releases = response.json()
                return releases[:5]
            except Exception:
                continue

    # 尝试直连
    try:
        response = requests.get(releases_api, timeout=15)

        if response.status_code == 200:
            releases = response.json()
            return releases[:5]
    except Exception:
        pass

    return []


def check_for_updates():
    """检查更新"""
    current_version = __version__.lstrip('v')

    # 尝试代理
    for proxy in PROXIES:
        success, response = test_proxy_connection(proxy, LATEST_RELEASE_API, timeout=10)

        if success:
            try:
                data = response.json()
                latest = data['tag_name'].lstrip('v')

                if latest != current_version:
                    return {
                        'has_update': True,
                        'current': current_version,
                        'latest': latest,
                        'download': DOWNLOAD_URL_TEMPLATE.format(version=latest),
                        'notes': data.get('body', ''),
                        'proxy_used': proxy
                    }
                return {'has_update': False, 'current': current_version, 'latest': latest, 'proxy_used': proxy}
            except Exception:
                continue

    # 尝试直连
    try:
        response = requests.get(LATEST_RELEASE_API, timeout=15)

        if response.status_code == 200:
            data = response.json()
            latest = data['tag_name'].lstrip('v')

            if latest != current_version:
                return {
                    'has_update': True,
                    'current': current_version,
                    'latest': latest,
                    'download': DOWNLOAD_URL_TEMPLATE.format(version=latest),
                    'notes': data.get('body', ''),
                    'proxy_used': '直连'
                }
            return {'has_update': False, 'current': current_version, 'latest': latest, 'proxy_used': '直连'}
    except Exception:
        pass

    return {'error': '检查更新失败，请检查网络连接'}


def get_latest_release():
    """获取最新Release信息"""
    from version import GITHUB_API_URL
    latest_api = f"{GITHUB_API_URL}/releases/latest"

    # 尝试代理
    for proxy in PROXIES:
        success, response = test_proxy_connection(proxy, latest_api, timeout=10)

        if success:
            try:
                release_data = response.json()
                return release_data
            except Exception:
                continue
        else:
            continue

    # 尝试直连
    try:
        response = requests.get(latest_api, timeout=15)

        if response.status_code == 200:
            release_data = response.json()
            return release_data
    except Exception:
        pass

    return None


def update():
    """系统更新页面"""
    version_info = get_version_info()

    # 获取Release历史
    release_history = get_release_history()

    # 从Release历史中获取最新版本号
    if release_history and len(release_history) > 0:
        latest_release = release_history[0]
        latest_version = latest_release['tag_name'].lstrip('v')
        version_info['latest_version'] = latest_version

        # 检查是否有更新
        current_version = __version__.lstrip('v')
        if latest_version != current_version:
            version_info['update_available'] = True
            # 添加下载URL
            version_info['download_url'] = DOWNLOAD_URL_TEMPLATE.format(version=latest_version)
        else:
            version_info['update_available'] = False
    else:
        # 如果无法获取Release历史，显示本地版本
        version_info['latest_version'] = __version__
        version_info['update_available'] = False

    return render_template('admin/update.html',
                           version_info=version_info,
                           release_history=release_history)


def check_update():
    """手动检查更新"""
    update_result = check_for_updates()

    if update_result.get('error'):
        flash(f'检查更新失败：{update_result["error"]}', 'danger')
    elif update_result.get('has_update'):
        flash(f'发现新版本 {update_result["latest"]}！', 'warning')
    else:
        flash(f'当前已是最新版本', 'success')

    return redirect(url_for('Admin.update'))


def get_latest_release_content():
    """获取最新Release内容"""
    from flask import jsonify

    latest_release = get_latest_release()

    if latest_release:
        return jsonify({
            'success': True,
            'data': latest_release
        })
    else:
        return jsonify({
            'success': False,
            'error': '无法获取最新Release信息'
        })


def calculate_file_hash(file_path, algorithm='sha256'):
    """计算文件的哈希值"""
    hash_obj = hashlib.new(algorithm)

    with open(file_path, 'rb') as f:
        # 分块读取，避免大文件占用过多内存
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)

    return hash_obj.hexdigest()


def verify_github_asset(file_path, asset_info):
    """验证GitHub Release asset的完整性"""
    try:
        # GitHub API返回的asset信息中包含size
        expected_size = asset_info.get('size')
        if expected_size:
            actual_size = os.path.getsize(file_path)
            if actual_size != expected_size:
                return False, f'文件大小不匹配：期望 {expected_size} 字节，实际 {actual_size} 字节'

        # 对于GitHub Release，我们可以验证文件是否为有效的ZIP文件
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # 测试ZIP文件完整性
                zip_ref.testzip()
        except zipfile.BadZipFile:
            return False, 'ZIP文件损坏或格式错误'
        except Exception as e:
            return False, f'ZIP文件验证失败：{str(e)}'

        return True, '文件验证通过'

    except Exception as e:
        return False, f'验证过程出错：{str(e)}'


def download_and_apply_update():
    """下载并应用更新 - 简化的热更新"""
    current_dir = Path.cwd()
    update_zip_path = current_dir / 'update.zip'

    # 检查是否已有更新在进行
    if is_update_in_progress():
        return jsonify({'success': False, 'error': '更新进程已在运行，请稍后再试'})

    # 设置更新状态
    set_update_status(True)

    try:

        # 获取最新Release信息
        latest_release = get_latest_release()
        if not latest_release:
            return jsonify({'success': False, 'error': '无法获取最新版本信息'})

        latest_version = latest_release['tag_name']
        current_version = f"v{__version__}"

        if latest_version == current_version:
            return jsonify({'success': False, 'error': '当前已是最新版本'})

        # 获取下载URL和asset信息
        download_url = None
        asset_info = None
        assets = latest_release.get('assets', [])

        for asset in assets:
            if asset['name'].endswith('.zip'):
                download_url = asset['browser_download_url']
                asset_info = asset
                break

        if not download_url:
            return jsonify({'success': False, 'error': '未找到可下载的更新包'})

        download_success = False

        # 尝试代理下载
        for proxy in PROXIES:
            try:
                # 构建代理下载URL
                proxy_clean = proxy.rstrip('/')
                download_url_clean = download_url.lstrip('/')
                proxied_download_url = f"{proxy_clean}/{download_url_clean}"

                response = requests.get(proxied_download_url, stream=True, timeout=120)
                response.raise_for_status()

                with open(update_zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                download_success = True
                break

            except Exception as e:
                continue

        # 如果代理都失败，尝试直连
        if not download_success:
            try:
                response = requests.get(download_url, stream=True, timeout=120)
                response.raise_for_status()

                with open(update_zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                download_success = True

            except Exception:
                pass

        if not download_success:
            raise Exception("所有下载方式都失败")

        # 验证下载的文件
        is_valid, verify_message = verify_github_asset(str(update_zip_path), asset_info)
        if not is_valid:
            update_zip_path.unlink()  # 删除无效的更新包
            return jsonify({'success': False, 'error': f'文件验证失败：{verify_message}'})

        # 步骤3: 解压更新包
        with zipfile.ZipFile(update_zip_path, 'r') as zip_ref:
            all_files = zip_ref.namelist()

            # 查找包含app.py的目录层级
            app_py_path = None
            for file_path in all_files:
                if file_path.endswith('app.py') and '/' in file_path:
                    app_py_path = file_path
                    break

            if app_py_path:
                # 有子目录结构，提取子目录内容
                prefix = app_py_path.rsplit('/', 1)[0] + '/'
                for member in zip_ref.infolist():
                    if member.filename.startswith(prefix) and member.filename != prefix:
                        member.filename = member.filename[len(prefix):]
                        if member.filename:
                            zip_ref.extract(member, '.')
            else:
                # 直接解压到根目录
                zip_ref.extractall('.')

        # 清理更新包
        update_zip_path.unlink()

        # 设置Flash消息
        flash(f'更新成功！版本 {current_version} → {latest_version}', 'success')

        # 启动自动重启
        import threading
        import time

        def auto_restart():
            time.sleep(2)  # 等待2秒让响应返回
            restart_gunicorn_process()

        restart_thread = threading.Thread(target=auto_restart)
        restart_thread.daemon = True
        restart_thread.start()

        return jsonify({'success': True})

    except Exception as e:
        # 清理文件
        if update_zip_path.exists():
            update_zip_path.unlink()

        return jsonify({'success': False, 'error': f'更新失败: {str(e)}'})

    finally:
        # 重置更新状态
        set_update_status(False)


def get_gunicorn_pidfile_path():
    """获取Gunicorn PID文件路径"""
    try:
        # 如果存在gunicorn_conf.py，快速解析pidfile配置
        conf_path = os.path.join(os.getcwd(), 'gunicorn_conf.py')
        if os.path.exists(conf_path):
            with open(conf_path, 'r', encoding='utf-8') as f:
                content = f.read()

            import re
            pidfile_match = re.search(r'pidfile\s*=\s*[\'"]([^\'"]+)[\'"]', content)
            if pidfile_match:
                pidfile_path = pidfile_match.group(1)
                return pidfile_path

        return None

    except Exception:
        return None


def restart_gunicorn_process():
    """重启应用进程

    - 在 Linux/Unix 上：如果存在 gunicorn_conf.py 且有 pidfile 配置，则优先用 Gunicorn 的 HUP 优雅重启；否则退回到重启当前进程。
    - 在 Windows 上：Gunicorn 不支持，始终重启当前 Python 进程（保留 sys.argv 启动方式）。
    """
    try:
        # Windows 平台：直接重启当前进程，不尝试使用 Gunicorn
        if os.name == 'nt':
            python_exe = sys.executable
            script_args = sys.argv
            os.execv(python_exe, [python_exe] + script_args)
            return

        # 非 Windows（Linux/Unix）：优先尝试通过 Gunicorn 的 PID 文件优雅重启
        pidfile_path = get_gunicorn_pidfile_path()

        if pidfile_path and os.path.exists(pidfile_path):
            with open(pidfile_path, 'r') as f:
                master_pid = int(f.read().strip())

            # 发送 HUP 信号给 Gunicorn 主进程，触发优雅重启
            import signal
            os.kill(master_pid, signal.SIGHUP)

        else:
            # 找不到 PID 文件时，退回到直接重启当前进程
            python_exe = sys.executable
            script_args = sys.argv
            os.execv(python_exe, [python_exe] + script_args)

    except Exception:
        # 出错时静默失败，避免影响当前请求返回
        pass


def health_check():
    """健康检查端点 - 用于检测服务器是否重启完成"""
    import time
    return jsonify({
        'status': 'ok',
        'timestamp': time.time(),
        'version': __version__
    })


def restart_application():
    """重启应用程序"""
    try:
        # 延迟重启，让当前请求先返回
        import threading
        import time

        def delayed_restart():
            time.sleep(2)  # 等待2秒让响应返回
            restart_gunicorn_process()

        # 在后台线程中执行重启
        restart_thread = threading.Thread(target=delayed_restart)
        restart_thread.daemon = True
        restart_thread.start()

        return jsonify({'success': True, 'message': '重启命令已发送'})

    except Exception as e:
        return jsonify({'success': False, 'error': f'重启失败: {str(e)}'})
