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

    def to_dict(self, hide_secret=True):
        """转换为字典"""
        return {
            'id': self.id,
            'key': self.key,
            'value': '******' if (hide_secret and self.is_secret) else self.value,
            'description': self.description,
            'is_secret': self.is_secret,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    @staticmethod
    def get_all():
        """获取所有全局变量"""
        return GlobalVariable.query.all()

    @staticmethod
    def get_by_key(key: str):
        """根据 key 获取变量"""
        return GlobalVariable.query.filter_by(key=key).first()

    @staticmethod
    def set_value(key: str, value: str, description: str = None, is_secret: bool = False):
        """设置变量值（不存在则创建）"""
        var = GlobalVariable.query.filter_by(key=key).first()
        if var:
            var.value = value
            if description is not None:
                var.description = description
            var.is_secret = is_secret
        else:
            var = GlobalVariable(
                key=key,
                value=value,
                description=description,
                is_secret=is_secret
            )
            db.session.add(var)
        db.session.commit()
        return var

    @staticmethod
    def delete_by_key(key: str):
        """删除变量"""
        var = GlobalVariable.query.filter_by(key=key).first()
        if var:
            db.session.delete(var)
            db.session.commit()
            return True
        return False
