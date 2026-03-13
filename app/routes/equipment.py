# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord
from app.models.log import SysLog  # 【核心新增】：导入系统日志模型
from app.utils.decorators import admin_required
from datetime import datetime, timedelta  # 【新增】：用于计算逾期时间

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


# --- 1. 页面路由：展示设备管理主页 ---
@equipment_bp.route('/')
def equipment_index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('equipment/index.html', role_id=session.get('role_id'))


# --- 2. API: 获取设备列表 (包含逾期判定与规格显示) ---
@equipment_bp.route('/api/list', methods=['GET'])
def get_equipment_list():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    equipments = Equipment.query.order_by(Equipment.created_at.desc()).all()

    data = []
    status_map = {0: '在库', 1: '已借出', 2: '维修中', 3: '报废'}

    for eq in equipments:
        is_overdue = False
        due_time_str = "N/A"

        # 判定逾期逻辑 (对应图表：逾期标注)
        if eq.status == 1:
            active_record = BorrowRecord.query.filter_by(
                equipment_id=eq.id,
                status='borrowing'
            ).first()
            if active_record and active_record.due_time:
                due_time_str = active_record.due_time.strftime('%Y-%m-%d %H:%M')
                if datetime.utcnow() > active_record.due_time:
                    is_overdue = True

        data.append({
            'id': eq.id,
            'name': eq.name,
            'serial_number': eq.serial_number,
            'specification': eq.specification or '无',  # 显示设备规格
            'status_code': eq.status,
            'status_text': status_map.get(eq.status, '未知'),
            'is_overdue': is_overdue,  # 逾期标志位
            'due_time': due_time_str,
            'added_by': eq.registrar.real_name if eq.registrar else '系统',
            'created_at': eq.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': data})


# --- 3. API: 新增设备 (包含日志审计) ---
@equipment_bp.route('/api/add', methods=['POST'])
@admin_required
def add_equipment():
    data = request.get_json()
    name = data.get('name')
    sn = data.get('serial_number')
    spec = data.get('specification')  # 接收规格信息

    if not name or not sn:
        return jsonify({'code': 400, 'msg': '名称和编号不能为空'})

    if Equipment.query.filter_by(serial_number=sn).first():
        return jsonify({'code': 400, 'msg': '该设备编号已存在'})

    new_eq = Equipment(
        name=name,
        serial_number=sn,
        specification=spec,
        added_by=session['user_id']
    )
    db.session.add(new_eq)

    # 记录审计日志
    new_log = SysLog(user_id=session['user_id'], action='录入设备', target=f"名称: {name}, S/N: {sn}")
    db.session.add(new_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备录入成功'})


# --- 4. API: 修改设备信息 (图表：修改设备信息/状态) ---
@equipment_bp.route('/api/update', methods=['POST'])
@admin_required
def update_equipment():
    data = request.get_json()
    eq = Equipment.query.get(data.get('id'))
    if not eq: return jsonify({'code': 404, 'msg': '找不到该设备'})

    eq.name = data.get('name', eq.name)
    eq.specification = data.get('specification', eq.specification)

    # 允许管理员手动切换状态 (如设为“维修中”或“报废”)
    if 'status' in data:
        eq.status = data['status']

    # 记录审计日志
    update_log = SysLog(user_id=session['user_id'], action='修改设备', target=f"S/N: {eq.serial_number}")
    db.session.add(update_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备信息已更新'})


# --- 5. API: 租借设备 (包含逾期时间设置与日志) ---
@equipment_bp.route('/api/borrow', methods=['POST'])
def borrow_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    # 默认借用周期为 7 天，也可由前端传参决定
    borrow_days = data.get('days', 7)

    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 0:
        return jsonify({'code': 400, 'msg': '设备当前不可借用'})

    # 1. 更新设备状态
    equipment.status = 1
    equipment.current_user_id = session['user_id']
    equipment.borrow_time = datetime.utcnow()

    # 2. 创建借用审计记录并设置预计归还时间 (逾期标注核心)
    due_date = equipment.borrow_time + timedelta(days=borrow_days)
    new_record = BorrowRecord(
        equipment_id=equipment.id,
        user_id=session['user_id'],
        status='borrowing',
        borrow_time=equipment.borrow_time,
        due_time=due_date
    )
    db.session.add(new_record)

    # 3. 写入系统审计日志
    borrow_log = SysLog(user_id=session['user_id'], action='借用设备', target=f"设备: {equipment.name}")
    db.session.add(borrow_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': f'借用成功，请于 {due_date.strftime("%Y-%m-%d")} 前归还'})


# --- 6. API: 归还设备 (包含闭环审计日志) ---
@equipment_bp.route('/api/return', methods=['POST'])
def return_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 1:
        return jsonify({'code': 400, 'msg': '操作无效'})

    if equipment.current_user_id != session['user_id'] and session.get('role_id') != 1:
        return jsonify({'code': 403, 'msg': '无权归还他人借用的设备'})

    active_record = BorrowRecord.query.filter_by(
        equipment_id=equipment.id,
        status='borrowing'
    ).first()

    if active_record:
        active_record.status = 'returned'
        active_record.return_time = datetime.utcnow()

    # 还原状态
    equipment.status = 0
    equipment.current_user_id = None
    equipment.borrow_time = None

    # 写入系统审计日志
    return_log = SysLog(user_id=session['user_id'], action='归还设备', target=f"设备: {equipment.name}")
    db.session.add(return_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': '归还成功，已自动更新审计日志'})