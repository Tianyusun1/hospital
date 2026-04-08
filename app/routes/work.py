import os
import uuid
from flask import Blueprint, request, jsonify, session, render_template, current_app
from werkzeug.utils import secure_filename
from app.extensions import db
from app.models.log import SysLog
from app.models.photography import Student, Work, WorkReview, Enrollment, TrainingClass
from app.utils.decorators import roles_required
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta

work_bp = Blueprint('work', __name__)


def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


def _write_log(action, target, risk_level=None, risk_msg=None):
    if risk_level is None:
        risk_level, risk_msg = check_operation_risk()
    db.session.add(SysLog(
        user_id=session.get('user_id'),
        action=action,
        target=target,
        ip_address=get_real_ip(),
        risk_level=risk_level,
        risk_msg=risk_msg
    ))


def _allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


# ================= 页面路由 =================

@work_bp.route('/work/')
@roles_required('admin', 'staff', 'teacher', 'student')
def work_page():
    return render_template('work/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


# ================= 作品 API =================

@work_bp.route('/work/api/list', methods=['GET'])
@roles_required('admin', 'staff', 'teacher', 'student')
def api_work_list():
    role = session.get('role_name')
    uid = session.get('user_id')

    query = Work.query.options(
        joinedload(Work.student),
        joinedload(Work.reviews).joinedload(WorkReview.teacher)
    )

    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu:
            return jsonify({'code': 200, 'data': []})
        query = query.filter_by(student_id=stu.id)
    elif role == 'teacher':
        # Works from classes where this teacher is assigned
        class_ids = [tc.id for tc in TrainingClass.query.filter_by(teacher_id=uid).all()]
        if not class_ids:
            return jsonify({'code': 200, 'data': []})
        enrollment_ids = [e.id for e in Enrollment.query.filter(Enrollment.class_id.in_(class_ids)).all()]
        if not enrollment_ids:
            return jsonify({'code': 200, 'data': []})
        query = query.filter(Work.enrollment_id.in_(enrollment_ids))

    works = query.order_by(Work.submitted_at.desc()).all()
    now_utc = datetime.utcnow()

    STATUS_MAP = {'submitted': '已提交', 'reviewed': '已点评', 'overdue': '已逾期'}

    # 当前学员 id（用于判断是否可删除）
    current_student_id = None
    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if stu:
            current_student_id = stu.id

    data = []
    for w in works:
        reviews = [{
            'id': r.id,
            'score': r.score,
            'comment': r.comment or '',
            'teacher_name': r.teacher.real_name if r.teacher else '',
            'review_time': r.review_time.strftime('%Y-%m-%d %H:%M') if r.review_time else ''
        } for r in w.reviews]

        deadline_str = ''
        is_overdue = False
        if w.deadline:
            deadline_bj = w.deadline + timedelta(hours=8)
            deadline_str = deadline_bj.strftime('%Y-%m-%d %H:%M')
            is_overdue = now_utc > w.deadline

        # 文件访问 URL：优先使用本地上传文件，其次使用外部链接
        file_access_url = ''
        if w.file_path:
            file_access_url = '/static/' + w.file_path.replace('\\', '/')
        elif w.file_url:
            file_access_url = w.file_url

        # 是否可被当前用户删除
        can_delete = False
        if role in ('admin', 'staff'):
            can_delete = True
        elif role == 'teacher':
            can_delete = True
        elif role == 'student' and current_student_id and w.student_id == current_student_id:
            # 学员只能删除尚未点评的自己的作品
            can_delete = (w.status != 'reviewed')

        data.append({
            'id': w.id,
            'student_id': w.student_id,
            'student_name': w.student.name if w.student else '',
            'enrollment_id': w.enrollment_id,
            'title': w.title,
            'description': w.description or '',
            'file_url': file_access_url,
            'original_filename': w.original_filename or '',
            'submitted_at': (w.submitted_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') if w.submitted_at else '',
            'deadline': deadline_str,
            'is_overdue': is_overdue,
            'status': w.status,
            'status_label': STATUS_MAP.get(w.status, w.status),
            'reviews': reviews,
            'can_delete': can_delete
        })
    return jsonify({'code': 200, 'data': data})


@work_bp.route('/work/api/submit', methods=['POST'])
@roles_required('student')
def api_work_submit():
    uid = session.get('user_id')
    stu = Student.query.filter_by(user_id=uid).first()
    if not stu:
        return jsonify({'code': 403, 'msg': '未找到学员档案'})

    title = request.form.get('title', '').strip()
    if not title:
        return jsonify({'code': 400, 'msg': '作品标题为必填项'})

    deadline = None
    deadline_str = request.form.get('deadline', '').strip()
    if deadline_str:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                deadline = datetime.strptime(deadline_str, fmt)
                break
            except ValueError:
                continue
        if deadline is None:
            return jsonify({'code': 400, 'msg': '截止日期格式不正确，请使用 YYYY-MM-DD HH:MM 格式'})

    # 处理文件上传
    file_path = None
    original_filename = None
    file_size = None
    file_mime = None

    upload_file = request.files.get('file')
    if upload_file and upload_file.filename:
        if not _allowed_file(upload_file.filename):
            return jsonify({'code': 400, 'msg': '不支持该文件格式，仅允许 jpg/jpeg/png/webp'})
        safe_name = secure_filename(upload_file.filename)
        ext = safe_name.rsplit('.', 1)[1].lower() if '.' in safe_name else 'jpg'
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        save_path = os.path.join(upload_folder, unique_name)
        upload_file.save(save_path)
        file_path = 'uploads/' + unique_name
        original_filename = upload_file.filename
        file_size = os.path.getsize(save_path)
        file_mime = upload_file.mimetype or ''

    work = Work(
        student_id=stu.id,
        enrollment_id=request.form.get('enrollment_id') or None,
        title=title,
        description=request.form.get('description', '').strip() or None,
        file_url=None,
        file_path=file_path,
        original_filename=original_filename,
        file_size=file_size,
        file_mime=file_mime,
        deadline=deadline,
        status='submitted'
    )
    db.session.add(work)
    _write_log('提交作品', f'学员: {stu.name}, 作品: {title}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '作品提交成功', 'id': work.id})


@work_bp.route('/work/api/delete/<int:work_id>', methods=['POST'])
@roles_required('admin', 'staff', 'teacher', 'student')
def api_work_delete(work_id):
    """
    删除作品规则：
    - 学员：只能删除自己的、且尚未被点评（status != 'reviewed'）的作品
    - 教师：可删除自己班级学员的作品（无论是否已点评）
    - 管理员/教务：可删除任意作品
    删除时同步删除磁盘文件（若文件不存在则忽略），并写入审计日志。
    """
    role = session.get('role_name')
    uid = session.get('user_id')

    work = Work.query.get(work_id)
    if not work:
        return jsonify({'code': 404, 'msg': '作品不存在'})

    # 权限校验
    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu or work.student_id != stu.id:
            return jsonify({'code': 403, 'msg': '无权删除他人作品'})
        if work.status == 'reviewed':
            return jsonify({'code': 403, 'msg': '作品已被点评，不能自行删除，请联系老师或管理员'})
    elif role == 'teacher':
        # 验证该作品属于此教师负责的班级
        class_ids = [tc.id for tc in TrainingClass.query.filter_by(teacher_id=uid).all()]
        allowed = False
        if work.enrollment_id:
            enrollment = Enrollment.query.get(work.enrollment_id)
            if enrollment and enrollment.class_id in class_ids:
                allowed = True
        if not allowed:
            return jsonify({'code': 403, 'msg': '无权删除该学员的作品'})
    # admin / staff：无额外限制

    work_title = work.title
    student_name = work.student.name if work.student else f'id={work.student_id}'

    # 删除磁盘文件（容错）
    if work.file_path:
        disk_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                 os.path.basename(work.file_path))
        try:
            if os.path.exists(disk_path):
                os.remove(disk_path)
        except OSError:
            pass  # 文件删除失败不阻断数据库操作

    # 删除关联点评记录，再删除作品
    WorkReview.query.filter_by(work_id=work_id).delete()
    db.session.delete(work)

    _write_log(
        '删除作品',
        f'操作者: {session.get("real_name")}({role}), 作品ID: {work_id}, 标题: {work_title}, 学员: {student_name}'
    )
    db.session.commit()
    return jsonify({'code': 200, 'msg': '作品已删除'})


@work_bp.route('/work/api/review', methods=['POST'])
@roles_required('admin', 'teacher')
def api_work_review():
    uid = session.get('user_id')
    data = request.get_json()
    work_id = data.get('work_id')
    work = Work.query.get(work_id)
    if not work:
        return jsonify({'code': 404, 'msg': '作品不存在'})

    score = data.get('score')
    comment = data.get('comment', '').strip()

    review = WorkReview(
        work_id=work_id,
        teacher_id=uid,
        score=score,
        comment=comment or None,
        status='done'
    )
    db.session.add(review)
    work.status = 'reviewed'
    _write_log('点评作品', f'作品ID: {work_id}, 评分: {score}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '点评提交成功'})


@work_bp.route('/work/api/reminders', methods=['GET'])
@roles_required('admin', 'staff', 'teacher', 'student')
def api_work_reminders():
    role = session.get('role_name')
    uid = session.get('user_id')
    now_utc = datetime.utcnow()
    soon = now_utc + timedelta(hours=24)

    query = Work.query.options(joinedload(Work.student))

    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu:
            return jsonify({'code': 200, 'data': []})
        query = query.filter_by(student_id=stu.id)

    works = query.filter(
        Work.status != 'reviewed',
        Work.deadline.isnot(None)
    ).all()

    reminders = []
    for w in works:
        if w.deadline and w.deadline <= soon:
            is_overdue = now_utc > w.deadline
            deadline_bj = w.deadline + timedelta(hours=8)
            student_name = w.student.name if w.student else '未知'
            if is_overdue:
                reminders.append({
                    'type': 'danger',
                    'work_id': w.id,
                    'msg': f'【已逾期】{student_name} 的作品《{w.title}》已超过截止日期 {deadline_bj.strftime("%m-%d %H:%M")}'
                })
            else:
                reminders.append({
                    'type': 'warning',
                    'work_id': w.id,
                    'msg': f'【即将截止】{student_name} 的作品《{w.title}》截止时间 {deadline_bj.strftime("%m-%d %H:%M")}'
                })

    return jsonify({'code': 200, 'data': reminders})


work_bp = Blueprint('work', __name__)


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

@work_bp.route('/work/')
@roles_required('admin', 'staff', 'teacher', 'student')
def work_page():
    return render_template('work/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


# ================= 作品 API =================

@work_bp.route('/work/api/list', methods=['GET'])
@roles_required('admin', 'staff', 'teacher', 'student')
def api_work_list():
    role = session.get('role_name')
    uid = session.get('user_id')

    query = Work.query.options(
        joinedload(Work.student),
        joinedload(Work.reviews).joinedload(WorkReview.teacher)
    )

    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu:
            return jsonify({'code': 200, 'data': []})
        query = query.filter_by(student_id=stu.id)
    elif role == 'teacher':
        # Works from classes where this teacher is assigned
        class_ids = [tc.id for tc in TrainingClass.query.filter_by(teacher_id=uid).all()]
        if not class_ids:
            return jsonify({'code': 200, 'data': []})
        enrollment_ids = [e.id for e in Enrollment.query.filter(Enrollment.class_id.in_(class_ids)).all()]
        if not enrollment_ids:
            return jsonify({'code': 200, 'data': []})
        query = query.filter(Work.enrollment_id.in_(enrollment_ids))

    works = query.order_by(Work.submitted_at.desc()).all()
    now_utc = datetime.utcnow()

    STATUS_MAP = {'submitted': '已提交', 'reviewed': '已点评', 'overdue': '已逾期'}
    data = []
    for w in works:
        reviews = [{
            'id': r.id,
            'score': r.score,
            'comment': r.comment or '',
            'teacher_name': r.teacher.real_name if r.teacher else '',
            'review_time': r.review_time.strftime('%Y-%m-%d %H:%M') if r.review_time else ''
        } for r in w.reviews]

        deadline_str = ''
        is_overdue = False
        if w.deadline:
            deadline_bj = w.deadline + timedelta(hours=8)
            deadline_str = deadline_bj.strftime('%Y-%m-%d %H:%M')
            is_overdue = now_utc > w.deadline

        data.append({
            'id': w.id,
            'student_id': w.student_id,
            'student_name': w.student.name if w.student else '',
            'enrollment_id': w.enrollment_id,
            'title': w.title,
            'description': w.description or '',
            'file_url': w.file_url or '',
            'submitted_at': (w.submitted_at + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') if w.submitted_at else '',
            'deadline': deadline_str,
            'is_overdue': is_overdue,
            'status': w.status,
            'status_label': STATUS_MAP.get(w.status, w.status),
            'reviews': reviews
        })
    return jsonify({'code': 200, 'data': data})


@work_bp.route('/work/api/submit', methods=['POST'])
@roles_required('student')
def api_work_submit():
    uid = session.get('user_id')
    stu = Student.query.filter_by(user_id=uid).first()
    if not stu:
        return jsonify({'code': 403, 'msg': '未找到学员档案'})

    data = request.get_json()
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'code': 400, 'msg': '作品标题为必填项'})

    deadline = None
    if data.get('deadline'):
        try:
            deadline = datetime.strptime(data['deadline'], '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                deadline = datetime.strptime(data['deadline'], '%Y-%m-%d')
            except ValueError:
                return jsonify({'code': 400, 'msg': '截止日期格式不正确，请使用 YYYY-MM-DD HH:MM 格式'})

    work = Work(
        student_id=stu.id,
        enrollment_id=data.get('enrollment_id') or None,
        title=title,
        description=data.get('description', '').strip() or None,
        file_url=data.get('file_url', '').strip() or None,
        deadline=deadline,
        status='submitted'
    )
    db.session.add(work)
    _write_log('提交作品', f'学员: {stu.name}, 作品: {title}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '作品提交成功', 'id': work.id})


@work_bp.route('/work/api/review', methods=['POST'])
@roles_required('admin', 'teacher')
def api_work_review():
    uid = session.get('user_id')
    data = request.get_json()
    work_id = data.get('work_id')
    work = Work.query.get(work_id)
    if not work:
        return jsonify({'code': 404, 'msg': '作品不存在'})

    score = data.get('score')
    comment = data.get('comment', '').strip()

    review = WorkReview(
        work_id=work_id,
        teacher_id=uid,
        score=score,
        comment=comment or None,
        status='done'
    )
    db.session.add(review)
    work.status = 'reviewed'
    _write_log('点评作品', f'作品ID: {work_id}, 评分: {score}')
    db.session.commit()
    return jsonify({'code': 200, 'msg': '点评提交成功'})


@work_bp.route('/work/api/reminders', methods=['GET'])
@roles_required('admin', 'staff', 'teacher', 'student')
def api_work_reminders():
    role = session.get('role_name')
    uid = session.get('user_id')
    now_utc = datetime.utcnow()
    soon = now_utc + timedelta(hours=24)

    query = Work.query.options(joinedload(Work.student))

    if role == 'student':
        stu = Student.query.filter_by(user_id=uid).first()
        if not stu:
            return jsonify({'code': 200, 'data': []})
        query = query.filter_by(student_id=stu.id)

    works = query.filter(
        Work.status != 'reviewed',
        Work.deadline.isnot(None)
    ).all()

    reminders = []
    for w in works:
        if w.deadline and w.deadline <= soon:
            is_overdue = now_utc > w.deadline
            deadline_bj = w.deadline + timedelta(hours=8)
            student_name = w.student.name if w.student else '未知'
            if is_overdue:
                reminders.append({
                    'type': 'danger',
                    'work_id': w.id,
                    'msg': f'【已逾期】{student_name} 的作品《{w.title}》已超过截止日期 {deadline_bj.strftime("%m-%d %H:%M")}'
                })
            else:
                reminders.append({
                    'type': 'warning',
                    'work_id': w.id,
                    'msg': f'【即将截止】{student_name} 的作品《{w.title}》截止时间 {deadline_bj.strftime("%m-%d %H:%M")}'
                })

    return jsonify({'code': 200, 'data': reminders})
