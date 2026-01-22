"""
@Project：WebBot
@File   ：bot.py
@IDE    ：PyCharm
@Author ：杨逸轩
@Date   ：2025/6/7 10:45
"""
from Models.Extensions import db, get_current_time


class Bot(db.Model):
    """机器人模型"""

    __tablename__ = 'bots'
    id = db.Column(db.Integer, primary_key=True, comment='机器人ID，主键')
    name = db.Column(db.String(100), nullable=False, comment='机器人名称')
    description = db.Column(db.Text, comment='机器人描述')

    # 协议配置
    protocol = db.Column(db.String(20), nullable=False, default='qq', comment='协议类型 (qq/onebot/telegram...)')
    config = db.Column(db.Text, nullable=False, comment='协议特定配置 (JSON格式)')

    is_active = db.Column(db.Boolean, default=True, nullable=False, comment='是否激活')
    is_running = db.Column(db.Boolean, default=False, nullable=False, comment='是否运行中')
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, comment='所有者ID')
    created_at = db.Column(db.DateTime, default=get_current_time, nullable=False, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time, comment='更新时间')

    def get_config(self):
        """获取协议配置"""
        import json

        if self.config:
            try:
                return json.loads(self.config)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_config(self, config_dict):
        """设置协议配置"""
        import json
        self.config = json.dumps(config_dict, ensure_ascii=False)

    def __repr__(self):
        return f'<Bot(id={self.id}, name="{self.name}", protocol="{self.protocol}", owner_id={self.owner_id}, is_running={self.is_running})>'
