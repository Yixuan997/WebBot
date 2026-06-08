"""
全局变量数据库模型
"""
from Models import db
from Models.Extensions import get_current_time


class GlobalVariable(db.Model):
    """全局变量表"""

    __tablename__ = 'global_variable'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(100), unique=True, nullable=False, comment='变量名')
    value = db.Column(db.Text, nullable=False, default='', comment='变量值')
    description = db.Column(db.String(255), comment='变量描述')
    is_secret = db.Column(db.Boolean, default=False, comment='是否敏感信息（如API Key）')
    created_at = db.Column(db.DateTime, default=get_current_time, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time, comment='更新时间')

    def __repr__(self):
        return f'<GlobalVariable {self.key}>'

