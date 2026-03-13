# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord  # 确保导入了新模型
from app.utils.decorators import admin_required
from datetime import datetime

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


# --- 1. 页面路由：展示设备管理主页 ---
@equipment_bp.route('/')
def equipment_index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    # 将 role_id 传给前端，用于控制“录入”按钮的显示
    return render_template('equipment/index.html', role_id=session.get('role_id'))


# --- 2. API: 获取设备列表 (供前端渲染表格使用) ---
@equipment_bp.route('/api/list', methods=['GET'])
def get_equipment_list():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    # 按录入时间倒序查询
    equipments = Equipment.query.order_by(Equipment.created_at.desc()).all()

    data = []
    status_map = {0: '在库', 1: '已借出', 2: '维修中', 3: '报废'}

    for eq in equipments:
        data.append({
            'id': eq.id,
            'name': eq.name,
            'serial_number': eq.serial_number,
            'status_code': eq.status,
            'status_text': status_map.get(eq.status, '未知'),
            'added_by': eq.registrar.real_name if eq.registrar else '系统',
            'created_at': eq.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': data})


# --- 3. API: 新增设备 (仅限管理员) ---
@equipment_bp.route('/api/add', methods=['POST'])
@admin_required
def add_equipment():
    data = request.get_json()
    name = data.get('name')
    sn = data.get('serial_number')

    if not name or not sn:
        return jsonify({'code': 400, 'msg': '名称和编号不能为空'})

    if Equipment.query.filter_by(serial_number=sn).first():
        return jsonify({'code': 400, 'msg': '该设备编号已存在'})

    new_eq = Equipment(name=name, serial_number=sn, added_by=session['user_id'])
    db.session.add(new_eq)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备录入成功'})


# --- 4. API: 租借设备 (同步记录审计日志) ---
@equipment_bp.route('/api/borrow', methods=['POST'])
def borrow_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 0:
        return jsonify({'code': 400, 'msg': '设备不可借用'})

    # 1. 更新设备主表状态
    equipment.status = 1
    equipment.current_user_id = session['user_id']
    equipment.borrow_time = datetime.utcnow()

    # 2. 新增：创建借用审计记录
    new_record = BorrowRecord(
        equipment_id=equipment.id,
        user_id=session['user_id'],
        status='borrowing',
        borrow_time=equipment.borrow_time
    )
    db.session.add(new_record)

    db.session.commit()
    return jsonify({'code': 200, 'msg': '借用成功，已生成审计记录'})


# --- 5. API: 归还设备 (同步闭环审计日志) ---
@equipment_bp.route('/api/return', methods=['POST'])
def return_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 1:
        return jsonify({'code': 400, 'msg': '操作无效'})

    # 只有借用人本人或管理员可以操作归还
    if equipment.current_user_id != session['user_id'] and session.get('role_id') != 1:
        return jsonify({'code': 403, 'msg': '无权归还他人借用的设备'})

    # 1. 新增：更新审计记录为“已归还”
    active_record = BorrowRecord.query.filter_by(
        equipment_id=equipment.id,
        status='borrowing'
    ).first()

    if active_record:
        active_record.status = 'returned'
        active_record.return_time = datetime.utcnow()

    # 2. 还原设备主表状态
    equipment.status = 0
    equipment.current_user_id = None
    equipment.borrow_time = None

    db.session.commit()
    return jsonify({'code': 200, 'msg': '归还成功，审计日志已更新'})