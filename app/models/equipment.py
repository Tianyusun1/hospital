# 文件位置：app/models/equipment.py
from app.extensions import db
from datetime import datetime


class Equipment(db.Model):
    __tablename__ = 'equipments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 设备名称
    serial_number = db.Column(db.String(50), unique=True, nullable=False)  # 设备编号

    # 设备规格/备注
    specification = db.Column(db.String(255), nullable=True)

    # 状态码：0-在库, 1-已借出, 2-维修中, 3-报废
    status = db.Column(db.Integer, default=0, nullable=False)

    # --- 租借相关字段 ---
    current_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # 当前借用人
    borrow_time = db.Column(db.DateTime, nullable=True)  # 借出时间

    # --- 【新增】：当前借用订单的预计归还时间 ---
    # 当设备状态为 1（已借出）时，此字段记录该次借用的截止日期
    due_time = db.Column(db.DateTime, nullable=True)

    # --- 基础字段 ---
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # 录入管理员
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 建立关联关系
    registrar = db.relationship('User', foreign_keys=[added_by])
    borrower = db.relationship('User', foreign_keys=[current_user_id])


class BorrowRecord(db.Model):
    __tablename__ = 'borrow_records'

    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipments.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # 实际借出时间
    borrow_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # --- 【核心修改】：预计归还时间 ---
    # 改为 nullable=False，强制要求借用时必须选择或生成一个归还期限
    due_time = db.Column(db.DateTime, nullable=False)

    # 实际归还时间（归还后填入）
    return_time = db.Column(db.DateTime, nullable=True)

    # 状态：'borrowing' (借用中), 'returned' (已归还)
    status = db.Column(db.String(20), default='borrowing', nullable=False)

    # 建立关联，方便跨表查询设备名称和借用人姓名
    equipment = db.relationship('Equipment', backref=db.backref('borrow_history', lazy=True))
    user = db.relationship('User', backref=db.backref('borrow_history', lazy=True))