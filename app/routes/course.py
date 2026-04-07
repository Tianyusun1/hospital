from flask import Blueprint, request, jsonify, session, render_template
from app.extensions import db
from app.models.user import User
from app.models.log import SysLog
from app.models.photography import Course, TrainingClass
from app.utils.decorators import roles_required
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload
from datetime import datetime

course_bp = Blueprint('course', __name__)


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

@course_bp.route('/course/')
@roles_required('admin', 'staff', 'teacher')
def course_page():
    return render_template('course/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


# ================= 课程 API =================

@course_bp.route('/course/api/list', methods=['GET'])
@roles_required('admin', 'staff', 'teacher')
def api_course_list():
    courses = Course.query.order_by(Course.created_at.desc()).all()
    data = [{
        'id': c.id,
        'name': c.name,
        'description': c.description or '',
        'price': float(c.price) if c.price else None,
        'duration_weeks': c.duration_weeks,
        'status': c.status,
        'created_at': c.created_at.strftime('%Y-%m-%d') if c.created_at else ''
    } for c in courses]
    return jsonify({'code': 200, 'data': data})


@course_bp.route('/course/api/add', methods=['POST'])
@roles_required('admin', 'staff')
def api_course_add():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'code': 400, 'msg': '课程名称为必填项'})
    if Course.query.filter_by(name=name).first():
        return jsonify({'code': 400, 'msg': '课程名称已存在'})

    course = Course(
        name=name,
        description=data.get('description', '').strip() or None,
        price=data.get('price') or None,
        duration_weeks=data.get('duration_weeks') or None,
        status=data.get('status', 'active')
    )
    db.session.add(course)
    _write_log('新增课程', f'课程: {name}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '课程添加成功', 'id': course.id})


@course_bp.route('/course/api/update', methods=['POST'])
@roles_required('admin', 'staff')
def api_course_update():
    data = request.get_json()
    course = Course.query.get(data.get('id'))
    if not course:
        return jsonify({'code': 404, 'msg': '课程不存在'})
    if 'name' in data:
        name = data['name'].strip()
        existing = Course.query.filter_by(name=name).first()
        if existing and existing.id != course.id:
            return jsonify({'code': 400, 'msg': '课程名称已存在'})
        course.name = name
    if 'description' in data:
        course.description = data['description'].strip() or None
    if 'price' in data:
        course.price = data['price'] or None
    if 'duration_weeks' in data:
        course.duration_weeks = data['duration_weeks'] or None
    if 'status' in data:
        course.status = data['status']
    _write_log('更新课程', f'课程ID: {course.id}, 名称: {course.name}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '课程更新成功'})


# ================= 班级 API =================

@course_bp.route('/class/api/list', methods=['GET'])
@roles_required('admin', 'staff', 'teacher')
def api_class_list():
    classes = TrainingClass.query.options(
        joinedload(TrainingClass.course),
        joinedload(TrainingClass.teacher)
    ).order_by(TrainingClass.created_at.desc()).all()
    data = [{
        'id': tc.id,
        'class_no': tc.class_no,
        'course_id': tc.course_id,
        'course_name': tc.course.name if tc.course else '',
        'teacher_id': tc.teacher_id,
        'teacher_name': tc.teacher.real_name if tc.teacher else '未分配',
        'start_date': str(tc.start_date) if tc.start_date else '',
        'end_date': str(tc.end_date) if tc.end_date else '',
        'capacity': tc.capacity,
        'status': tc.status,
        'notes': tc.notes or ''
    } for tc in classes]
    return jsonify({'code': 200, 'data': data})


@course_bp.route('/class/api/add', methods=['POST'])
@roles_required('admin', 'staff')
def api_class_add():
    data = request.get_json()
    class_no = data.get('class_no', '').strip()
    course_id = data.get('course_id')
    if not class_no or not course_id:
        return jsonify({'code': 400, 'msg': '班级编号和课程为必填项'})
    if TrainingClass.query.filter_by(class_no=class_no).first():
        return jsonify({'code': 400, 'msg': '班级编号已存在'})
    if not Course.query.get(course_id):
        return jsonify({'code': 404, 'msg': '课程不存在'})

    start_date = end_date = None
    if data.get('start_date'):
        try:
            start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'code': 400, 'msg': '开始日期格式不正确，请使用 YYYY-MM-DD 格式 (例如: 2026-04-07)'})
    if data.get('end_date'):
        try:
            end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'code': 400, 'msg': '结束日期格式不正确，请使用 YYYY-MM-DD 格式 (例如: 2026-04-07)'})

    tc = TrainingClass(
        class_no=class_no,
        course_id=course_id,
        teacher_id=data.get('teacher_id') or None,
        start_date=start_date,
        end_date=end_date,
        capacity=data.get('capacity', 20),
        status=data.get('status', 'open'),
        notes=data.get('notes', '').strip() or None
    )
    db.session.add(tc)
    _write_log('新增班级', f'班级编号: {class_no}, 课程ID: {course_id}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '班级添加成功', 'id': tc.id})


@course_bp.route('/class/api/update', methods=['POST'])
@roles_required('admin', 'staff')
def api_class_update():
    data = request.get_json()
    tc = TrainingClass.query.get(data.get('id'))
    if not tc:
        return jsonify({'code': 404, 'msg': '班级不存在'})
    if 'class_no' in data:
        cn = data['class_no'].strip()
        existing = TrainingClass.query.filter_by(class_no=cn).first()
        if existing and existing.id != tc.id:
            return jsonify({'code': 400, 'msg': '班级编号已存在'})
        tc.class_no = cn
    if 'course_id' in data:
        tc.course_id = data['course_id']
    if 'teacher_id' in data:
        tc.teacher_id = data['teacher_id'] or None
    if 'start_date' in data and data['start_date']:
        try:
            tc.start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    if 'end_date' in data and data['end_date']:
        try:
            tc.end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    if 'capacity' in data:
        tc.capacity = data['capacity']
    if 'status' in data:
        tc.status = data['status']
    if 'notes' in data:
        tc.notes = data['notes'].strip() or None
    _write_log('更新班级', f'班级ID: {tc.id}, 编号: {tc.class_no}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '班级更新成功'})


@course_bp.route('/course/api/teachers', methods=['GET'])
@roles_required('admin', 'staff', 'teacher')
def api_teacher_list():
    from app.models.user import Role
    teacher_role = Role.query.filter_by(role_name='teacher').first()
    if not teacher_role:
        return jsonify({'code': 200, 'data': []})
    teachers = User.query.filter_by(role_id=teacher_role.id, status='approved').all()
    data = [{'id': t.id, 'name': t.real_name} for t in teachers]
    return jsonify({'code': 200, 'data': data})
