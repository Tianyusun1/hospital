# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord
from app.models.log import SysLog
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
# --- 【核心新增】：导入安全校验工具 ---
from app.utils.security import check_operation_risk, check_borrow_duration_risk, get_combined_risk

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


# --- 1. 页面路由：展示设备管理主页 ---
@equipment_bp.route('/')
def equipment_index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('equipment/index.html', role_id=session.get('role_id'))


# --- 2. API: 获取设备列表 ---
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
            'specification': eq.specification or '无',
            'status_code': eq.status,
            'status_text': status_map.get(eq.status, '未知'),
            'is_overdue': is_overdue,
            'due_time': due_time_str,
            'added_by': eq.registrar.real_name if eq.registrar else '系统',
            'created_at': eq.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': data})


# --- 3. API: 新增设备 (包含时间风险审计) ---
@equipment_bp.route('/api/add', methods=['POST'])
@admin_required
def add_equipment():
    data = request.get_json()
    name = data.get('name')
    sn = data.get('serial_number')
    spec = data.get('specification')

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

    # 行为安全检测
    r_level, r_msg = check_operation_risk()
    new_log = SysLog(
        user_id=session['user_id'],
        action='录入设备',
        target=f"名称: {name}, S/N: {sn}",
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(new_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备录入成功'})


# --- 4. API: 修改设备信息 (包含时间风险审计) ---
@equipment_bp.route('/api/update', methods=['POST'])
@admin_required
def update_equipment():
    data = request.get_json()
    eq = Equipment.query.get(data.get('id'))
    if not eq: return jsonify({'code': 404, 'msg': '找不到该设备'})

    eq.name = data.get('name', eq.name)
    eq.specification = data.get('specification', eq.specification)
    if 'status' in data:
        eq.status = data['status']

    # 行为安全检测
    r_level, r_msg = check_operation_risk()
    update_log = SysLog(
        user_id=session['user_id'],
        action='修改设备',
        target=f"S/N: {eq.serial_number}",
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(update_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备信息已更新'})


# --- 5. API: 租借设备 (包含时间风险审计) ---
@equipment_bp.route('/api/borrow', methods=['POST'])
def borrow_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    borrow_days = data.get('days', 7)
    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 0:
        return jsonify({'code': 400, 'msg': '设备当前不可借用'})

    equipment.status = 1
    equipment.current_user_id = session['user_id']
    equipment.borrow_time = datetime.utcnow()

    due_date = equipment.borrow_time + timedelta(days=borrow_days)
    new_record = BorrowRecord(
        equipment_id=equipment.id,
        user_id=session['user_id'],
        status='borrowing',
        borrow_time=equipment.borrow_time,
        due_time=due_date
    )
    db.session.add(new_record)

    # 行为安全检测
    r_level, r_msg = check_operation_risk()
    borrow_log = SysLog(
        user_id=session['user_id'],
        action='借用设备',
        target=f"设备: {equipment.name}",
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(borrow_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': f'借用成功，请于 {due_date.strftime("%Y-%m-%d")} 前归还'})


# --- 6. API: 归还设备 (进阶功能：包含时长异常判定) ---
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

    # --- 【核心逻辑】：双重风险判定 ---
    # 1. 检测操作时间风险 (是否凌晨操作)
    risk1_lvl, risk1_msg = check_operation_risk()

    # 2. 检测使用时长风险 (是否超长占用)
    risk2_lvl, risk2_msg = check_borrow_duration_risk(equipment.borrow_time)

    # 综合判定：取最高级别的风险
    final_risk_lvl, final_risk_msg = get_combined_risk([(risk1_lvl, risk1_msg), (risk2_lvl, risk2_msg)])

    active_record = BorrowRecord.query.filter_by(
        equipment_id=equipment.id,
        status='borrowing'
    ).first()

    if active_record:
        active_record.status = 'returned'
        active_record.return_time = datetime.utcnow()

    equipment.status = 0
    equipment.current_user_id = None
    equipment.borrow_time = None

    # 记录审计日志，带入综合风险判定
    return_log = SysLog(
        user_id=session['user_id'],
        action='归还设备',
        target=f"设备: {equipment.name}",
        risk_level=final_risk_lvl,
        risk_msg=final_risk_msg
    )
    db.session.add(return_log)
    db.session.commit()

    return jsonify({
        'code': 200,
        'msg': '归还成功',
        'risk_warning': final_risk_msg if final_risk_lvl > 0 else None
    })