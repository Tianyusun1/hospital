# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord
from app.models.log import SysLog
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
# 去掉了需要你在 security.py 中额外手写的方法，直接保留核心的 check_operation_risk 即可
from app.utils.security import check_operation_risk
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


# --- 5. API: 管理员强制变更设备状态 (维修/报废/下线) ---
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


# --- 7. API: 归还设备 (融合行为安全审计) ---
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

    # ================= 核心行为安全与日志审计合并 =================
    final_risk_lvl = 0
    final_risk_msg = "正常归还"

    # 1. 检查是否存在非工作时间操作 (获取你之前写好的判定)
    time_risk_lvl, time_risk_msg = check_operation_risk()
    if time_risk_lvl > 0:
        final_risk_lvl = time_risk_lvl
        final_risk_msg = time_risk_msg

    if active_record:
        # 2. 检查使用时长是否异常超界 (例如：借用超过 30 天)
        borrow_duration = datetime.utcnow() - active_record.borrow_time
        duration_days = borrow_duration.days

        if duration_days > 30:
            final_risk_lvl = 2  # 强制设置为最高风险(红色报警)
            if time_risk_lvl > 0:
                final_risk_msg = f"双重高危异常：设备被长期占用长达 {duration_days} 天，且 {time_risk_msg}"
            else:
                final_risk_msg = f"异常行为：该设备被长期超期占用，长达 {duration_days} 天"

        # 3. 结算并更新借还记录状态
        active_record.status = 'returned'
        active_record.return_time = datetime.utcnow()
    # ==============================================================

    # 重置设备基础表状态
    equipment.status = 0
    equipment.current_user_id = None
    equipment.borrow_time = None
    equipment.due_time = None

    # 生成安全审计日志
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
        # 将报警信息返回给前端，前端可根据是否存在 risk_warning 决定是否弹出严重警告框
        'risk_warning': final_risk_msg if final_risk_lvl > 0 else None
    })


# --- 8. 【新增】API: 临期及逾期提醒 ---
@equipment_bp.route('/api/reminders', methods=['GET'])
def get_due_reminders():
    """获取当前用户的临近归还提醒 (仅剩 24 小时以内) 及逾期提醒"""
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '未登录'})

    user_id = session['user_id']
    now_utc = datetime.utcnow()

    # 获取该用户当前借用中的所有记录
    active_records = BorrowRecord.query.options(joinedload(BorrowRecord.equipment)).filter_by(
        user_id=user_id,
        status='borrowing'
    ).all()

    reminders = []
    for record in active_records:
        if not record.due_time:
            continue

        # 计算距离归还时间的剩余秒数
        time_diff = record.due_time - now_utc
        remaining_seconds = time_diff.total_seconds()

        # 逻辑1：不足 24 小时 (86400秒)，且还没逾期 (>0)
        if 0 < remaining_seconds <= 86400:
            hours_left = int(remaining_seconds // 3600)
            reminders.append({
                'type': 'warning',
                'msg': f"⏱️ 临期提醒：您借用的【{record.equipment.name}】(编号:{record.equipment.serial_number}) 距离归还期限仅剩 {hours_left} 小时，请合理安排时间并按时归还。"
            })
        # 逻辑2：已经逾期的情况，给以更严重的警告
        elif remaining_seconds <= 0:
            overdue_days = abs(int(remaining_seconds // 86400))
            reminders.append({
                'type': 'danger',
                'msg': f"🚨 逾期警告：您借用的【{record.equipment.name}】已逾期 {overdue_days} 天！请立即归还，以免触发系统风控记录。"
            })

    return jsonify({'code': 200, 'data': reminders})