# QQ 机器人管理系统

一个基于 Flask 的多协议机器人管理与工作流平台，支持机器人统一管理、可视化流程编排与后台运维。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-green.svg)](https://flask.palletsprojects.com/)

## 快速导航

- [项目特性](#项目特性)
- [协议支持](#协议支持)
- [快速开始](#快速开始)
- [配置流程](#配置流程)
- [工作流示例](#工作流示例)
- [开发与贡献](#开发与贡献)
- [部署建议](#部署建议)

## 项目特性

- 多机器人统一管理：一个后台管理多个机器人实例
- 多协议适配：统一事件模型，便于扩展新协议
- 可视化工作流：通过节点编排实现自动化处理逻辑
- 内置变量系统：支持模板变量与节点间数据传递
- 管理后台完整：用户权限、日志查看、系统设置集中管理
- 可运维：支持 Gunicorn 部署、日志排查与在线配置

## 协议支持

| 协议 | 状态 | 说明 |
|---|---|---|
| `qq` | 已支持 | QQ 官方协议适配 |
| `onebot` | 已支持 | OneBot V11 协议适配 |
| `kook` | 已支持 | KOOK 协议适配 |

## 快速开始

### 1) 环境要求

- Python 3.10+
- 建议使用虚拟环境

### 2) 安装依赖

```bash
git clone https://github.com/Yixuan997/WebBot.git
cd WebBot

# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux/macOS
# python3 -m venv .venv
# source .venv/bin/activate

pip install -r requirements.txt
```

### 3) 启动项目

```bash
# 开发
python app.py

# 生产（示例）
gunicorn -c gunicorn_conf.py app:app
```

默认访问地址：`http://127.0.0.1:5000`

## 配置流程

1. 首次访问后台并完成初始化安装
2. 创建管理员账号并登录系统
3. 在「机器人管理」中添加机器人配置
4. 在「工作流管理」中创建或导入工作流
5. 启动机器人并观察日志确认收发正常

## 工作流示例

工作流能力覆盖触发、条件、数据处理和动作执行，常见节点包括：

- 触发：关键词触发、定时触发
- 逻辑：条件判断、循环遍历
- 数据：字符串处理、JSON 提取、变量设置、数据存储
- 动作：发送消息、HTTP 请求、自定义端点、HTML 渲染

常见变量示例：

- `{{message}}`
- `{{group_id}}`
- `{{response_json.data.xxx}}`
- `{{endpoint_response}}`

## 开发与贡献

- 欢迎通过 Issue 提交问题与需求建议
- 欢迎通过 PR 提交功能优化与修复
- 提交前建议先在本地完成基础运行验证

## 部署建议

- 推荐使用 `gunicorn` + `nginx`
- 当前建议 `workers=1`，避免运行态状态同步问题
- 建议配置日志轮转，避免日志文件持续膨胀
- Webhook 协议需要公网可达的回调地址

---

<div align="center">

**🤖 让机器人管理更简单、更稳定。**

[![快速开始](https://img.shields.io/badge/快速开始-查看文档-brightgreen.svg?style=for-the-badge)](#快速开始)
[![工作流](https://img.shields.io/badge/工作流-可视化编排-blue.svg?style=for-the-badge)](#工作流示例)
[![部署建议](https://img.shields.io/badge/部署建议-生产可用-orange.svg?style=for-the-badge)](#部署建议)

**© 2026 QQ 机器人管理系统**

</div>
