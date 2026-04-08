from flask import Blueprint, request, jsonify, render_template, session
from app.extensions import db
from app.models.user import User, Role
from app.models.log import SysLog
from app.models.photography import Enrollment, Payment, WorkReview
from app.utils.decorators import admin_required, roles_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
DEFAULT_TEACHER_DEPARTMENT = '教学部'


def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


def ensure_core_roles():
    role_defs = [
        ('admin', '超级管理员'),
        ('staff', '教务/前台'),
        ('teacher', '教师'),
        ('student', '学员')
    ]
    role_map = {}
    changed = False
    for role_name, desc in role_defs:
        role = Role.query.filter_by(role_name=role_name).first()
        if not role:
            role = Role(role_name=role_name, description=desc)
            db.session.add(role)
            changed = True
        role_map[role_name] = role
    if changed:
        db.session.commit()
    return role_map


# ================= 用户审核与管理 =================

@admin_bp.route('/users/review', methods=['GET'])
@roles_required('admin', 'staff')
def review_page():
    return render_template('admin/review_users.html', role_name=session.get('role_name'))


@admin_bp.route('/api/users/pending', methods=['GET'])
@roles_required('admin', 'staff')
def get_pending_users():
    users = User.query.options(joinedload(User.role)).filter_by(status='pending').order_by(User.created_at.desc()).all()
    user_list = [{
        'id': u.id,
        'username': u.username,
        'real_name': u.real_name,
        'department': u.department,
        'phone': u.phone or '未留存',
        'role_name': u.role.role_name if u.role else 'student',
        'created_at': u.created_at.strftime('%Y-%m-%d %H:%M')
    } for u in users]
    return jsonify({'code': 200, 'data': user_list})


@admin_bp.route('/api/users/do_review', methods=['POST'])
@roles_required('admin', 'staff')
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
        msg = f'已通过 {user.real_name} 的注册申请'
    else:
        user.status = 'rejected'
        msg = f'已拒绝 {user.real_name} 的注册申请'

    r_level, r_msg = check_operation_risk()
    review_log = SysLog(
        user_id=session.get('user_id'),
        action='用户审核',
        target=f"用户: {user.real_name}, 动作: {action}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(review_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': msg})


@admin_bp.route('/api/users/all', methods=['GET'])
@roles_required('admin', 'staff')
def get_all_users():
    users = User.query.options(joinedload(User.role)).filter(User.status != 'pending').all()
    data = [{
        'id': u.id,
        'username': u.username,
        'real_name': u.real_name,
        'department': u.department,
        'role_name': u.role.role_name if u.role else '未分配',
        'role_id': u.role_id,
        'status': u.status,
        'is_locked': u.is_locked
    } for u in users]
    return jsonify({'code': 200, 'data': data})


@admin_bp.route('/api/users/update', methods=['POST'])
@roles_required('admin', 'staff')
def update_user_info():
    data = request.get_json()
    user = User.query.get(data.get('user_id'))
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'})

    if 'role_id' in data:
        user.role_id = data['role_id']
    if 'new_password' in data and data['new_password']:
        user.password_hash = generate_password_hash(data['new_password'])
    if 'status' in data:
        user.status = data['status']
    if 'unlock' in data and data['unlock'] is True:
        user.is_locked = False
        user.failed_login_attempts = 0

    r_level, r_msg = check_operation_risk()
    update_log = SysLog(
        user_id=session.get('user_id'),
        action='修改用户信息',
        target=f"目标用户: {user.username}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(update_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '用户信息更新成功'})


@admin_bp.route('/api/users/delete', methods=['POST'])
@admin_required
def delete_user():
    data = request.get_json()
    user = User.query.get(data.get('user_id'))

    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'})

    if user.id == session.get('user_id'):
        return jsonify({'code': 400, 'msg': '操作拒绝：不能删除当前登录的账号'})

    username = user.username
    db.session.delete(user)

    r_level, r_msg = check_operation_risk()
    del_log = SysLog(
        user_id=session.get('user_id'),
        action='删除用户',
        target=f"被删用户: {username}",
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(del_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '该用户已被彻底删除'})


@admin_bp.route('/api/users/roles', methods=['GET'])
@roles_required('admin', 'staff')
def get_roles():
    role_map = ensure_core_roles()
    roles = [role_map['admin'], role_map['staff'], role_map['teacher'], role_map['student']]
    return jsonify({'code': 200, 'data': [{'id': r.id, 'role_name': r.role_name, 'description': r.description} for r in roles]})


@admin_bp.route('/api/users/create', methods=['POST'])
@roles_required('admin', 'staff')
def create_teacher_user():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    real_name = (data.get('real_name') or '').strip()
    department = (data.get('department') or DEFAULT_TEACHER_DEPARTMENT).strip() or DEFAULT_TEACHER_DEPARTMENT
    phone = (data.get('phone') or '').strip() or None
    role_name = (data.get('role_name') or 'teacher').strip()

    if role_name != 'teacher':
        return jsonify({'code': 400, 'msg': '当前仅支持新增教师账号'})
    if not username or not password or not real_name:
        return jsonify({'code': 400, 'msg': '账号、密码、姓名为必填项'})
    if len(password) < 6:
        return jsonify({'code': 400, 'msg': '密码长度不能少于6位'})
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'msg': '该账号已存在'})

    role_map = ensure_core_roles()
    teacher_role = role_map['teacher']

    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        real_name=real_name,
        department=department,
        phone=phone,
        status='approved',
        role_id=teacher_role.id
    )
    db.session.add(user)

    r_level, r_msg = check_operation_risk()
    create_log = SysLog(
        user_id=session.get('user_id'),
        action='新增教师账号',
        target=f'账号: {username}, 姓名: {real_name}',
        ip_address=get_real_ip(),
        risk_level=r_level,
        risk_msg=r_msg
    )
    db.session.add(create_log)
    db.session.commit()
    return jsonify({'code': 200, 'msg': '教师账号创建成功'})


# ================= 审计日志 =================

@admin_bp.route('/audit', methods=['GET'])
@admin_required
def audit_page():
    return render_template('admin/audit.html')


@admin_bp.route('/api/audit/list', methods=['GET'])
@admin_required
def get_audit_logs():
    """报名/缴费/点评操作审计"""
    records = SysLog.query.options(
        joinedload(SysLog.operator)
    ).filter(
        SysLog.action.in_(['新增报名', '更新报名状态', '新增缴费', '点评作品', '新增学员', '更新学员'])
    ).order_by(SysLog.created_at.desc()).limit(200).all()

    log_list = [{
        'id': r.id,
        'operator': r.operator.username if r.operator else '系统',
        'operator_name': r.operator.real_name if r.operator else '系统',
        'action': r.action,
        'target': r.target or '',
        'time': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'ip': r.ip_address or ''
    } for r in records]
    return jsonify({'code': 200, 'data': log_list})


@admin_bp.route('/api/sys_logs/list', methods=['GET'])
@admin_required
def get_sys_logs():
    operator_username = request.args.get('user_id')
    start_date = request.args.get('start_date')
    risk_level = request.args.get('risk_level')

    query = SysLog.query.outerjoin(User, SysLog.user_id == User.id).options(joinedload(SysLog.operator))

    if operator_username:
        query = query.filter(User.username == operator_username)

    if risk_level and risk_level.isdigit():
        query = query.filter(SysLog.risk_level == int(risk_level))

    if start_date:
        try:
            dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(SysLog.created_at >= dt)
        except ValueError:
            pass

    logs = query.order_by(SysLog.created_at.desc()).all()

    data = [{
        'id': l.id,
        'operator': l.operator.username if l.operator else '系统/匿名',
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
    one_day_ago = datetime.utcnow() - timedelta(days=1)
    warning_count = SysLog.query.filter(SysLog.risk_level > 0, SysLog.created_at >= one_day_ago).count()
    danger_count = SysLog.query.filter(SysLog.risk_level == 2, SysLog.created_at >= one_day_ago).count()
    return jsonify({
        'code': 200,
        'warning_total': warning_count,
        'danger_total': danger_count
    })
