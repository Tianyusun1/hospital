# 文件位置：app/models/log.py
from app.extensions import db
from datetime import datetime


class SysLog(db.Model):
    __tablename__ = 'sys_logs'

    id = db.Column(db.Integer, primary_key=True)

    # 操作人 ID (对应图表：按操作人筛选)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # 操作行为 (例如：登录、借用设备、录入设备、审核用户)
    action = db.Column(db.String(100), nullable=False)

    # 操作对象/备注 (例如：设备序列号 EKG-001 或 用户工号 202301)
    target = db.Column(db.String(255), nullable=True)

    # 访问 IP (可选，增强审计安全性)
    ip_address = db.Column(db.String(50), nullable=True)

    # 操作时间 (对应图表：按时间筛选)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 建立关联，方便直接查询操作人的姓名
    operator = db.relationship('User', backref=db.backref('sys_logs', lazy=True))