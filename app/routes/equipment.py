# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord
from app.models.log import SysLog
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
from app.utils.security import check_operation_risk, check_borrow_duration_risk, get_combined_risk
from sqlalchemy.orm import joinedload

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


def get_real_ip():
    """获取客户端真实 IP 地址"""
    return request.headers.get('X-Forwarded-For', request.remote_addr)


# --- 1. 页面路由 ---
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

    # 加载设备及其录入人信息
    equipments = Equipment.query.options(joinedload(Equipment.registrar)).order_by(Equipment.created_at.desc()).all()

    # 获取当前所有借用中的记录用于逾期判断
    active_borrows = BorrowRecord.query.filter_by(status='borrowing').all()
    borrow_map = {b.equipment_id: b for b in active_borrows}

    data = []
    status_map = {0: '在库', 1: '已借出', 2: '维修中', 3: '报废'}
    now_utc = datetime.utcnow()

    for eq in equipments:
        is_overdue = False
        due_time_str = "N/A"

        if eq.status == 1:
            active_record = borrow_map.get(eq.id)
            if active_record and active_record.due_time:
                # 转为北京时间展示
                due_time_beijing = active_record.due_time + timedelta(hours=8)
                due_time_str = due_time_beijing.strftime('%Y-%m-%d %H:%M')
                # 逾期判定
                if now_utc > active_record.due_time:
                    is_overdue = True

        created_at_beijing = eq.created_at + timedelta(hours=8)

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
            'created_at': created_at_beijing.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': data})


# --- 3. API: 新增设备 ---
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

    r_level, r_msg = check_operation_risk()
    new_log = SysLog(
        user_id=session['user_id'],
        action='录入设备',
        target=f"名称: {name}, S/N: {sn}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(new_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备录入成功'})


# --- 4. API: 修改设备基础信息 ---
@equipment_bp.route('/api/update', methods=['POST'])
@admin_required
def update_equipment():
    data = request.get_json()
    eq = Equipment.query.get(data.get('id'))
    if not eq: return jsonify({'code': 404, 'msg': '找不到该设备'})

    eq.name = data.get('name', eq.name)
    eq.specification = data.get('specification', eq.specification)

    r_level, r_msg = check_operation_risk()
    update_log = SysLog(
        user_id=session['user_id'],
        action='修改基本信息',
        target=f"S/N: {eq.serial_number}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(update_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '设备基本信息已更新'})


# --- 5. 【新增】API: 管理员强制变更设备状态 (维修/报废/下线) ---
@equipment_bp.route('/api/admin/update_status', methods=['POST'])
@admin_required
def admin_update_status():
    data = request.get_json()
    eq_id = data.get('equipment_id')
    new_status = data.get('status')  # 0-在库, 2-维修中, 3-报废
    note = data.get('note', '未填写原因')

    equipment = Equipment.query.get(eq_id)
    if not equipment:
        return jsonify({'code': 404, 'msg': '设备不存在'})

    # 安全检查：借用中的设备不能直接改状态，必须先归还
    if equipment.status == 1:
        return jsonify({'code': 400, 'msg': '设备正在借用中，请先执行归还流程'})

    status_names = {0: '在库', 2: '维修中', 3: '报废'}
    old_status_name = status_names.get(equipment.status, '未知')
    new_status_name = status_names.get(new_status, '未知')

    # 更新状态
    equipment.status = new_status

    # 记录审计日志
    r_level, r_msg = check_operation_risk()
    log = SysLog(
        user_id=session['user_id'],
        action='手动变更状态',
        target=f"设备:{equipment.name}(S/N:{equipment.serial_number}) 从[{old_status_name}]变更为[{new_status_name}]。原因:{note}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({'code': 200, 'msg': f'状态已更新为: {new_status_name}'})


# --- 6. API: 租借设备 ---
@equipment_bp.route('/api/borrow', methods=['POST'])
def borrow_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    return_date_str = data.get('return_date')

    if not return_date_str:
        return jsonify({'code': 400, 'msg': '必须选择预计归还日期'})

    equipment = Equipment.query.get(eq_id)
    if not equipment or equipment.status != 0:
        return jsonify({'code': 400, 'msg': '设备当前不可借用（可能已借出或在维修）'})

    try:
        due_date_obj = datetime.strptime(return_date_str, '%Y-%m-%d')
        due_date_utc = due_date_obj.replace(hour=23, minute=59, second=59) - timedelta(hours=8)
        if due_date_utc <= datetime.utcnow():
            return jsonify({'code': 400, 'msg': '归还日期不能早于当前时间'})
    except ValueError:
        return jsonify({'code': 400, 'msg': '日期格式无效'})

    equipment.status = 1
    equipment.current_user_id = session['user_id']
    equipment.borrow_time = datetime.utcnow()
    equipment.due_time = due_date_utc

    new_record = BorrowRecord(
        equipment_id=equipment.id,
        user_id=session['user_id'],
        status='borrowing',
        borrow_time=equipment.borrow_time,
        due_time=due_date_utc
    )
    db.session.add(new_record)

    r_level, r_msg = check_operation_risk()
    borrow_log = SysLog(
        user_id=session['user_id'],
        action='借用设备',
        target=f"设备: {equipment.name}, 预计归还: {return_date_str}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(borrow_log)
    db.session.commit()

    return jsonify({'code': 200, 'msg': f'借用成功，请于 {return_date_str} 前归还'})


# --- 7. API: 归还设备 ---
@equipment_bp.route('/api/return', methods=['POST'])
def return_equipment():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    data = request.get_json()
    eq_id = data.get('equipment_id')
    equipment = Equipment.query.get(eq_id)

    if not equipment or equipment.status != 1:
        return jsonify({'code': 400, 'msg': '操作无效'})

    is_admin = session.get('role_id') == 1 or session.get('role_name') == 'admin'
    if equipment.current_user_id != session['user_id'] and not is_admin:
        return jsonify({'code': 403, 'msg': '无权归还他人借用的设备'})

    active_record = BorrowRecord.query.filter_by(
        equipment_id=equipment.id,
        status='borrowing'
    ).first()

    risk1_lvl, risk1_msg = check_operation_risk()
    risk2_lvl, risk2_msg = check_borrow_duration_risk(active_record)
    final_risk_lvl, final_risk_msg = get_combined_risk([(risk1_lvl, risk1_msg), (risk2_lvl, risk2_msg)])

    if active_record:
        active_record.status = 'returned'
        active_record.return_time = datetime.utcnow()

    equipment.status = 0
    equipment.current_user_id = None
    equipment.borrow_time = None
    equipment.due_time = None

    return_log = SysLog(
        user_id=session['user_id'],
        action='归还设备',
        target=f"设备: {equipment.name}",
        ip_address=get_real_ip(),
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