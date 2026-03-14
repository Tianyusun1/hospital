# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment, BorrowRecord
from app.models.log import SysLog
from app.utils.decorators import admin_required
from datetime import datetime, timedelta
from app.utils.security import check_operation_risk, check_borrow_duration_risk, get_combined_risk
# --- 【核心新增】：导入 joinedload 解决 N+1 查询 ---
from sqlalchemy.orm import joinedload

equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


# --- 【核心新增】：获取真实 IP 辅助函数 ---
def get_real_ip():
    """获取客户端真实 IP 地址，防代理穿透"""
    return request.headers.get('X-Forwarded-For', request.remote_addr)


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

    # 【性能优化 1】：使用 joinedload 一次性查出设备对应的 registrar(录入人) 数据
    equipments = Equipment.query.options(joinedload(Equipment.registrar)).order_by(Equipment.created_at.desc()).all()

    # 【性能优化 2】：一次性查出所有“正在借用”的记录，转为字典映射，避免在 for 循环中反复查库！
    active_borrows = BorrowRecord.query.filter_by(status='borrowing').all()
    borrow_map = {b.equipment_id: b for b in active_borrows}

    data = []
    status_map = {0: '在库', 1: '已借出', 2: '维修中', 3: '报废'}
    now_utc = datetime.utcnow()

    for eq in equipments:
        is_overdue = False
        due_time_str = "N/A"

        if eq.status == 1:
            # 直接从字典中获取，不再产生 SQL 查询
            active_record = borrow_map.get(eq.id)
            if active_record and active_record.due_time:
                # 【时间修复】：转为北京时间 (UTC+8) 给前端展示
                due_time_beijing = active_record.due_time + timedelta(hours=8)
                due_time_str = due_time_beijing.strftime('%Y-%m-%d %H:%M')
                if now_utc > active_record.due_time:
                    is_overdue = True

        # 【时间修复】：录入时间也转为北京时间展示
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
        ip_address=get_real_ip(),  # 【安全修复】：补全真实IP记录
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
        ip_address=get_real_ip(),  # 【安全修复】：补全真实IP记录
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
        ip_address=get_real_ip(),  # 【安全修复】：补全真实IP记录
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(borrow_log)
    db.session.commit()

    # 提示时间也转为北京时间
    due_date_beijing = due_date + timedelta(hours=8)
    return jsonify({'code': 200, 'msg': f'借用成功，请于 {due_date_beijing.strftime("%Y-%m-%d")} 前归还'})


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

    # 【权限修复】：不再硬编码 role_id == 1，兼容了通过 role_name 验证的更优方式
    is_admin = session.get('role_id') == 1 or session.get('role_name') == 'admin'
    if equipment.current_user_id != session['user_id'] and not is_admin:
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
        ip_address=get_real_ip(),  # 【安全修复】：补全真实IP记录
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