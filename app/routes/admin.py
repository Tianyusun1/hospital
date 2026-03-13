# 文件位置：app/routes/admin.py
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models.user import User, Role  # 导入角色模型
from app.models.equipment import BorrowRecord
from app.models.log import SysLog  # 【核心新增】：导入系统操作日志模型
from app.utils.decorators import admin_required
from werkzeug.security import generate_password_hash  # 用于重置密码
from datetime import datetime

# 创建名为 admin 的蓝图，并为其下所有路由统一添加 /admin 前缀
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ================= 1. 用户审核与管理 (Module 3) =================

@admin_bp.route('/users/review', methods=['GET'])
@admin_required
def review_page():
    """展示待审核用户页面"""
    return render_template('admin/review_users.html')


@admin_bp.route('/api/users/pending', methods=['GET'])
@admin_required
def get_pending_users():
    """获取所有“待审核”状态的用户列表"""
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
    """处理用户审核 (通过/拒绝)，并记录审计日志"""
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

    # 【核心新增】：记录审核审计日志
    review_log = SysLog(
        user_id=request.environ.get('user_id'),  # 假设 session 或环境中有当前操作人
        action='用户审核',
        target=f"用户: {user.real_name}, 动作: {action}",
        ip_address=request.remote_addr
    )
    db.session.add(review_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': msg})


# --- 新增：获取所有正常状态的用户 (图表：查询/展示用户列表) ---
@admin_bp.route('/api/users/all', methods=['GET'])
@admin_required
def get_all_users():
    """获取系统中所有非待审核的用户"""
    users = User.query.filter(User.status != 'pending').all()
    data = [{
        'id': u.id,
        'username': u.username,
        'real_name': u.real_name,
        'department': u.department,
        'role_name': u.role.role_name if u.role else '未分配',
        'status': u.status
    } for u in users]
    return jsonify({'code': 200, 'data': data})


# --- 新增：修改用户信息 (图表：简易修改用户-密码/角色) ---
@admin_bp.route('/api/users/update', methods=['POST'])
@admin_required
def update_user_info():
    """管理员强制修改用户信息或重置密码"""
    data = request.get_json()
    user = User.query.get(data.get('user_id'))
    if not user: return jsonify({'code': 404, 'msg': '用户不存在'})

    # 修改角色
    if 'role_id' in data:
        user.role_id = data['role_id']

    # 强制重置密码
    if 'new_password' in data:
        user.password_hash = generate_password_hash(data['new_password'])

    # 修改账号状态 (如禁用账号)
    if 'status' in data:
        user.status = data['status']

    # 记录审计日志
    update_log = SysLog(
        action='修改用户信息',
        target=f"目标用户: {user.username}",
        ip_address=request.remote_addr
    )
    db.session.add(update_log)

    db.session.commit()
    return jsonify({'code': 200, 'msg': '用户信息更新成功'})


# ================= 2. 借还审计与系统日志 (Module 6) =================

@admin_bp.route('/audit', methods=['GET'])
@admin_required
def audit_page():
    """展示借还审计日志与系统日志界面"""
    return render_template('admin/audit.html')


@admin_bp.route('/api/audit/list', methods=['GET'])
@admin_required
def get_borrow_logs():
    """获取设备借还流转记录 (借还业务专题)"""
    records = BorrowRecord.query.order_by(BorrowRecord.borrow_time.desc()).all()
    log_list = []
    for r in records:
        log_list.append({
            'id': r.id,
            'equipment_name': r.equipment.name,
            'serial_number': r.equipment.serial_number,
            'user_name': r.user.real_name,
            'department': r.user.department,
            'borrow_time': r.borrow_time.strftime('%Y-%m-%d %H:%M:%S'),
            'return_time': r.return_time.strftime('%Y-%m-%d %H:%M:%S') if r.return_time else '借用中',
            'status': '已归还' if r.status == 'returned' else '借用中'
        })
    return jsonify({'code': 200, 'data': log_list})


# --- 新增：系统操作日志查询 (图表：日志列表查询-按操作人/时间筛选) ---
@admin_bp.route('/api/sys_logs/list', methods=['GET'])
@admin_required
def get_sys_logs():
    """获取全局系统操作审计日志，支持参数筛选"""
    # 接收筛选参数
    operator_id = request.args.get('user_id')
    start_date = request.args.get('start_date')  # 格式: 2023-01-01

    query = SysLog.query

    # 按操作人筛选
    if operator_id:
        query = query.filter_by(user_id=operator_id)

    # 按时间筛选
    if start_date:
        dt = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(SysLog.created_at >= dt)

    logs = query.order_by(SysLog.created_at.desc()).all()

    data = [{
        'id': l.id,
        'operator': l.operator.real_name if l.operator else '系统/匿名',
        'action': l.action,
        'target': l.target,
        'ip': l.ip_address,
        'time': l.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for l in logs]

    return jsonify({'code': 200, 'data': data})