"""
用户工作流订阅模型
"""
from Models.Extensions import db, get_current_time


class UserWorkflow(db.Model):
    """用户工作流订阅表"""
    __tablename__ = 'user_workflow'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'),
                        nullable=False, comment='用户ID')
    workflow_id = db.Column(db.Integer, db.ForeignKey('workflow.id', ondelete='CASCADE'),
                            nullable=False, comment='工作流ID')
    enabled = db.Column(db.Boolean, default=True, nullable=False, comment='是否启用')
    subscribed_at = db.Column(db.DateTime, default=get_current_time, nullable=False, comment='订阅时间')
    updated_at = db.Column(db.DateTime, default=get_current_time, onupdate=get_current_time,
                           nullable=False, comment='更新时间')

    # 联合唯一约束
    __table_args__ = (
        db.UniqueConstraint('user_id', 'workflow_id', name='uq_user_workflow'),
    )

    # 关系
    user = db.relationship('User', backref=db.backref('user_workflows', lazy='dynamic', cascade='all, delete-orphan'))
    workflow = db.relationship('Workflow', backref=db.backref('user_workflows', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserWorkflow user_id={self.user_id} workflow_id={self.workflow_id} enabled={self.enabled}>'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'workflow_id': self.workflow_id,
            'enabled': self.enabled,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
