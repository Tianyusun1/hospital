from flask import Blueprint, request, jsonify, render_template, session
from app.extensions import db
from app.models.user import User, Role
from app.models.log import SysLog
from app.models.photography import Student, Course, TrainingClass, Enrollment, Payment, Work, WorkReview
from app.utils.decorators import admin_required
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload
from sqlalchemy import func

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


def _ensure_student_profile_for_user(user_id, creator_id=None):
    stu = Student.query.filter_by(user_id=user_id).first()
    if stu:
        return stu

    user = User.query.get(user_id)
    if not user:
        return None

    candidate_phone = (user.phone or f'auto-{user.id}')[:20]
    existing_phone = Student.query.filter(
        Student.phone == candidate_phone,
        Student.user_id != user.id
    ).first()
    if existing_phone:
        candidate_phone = f'auto-{user.id}'

    stu = Student(
        name=(user.real_name or user.username or '学员').strip(),
        phone=candidate_phone,
        user_id=user.id,
        created_by=creator_id if creator_id is not None else user.id
    )
    db.session.add(stu)
    db.session.flush()
    return stu


# ================= 用户审核与管理 =================

@admin_bp.route('/users/review', methods=['GET'])
@admin_required
def review_page():
    return render_template('admin/review_users.html')


@admin_bp.route('/api/users/pending', methods=['GET'])
@admin_required
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
        role = Role.query.get(user.role_id)
        if role and role.role_name == 'student':
            _ensure_student_profile_for_user(user.id, session.get('user_id'))
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
@admin_required
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
@admin_required
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
        role = Role.query.get(user.role_id)
        if data['status'] == 'approved' and role and role.role_name == 'student':
            _ensure_student_profile_for_user(user.id, session.get('user_id'))
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
@admin_required
def get_roles():
    roles = Role.query.all()
    return jsonify({'code': 200, 'data': [{'id': r.id, 'role_name': r.role_name, 'description': r.description} for r in roles]})


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


# ================= 数据统计 =================

@admin_bp.route('/statistics', methods=['GET'])
@admin_required
def statistics_page():
    return render_template('admin/statistics.html',
                           real_name=session.get('real_name'))


@admin_bp.route('/api/statistics', methods=['GET'])
@admin_required
def get_statistics():
    total_students = Student.query.count()
    active_enrollments = Enrollment.query.filter_by(status='active').count()
    pending_works = Work.query.filter_by(status='submitted').count()

    one_day_ago = datetime.utcnow() - timedelta(days=1)
    risk_24h = SysLog.query.filter(SysLog.risk_level > 0, SysLog.created_at >= one_day_ago).count()

    # 各课程在读报名人数
    course_stats = db.session.query(
        Course.name,
        func.count(Enrollment.id).label('count')
    ).join(TrainingClass, TrainingClass.course_id == Course.id
    ).join(Enrollment, Enrollment.class_id == TrainingClass.id
    ).filter(Enrollment.status == 'active'
    ).group_by(Course.id, Course.name
    ).order_by(func.count(Enrollment.id).desc()).all()

    # 缴费类型分布
    payment_stats = db.session.query(
        Payment.pay_type,
        func.count(Payment.id).label('count'),
        func.sum(Payment.amount).label('total')
    ).group_by(Payment.pay_type).all()

    # 最近10条报名
    recent = Enrollment.query.options(
        joinedload(Enrollment.student),
        joinedload(Enrollment.training_class).joinedload(TrainingClass.course)
    ).order_by(Enrollment.enrolled_at.desc()).limit(10).all()

    return jsonify({'code': 200, 'data': {
        'total_students': total_students,
        'active_enrollments': active_enrollments,
        'pending_works': pending_works,
        'risk_24h': risk_24h,
        'course_stats': [{'name': r.name, 'count': r.count} for r in course_stats],
        'payment_stats': [{'pay_type': r.pay_type, 'count': r.count, 'total': float(r.total or 0)} for r in payment_stats],
        'recent_enrollments': [{
            'student_name': e.student.name if e.student else '',
            'course_name': e.training_class.course.name if e.training_class and e.training_class.course else '',
            'class_no': e.training_class.class_no if e.training_class else '',
            'status': e.status,
            'enrolled_at': e.enrolled_at.strftime('%Y-%m-%d %H:%M') if e.enrolled_at else ''
        } for e in recent]
    }})
