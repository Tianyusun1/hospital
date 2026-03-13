# 文件位置：app/models/user.py
from app.extensions import db
from datetime import datetime


# 角色表模型
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))


# 用户表模型 (已升级)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)  # 职工工号
    password_hash = db.Column(db.String(255), nullable=False)

    # --- 新增：用于审核的真实身份信息 ---
    real_name = db.Column(db.String(50), nullable=False)  # 真实姓名
    department = db.Column(db.String(100), nullable=False)  # 所属科室
    phone = db.Column(db.String(20), nullable=True)  # 联系电话

    # --- 新增：账号状态 ---
    # 状态取值：'pending' (待审核), 'approved' (已通过), 'rejected' (已拒绝)
    status = db.Column(db.String(20), default='pending', nullable=False)

    # 外键关联角色表
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    role = db.relationship('Role', backref=db.backref('users', lazy=True))