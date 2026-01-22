"""
@Project：WebBot 
@File   ：System.py
@IDE    ：PyCharm 
@Author ：杨逸轩
@Date   ：2025/6/7 09:55 
"""
from Models.Extensions import db


# 网站设置
class System(db.Model):
    __tablename__ = 'system'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False, comment='网站标题')
    des = db.Column(db.Text, nullable=False, comment='网站描述')
    key = db.Column(db.Text, nullable=False, comment='网站关键词')
    email = db.Column(db.String(100), nullable=False, comment='邮箱')
    icp = db.Column(db.Text, nullable=False, comment='网站备案号')
    cop = db.Column(db.Text, nullable=False, comment='网站底部版权')

    def __repr__(self):
        return f'<title:{self.title}>'


# 邮件服务配置模型
class Email(db.Model):
    __tablename__ = 'email'
    id = db.Column(db.Integer, primary_key=True)  # 配置项ID
    server = db.Column(db.String(100), nullable=False, comment='SMTP服务器地址')  # 邮件服务器地址
    port = db.Column(db.Integer, nullable=False, default=587, comment='SMTP端口号')  # SMTP端口
    use_tls = db.Column(db.Boolean, nullable=False, default=True, comment='是否启用TLS安全连接')  # 是否开启TLS加密传输
    user = db.Column(db.String(100), nullable=False, comment='SMTP用户名')  # 登录邮件服务器的用户名
    password = db.Column(db.String(100), nullable=False, comment='SMTP密码或授权码')  # 登录密码或应用专用密码
