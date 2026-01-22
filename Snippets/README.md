# 代码片段 (Snippets)

工作流中可执行的Python代码片段目录。

## 📁 目录结构

```
Snippets/
├── README.md              # 本文件
├── _template.py           # 代码片段模板
├── check_vip.py           # 示例: VIP检查
└── background/            # 后台任务片段
    └── README.md
```

## 📝 代码片段格式

每个代码片段都是一个包含 `execute(context)` 函数的Python文件:

```python
"""
代码片段说明
简短描述这个代码片段的功能
"""

def execute(context):
    """
    执行代码片段
    
    Args:
        context: WorkflowContext - 工作流上下文对象
        
    可用方法:
        - context.event: 消息事件对象
        - context.get_variable(name): 获取变量
        - context.set_variable(name, value): 设置变量
        - context.set_response(message): 设置响应消息
        - context.render_template(text): 渲染模板字符串
        
    Returns:
        dict: 返回结果(可选), 会自动保存到上下文变量
    """
    # 1. 获取输入
    user_id = context.get_variable('user_id')
    
    # 2. 执行业务逻辑
    result = do_something(user_id)
    
    # 3. 设置输出
    context.set_variable('result', result)
    
    # 4. 返回结果(可选)
    return {'success': True, 'data': result}
```

## 🔧 可用模块

代码片段中可以导入以下模块:

### 核心模块
- `Models` - 数据库模型 (User, Bot, WorkflowPlugin等)
- `Core.message.builder.MessageBuilder` - 消息构建器
- `Core.logging.file_logger` - 日志记录

### 标准库
- `datetime`, `time`
- `json`, `re`
- `threading` (用于后台任务)

### 第三方库
- `requests` - HTTP请求

## 💡 使用示例

### 示例1: 简单数据查询

```python
"""查询用户信息"""

def execute(context):
    user_id = context.get_variable('user_id')
    
    from Models import User
    user = User.query.filter_by(qq_id=user_id).first()
    
    if user:
        context.set_variable('user_name', user.username)
        context.set_variable('user_level', user.level)
        return {'found': True}
    else:
        return {'found': False}
```

### 示例2: 发送复杂消息

```python
"""构建并发送Markdown消息"""

def execute(context):
    from Core.message.builder import MessageBuilder
    
    user_name = context.get_variable('user_name')
    score = context.get_variable('score')
    
    markdown_text = f"""
# 用户信息
**姓名**: {user_name}
**积分**: {score}
    """
    
    message = MessageBuilder.markdown(markdown_text)
    context.set_response(message)
    
    return {'message_sent': True}
```

### 示例3: 后台任务

```python
"""启动后台数据同步任务"""

import threading
import time

_sync_thread = None

def execute(context):
    global _sync_thread
    
    if _sync_thread is None or not _sync_thread.is_alive():
        _sync_thread = threading.Thread(target=sync_loop, daemon=True)
        _sync_thread.start()
        return {'status': 'started'}
    else:
        return {'status': 'already_running'}

def sync_loop():
    """后台循环同步"""
    while True:
        time.sleep(3600)  # 每小时执行一次
        try:
            sync_data()
        except Exception as e:
            print(f"同步失败: {e}")

def sync_data():
    """执行数据同步"""
    from Models import User
    # 同步逻辑...
```

## ⚠️ 注意事项

1. **命名规范**: 文件名使用小写字母和下划线,如 `check_vip.py`
2. **必须有execute函数**: 每个片段必须包含 `execute(context)` 函数
3. **异常处理**: 代码片段中应该处理可能的异常
4. **执行超时**: 默认10秒超时,避免长时间阻塞
5. **线程安全**: 后台任务注意线程安全和资源管理

## 🚀 在工作流中使用

1. 在工作流编辑器中添加"执行代码片段"节点
2. 选择要执行的代码片段
3. 配置超时时间(可选)
4. 保存工作流

代码片段的返回值会自动保存到上下文变量中,可以在后续节点中使用。
