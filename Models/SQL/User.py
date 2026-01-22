"""
@Project ：WebBot
@File    ：User.py
@IDE     ：PyCharm
@Author  ：杨逸轩
@Date    ：2025/6/7 下午6:54
"""

from Models.Extensions import db, get_current_time


class User(db.Model):
    """用户模型"""

    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True, comment='用户ID，主键')
    username = db.Column(db.String(80), unique=True, nullable=False, comment='用户名')
    password = db.Column(db.String(255), nullable=False, comment='用户密码')
    qq = db.Column(db.String(20), unique=True, nullable=False, comment='用户QQ')
    email = db.Column(db.String(100), unique=True, nullable=False, comment='用户邮箱')
    role = db.Column(db.String(20), default='user', comment='角色')
    registered_on = db.Column(db.DateTime, nullable=False, default=get_current_time, comment='注册时间')
    last_login = db.Column(db.DateTime, comment='最后一次登录时间')
    vip = db.Column(db.Boolean, default=False, comment='是否为会员')

    # 添加一些便捷属性
    @property
    def is_admin(self):
        """检查是否为管理员"""
        return self.role == 'admin'

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', registered_on='{self.registered_on}', vip={self.vip}, role={self.role})>"

    # 关系
    bots = db.relationship('Bot', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
