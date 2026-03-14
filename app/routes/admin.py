# 文件位置：app/routes/admin.py
from flask import Blueprint, request, jsonify, render_template, session
from app.extensions import db
from app.models.user import User, Role
from app.models.equipment import BorrowRecord
from app.models.log import SysLog
from app.utils.decorators import admin_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from app.utils.security import check_operation_risk
# --- 【核心修复1】：导入 joinedload 用于解决 N+1 查询性能瓶颈 ---
from sqlalchemy.orm import joinedload

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# --- 【核心修复2】：新增获取真实 IP 的辅助函数 ---
def get_real_ip():
    """获取客户端真实 IP 地址，防代理穿透"""
    return request.headers.get('X-Forwarded-For', request.remote_addr)


# ================= 1. 用户审核与管理 =================

@admin_bp.route('/users/review', methods=['GET'])
@admin_required
def review_page():
    return render_template('admin/review_users.html')


@admin_bp.route('/api/users/pending', methods=['GET'])
@admin_required
def get_pending_users():
    users = User.query.filter_by(status='pending').order_by(User.created_at.desc()).all()
    user_list = []
    for u in users:
        user_list.append({
            'id': u.id,
            'username': u.username,
            'real_name': u.real_name,
            'department': u.department,
            'phone': u.phone or '未留存',
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': user_list})


@admin_bp.route('/api/users/do_review', methods=['POST'])
@admin_required
def do_review():
    data = request.get_json()
    user_id = data.get('user_id')
    action = data.get('action')

    if not user_id or action not in ['approve', 'reject']:
        return jsonify({'code': 400, 'msg': '参数不合法'})

    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '找不到该用户'})

    if user.status != 'pending':
        return jsonify({'code': 400, 'msg': '该用户已处理过'})

    if action == 'approve':
        user.status = 'approved'
        msg = f'已通过 {user.real_name} 的入网申请'
    else:
        user.status = 'rejected'
        msg = f'已拒绝 {user.real_name} 的入网申请'

    # --- 行为安全检测 ---
    r_level, r_msg = check_operation_risk()

    review_log = SysLog(
        user_id=session.get('user_id'),
        action='用户审核',
        target=f"用户: {user.real_name}, 动作: {action}",
        ip_address=get_real_ip(),  # 使用真实 IP
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(review_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': msg})


@admin_bp.route('/api/users/all', methods=['GET'])
@admin_required
def get_all_users():
    # 【性能优化】：使用 joinedload 预先加载 role 表，避免 for 循环中发生 N+1 查询
    users = User.query.options(joinedload(User.role)).filter(User.status != 'pending').all()
    data = [{
        'id': u.id,
        'username': u.username,
        'real_name': u.real_name,
        'department': u.department,
        'role_name': u.role.role_name if u.role else '未分配',
        'status': u.status
    } for u in users]
    return jsonify({'code': 200, 'data': data})


@admin_bp.route('/api/users/update', methods=['POST'])
@admin_required
def update_user_info():
    data = request.get_json()
    user = User.query.get(data.get('user_id'))
    if not user: return jsonify({'code': 404, 'msg': '用户不存在'})

    if 'role_id' in data:
        user.role_id = data['role_id']
    if 'new_password' in data:
        user.password_hash = generate_password_hash(data['new_password'])
    if 'status' in data:
        user.status = data['status']

    # --- 行为安全检测 ---
    r_level, r_msg = check_operation_risk()

    update_log = SysLog(
        user_id=session.get('user_id'),
        action='修改用户信息',
        target=f"目标用户: {user.username}",
        ip_address=get_real_ip(),  # 使用真实 IP
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(update_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '用户信息更新成功'})


# ================= 2. 借还审计与系统日志 =================

@admin_bp.route('/audit', methods=['GET'])
@admin_required
def audit_page():
    return render_template('admin/audit.html')


@admin_bp.route('/api/audit/list', methods=['GET'])
@admin_required
def get_borrow_logs():
    # 【性能优化】：使用 joinedload 一次性查出借还记录对应的 equipment 和 user 数据
    records = BorrowRecord.query.options(
        joinedload(BorrowRecord.equipment),
        joinedload(BorrowRecord.user)
    ).order_by(BorrowRecord.borrow_time.desc()).all()

    log_list = []
    for r in records:
        log_list.append({
            'id': r.id,
            'equipment_name': r.equipment.name if r.equipment else '设备已删除',
            'serial_number': r.equipment.serial_number if r.equipment else 'N/A',
            'user_name': r.user.real_name if r.user else '用户已删除',
            'department': r.user.department if r.user else 'N/A',
            'borrow_time': r.borrow_time.strftime('%Y-%m-%d %H:%M:%S'),
            'return_time': r.return_time.strftime('%Y-%m-%d %H:%M:%S') if r.return_time else '借用中',
            'status': '已归还' if r.status == 'returned' else '借用中'
        })
    return jsonify({'code': 200, 'data': log_list})


@admin_bp.route('/api/sys_logs/list', methods=['GET'])
@admin_required
def get_sys_logs():
    operator_id = request.args.get('user_id')
    start_date = request.args.get('start_date')
    risk_level = request.args.get('risk_level')

    # 【性能优化】：预先联合查询 operator (User 表)，解决原来列表推导式引发的数据库性能崩塌
    query = SysLog.query.options(joinedload(SysLog.operator))

    if operator_id:
        query = query.filter_by(user_id=operator_id)
    if risk_level and risk_level.isdigit():
        query = query.filter_by(risk_level=int(risk_level))
    if start_date:
        try:
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(SysLog.created_at >= dt)
        except ValueError:
            pass

    logs = query.order_by(SysLog.created_at.desc()).all()

    data = [{
        'id': l.id,
        'operator': l.operator.real_name if l.operator else '系统/匿名',
        'action': l.action,
        'target': l.target,
        'ip': l.ip_address,
        'risk_level': l.risk_level,
        'risk_msg': l.risk_msg,
        'time': l.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for l in logs]

    return jsonify({'code': 200, 'data': data})


@admin_bp.route('/api/sys_logs/alerts', methods=['GET'])
@admin_required
def get_log_alerts():
    """获取最近 24 小时内的高风险操作数量"""
    one_day_ago = datetime.utcnow() - timedelta(days=1)

    warning_count = SysLog.query.filter(SysLog.risk_level > 0, SysLog.created_at >= one_day_ago).count()
    danger_count = SysLog.query.filter(SysLog.risk_level == 2, SysLog.created_at >= one_day_ago).count()

    return jsonify({
        'code': 200,
        'warning_total': warning_count,
        'danger_total': danger_count
    })