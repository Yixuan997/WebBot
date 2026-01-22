"""
工作流数据库模型
"""
from sqlalchemy.ext.mutable import MutableDict

from Models import db
from Models.Extensions import get_current_time


class Workflow(db.Model):
    """工作流表"""

    __tablename__ = 'workflow'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), unique=True, nullable=False, comment='插件名称')
    description = db.Column(db.Text, comment='插件描述')
    enabled = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用')
    priority = db.Column(db.Integer, default=100, comment='优先级，数字越小优先级越高')
    # 使用MutableDict自动追踪JSON字段变化
    config = db.Column(MutableDict.as_mutable(db.JSON), nullable=False, comment='工作流配置（JSON）')
    created_at = db.Column(db.DateTime, default=get_current_time, comment='创建时间')
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time, comment='更新时间')
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), comment='创建者ID')

    # 关系
    creator = db.relationship('User', backref=db.backref('workflow', lazy='dynamic'))

    def __repr__(self):
        return f'<Workflow {self.name}>'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'priority': self.priority,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'creator_id': self.creator_id,
            'creator_name': self.creator.username if self.creator else None
        }

    @staticmethod
    def create_from_config(name: str, description: str, config: dict, creator_id: int = None,
                           enabled: bool = True, priority: int = 100):
        """从配置创建插件"""
        plugin = Workflow(
            name=name,
            description=description,
            config=config,
            creator_id=creator_id,
            enabled=enabled,
            priority=priority
        )
        db.session.add(plugin)
        db.session.commit()
        return plugin

    def get_config(self):
        """获取配置"""
        return self.config if self.config else {}

    def update_config(self, config: dict):
        """更新配置"""
        # MutableDict会自动追踪变化，不需要flag_modified
        self.config = config
        self.updated_at = get_current_time()
        db.session.commit()

    def toggle_enabled(self):
        """切换启用状态"""
        self.enabled = not self.enabled
        db.session.commit()

    @staticmethod
    def get_enabled_plugins():
        """获取所有启用的插件，按优先级排序"""
        return Workflow.query.filter_by(enabled=True).order_by(Workflow.priority.asc()).all()
