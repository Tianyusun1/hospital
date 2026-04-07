from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from app.extensions import db
from app.models.user import User
from app.models.log import SysLog
from app.models.photography import Student, Course, TrainingClass, Enrollment, Payment
from app.utils.decorators import roles_required, login_required
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload
from datetime import datetime

student_bp = Blueprint('student', __name__)


def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


def _write_log(action, target):
    rl, rm = check_operation_risk()
    db.session.add(SysLog(
        user_id=session.get('user_id'),
        action=action,
        target=target,
        ip_address=get_real_ip(),
        risk_level=rl,
        risk_msg=rm
    ))


# ================= 页面路由 =================

@student_bp.route('/student/')
@roles_required('admin', 'staff', 'student')
def student_page():
    return render_template('student/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


@student_bp.route('/student/dashboard')
@roles_required('student')
def student_dashboard():
    return render_template('student/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


# ================= 学员 API =================

@student_bp.route('/student/api/list', methods=['GET'])
@roles_required('admin', 'staff')
def api_student_list():
    students = Student.query.options(
        joinedload(Student.user_account),
        joinedload(Student.creator)
    ).order_by(Student.created_at.desc()).all()
    data = []
    for s in students:
        data.append({
            'id': s.id,
            'name': s.name,
            'phone': s.phone,
            'id_card': s.id_card or '',
            'address': s.address or '',
            'notes': s.notes or '',
            'user_id': s.user_id,
            'created_by_name': s.creator.real_name if s.creator else '',
            'created_at': (s.created_at).strftime('%Y-%m-%d %H:%M') if s.created_at else ''
        })
    return jsonify({'code': 200, 'data': data})


@student_bp.route('/student/api/my_info', methods=['GET'])
@roles_required('student')
def api_my_info():
    uid = session.get('user_id')
    stu = Student.query.filter_by(user_id=uid).first()
    if not stu:
        return jsonify({'code': 404, 'msg': '未找到您的学员档案，请联系教务'})
    return jsonify({'code': 200, 'data': {
        'id': stu.id,
        'name': stu.name,
        'phone': stu.phone,
        'id_card': stu.id_card or '',
        'address': stu.address or '',
        'notes': stu.notes or ''
    }})


@student_bp.route('/student/api/add', methods=['POST'])
@roles_required('admin', 'staff')
def api_student_add():
    data = request.get_json()
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    if not name or not phone:
        return jsonify({'code': 400, 'msg': '姓名和手机号为必填项'})
    if Student.query.filter_by(phone=phone).first():
        return jsonify({'code': 400, 'msg': '该手机号已存在'})
    stu = Student(
        name=name,
        phone=phone,
        id_card=data.get('id_card', '').strip() or None,
        address=data.get('address', '').strip() or None,
        notes=data.get('notes', '').strip() or None,
        created_by=session.get('user_id')
    )
    db.session.add(stu)
    _write_log('新增学员', f'学员: {name}, 手机: {phone}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '学员添加成功', 'id': stu.id})


@student_bp.route('/student/api/update', methods=['POST'])
@roles_required('admin', 'staff')
def api_student_update():
    data = request.get_json()
    stu_id = data.get('id')
    stu = Student.query.get(stu_id)
    if not stu:
        return jsonify({'code': 404, 'msg': '学员不存在'})
    if 'name' in data:
        stu.name = data['name'].strip()
    if 'phone' in data:
        phone = data['phone'].strip()
        existing = Student.query.filter_by(phone=phone).first()
        if existing and existing.id != stu.id:
            return jsonify({'code': 400, 'msg': '该手机号已被其他学员使用'})
        stu.phone = phone
    if 'id_card' in data:
        stu.id_card = data['id_card'].strip() or None
    if 'address' in data:
        stu.address = data['address'].strip() or None
    if 'notes' in data:
        stu.notes = data['notes'].strip() or None
    _write_log('更新学员', f'学员ID: {stu_id}, 姓名: {stu.name}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '学员信息更新成功'})


# ================= 报名 API =================

@student_bp.route('/enrollment/api/list', methods=['GET'])
@roles_required('admin', 'staff', 'student')
def api_enrollment_list():
    role = session.get('role_name')
    uid = session.get('user_id')

    query = Enrollment.query.options(
        joinedload(Enrollment.student),
        joinedload(Enrollment.training_class).joinedload(TrainingClass.course)
    )

    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu:
            return jsonify({'code': 200, 'data': []})
        query = query.filter_by(student_id=stu.id)
    else:
        student_id = request.args.get('student_id')
        if student_id:
            query = query.filter_by(student_id=int(student_id))

    enrollments = query.order_by(Enrollment.enrolled_at.desc()).all()

    data = []
    for e in enrollments:
        tc = e.training_class
        data.append({
            'id': e.id,
            'student_id': e.student_id,
            'student_name': e.student.name if e.student else '',
            'class_id': e.class_id,
            'class_no': tc.class_no if tc else '',
            'course_name': tc.course.name if tc and tc.course else '',
            'status': e.status,
            'enrolled_at': e.enrolled_at.strftime('%Y-%m-%d %H:%M') if e.enrolled_at else '',
            'service_start': str(e.service_start) if e.service_start else '',
            'service_end': str(e.service_end) if e.service_end else '',
            'notes': e.notes or ''
        })
    return jsonify({'code': 200, 'data': data})


@student_bp.route('/enrollment/api/add', methods=['POST'])
@roles_required('admin', 'staff')
def api_enrollment_add():
    data = request.get_json()
    student_id = data.get('student_id')
    class_id = data.get('class_id')
    if not student_id or not class_id:
        return jsonify({'code': 400, 'msg': '学员和班级为必填项'})
    if not Student.query.get(student_id):
        return jsonify({'code': 404, 'msg': '学员不存在'})
    if not TrainingClass.query.get(class_id):
        return jsonify({'code': 404, 'msg': '班级不存在'})

    service_start = None
    service_end = None
    if data.get('service_start'):
        try:
            service_start = datetime.strptime(data['service_start'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'code': 400, 'msg': '服务开始日期格式不正确，请使用 YYYY-MM-DD 格式'})
    if data.get('service_end'):
        try:
            service_end = datetime.strptime(data['service_end'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'code': 400, 'msg': '服务结束日期格式不正确，请使用 YYYY-MM-DD 格式'})

    enroll = Enrollment(
        student_id=student_id,
        class_id=class_id,
        status=data.get('status', 'active'),
        service_start=service_start,
        service_end=service_end,
        notes=data.get('notes', '').strip() or None,
        created_by=session.get('user_id')
    )
    db.session.add(enroll)
    _write_log('新增报名', f'学员ID: {student_id}, 班级ID: {class_id}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '报名成功', 'id': enroll.id})


@student_bp.route('/enrollment/api/update_status', methods=['POST'])
@roles_required('admin', 'staff')
def api_enrollment_update_status():
    data = request.get_json()
    enroll_id = data.get('id')
    new_status = data.get('status')
    allowed = ['active', 'pending', 'withdrawn', 'completed']
    if new_status not in allowed:
        return jsonify({'code': 400, 'msg': '无效的状态值'})
    enroll = Enrollment.query.get(enroll_id)
    if not enroll:
        return jsonify({'code': 404, 'msg': '报名记录不存在'})
    enroll.status = new_status
    _write_log('更新报名状态', f'报名ID: {enroll_id}, 新状态: {new_status}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '状态更新成功'})


# ================= 缴费 API =================

@student_bp.route('/payment/api/list', methods=['GET'])
@roles_required('admin', 'staff')
def api_payment_list():
    enrollment_id = request.args.get('enrollment_id')
    query = Payment.query.options(
        joinedload(Payment.recorder)
    )
    if enrollment_id:
        query = query.filter_by(enrollment_id=int(enrollment_id))
    payments = query.order_by(Payment.pay_time.desc()).all()

    PAY_TYPE_MAP = {'deposit': '定金', 'final': '尾款', 'refund': '退款'}
    PAY_METHOD_MAP = {'cash': '现金', 'wechat': '微信', 'alipay': '支付宝', 'transfer': '转账'}

    data = [{
        'id': p.id,
        'enrollment_id': p.enrollment_id,
        'amount': float(p.amount),
        'pay_type': p.pay_type,
        'pay_type_label': PAY_TYPE_MAP.get(p.pay_type, p.pay_type),
        'pay_method': p.pay_method,
        'pay_method_label': PAY_METHOD_MAP.get(p.pay_method, p.pay_method),
        'pay_time': p.pay_time.strftime('%Y-%m-%d %H:%M') if p.pay_time else '',
        'notes': p.notes or '',
        'recorder': p.recorder.real_name if p.recorder else ''
    } for p in payments]
    return jsonify({'code': 200, 'data': data})


@student_bp.route('/payment/api/add', methods=['POST'])
@roles_required('admin', 'staff')
def api_payment_add():
    data = request.get_json()
    enrollment_id = data.get('enrollment_id')
    amount = data.get('amount')
    pay_type = data.get('pay_type')
    pay_method = data.get('pay_method')

    if not all([enrollment_id, amount, pay_type, pay_method]):
        return jsonify({'code': 400, 'msg': '缺少必填字段'})
    if not Enrollment.query.get(enrollment_id):
        return jsonify({'code': 404, 'msg': '报名记录不存在'})

    pay = Payment(
        enrollment_id=enrollment_id,
        amount=float(amount),
        pay_type=pay_type,
        pay_method=pay_method,
        notes=data.get('notes', '').strip() or None,
        recorded_by=session.get('user_id')
    )
    db.session.add(pay)
    _write_log('新增缴费', f'报名ID: {enrollment_id}, 金额: {amount}, 类型: {pay_type}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '缴费记录添加成功', 'id': pay.id})
