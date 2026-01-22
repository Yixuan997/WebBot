"""
数据库迁移脚本 - 创建新表
运行: python migrate_db.py
"""
from app import app
from Models import db

with app.app_context():
    # 创建所有不存在的表
    db.create_all()
    print("数据库迁移完成")
