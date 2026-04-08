from flask import Blueprint, request, jsonify, session, render_template, current_app, send_from_directory
from app.extensions import db
from app.models.log import SysLog
from app.models.photography import Student, Work, WorkReview, Enrollment, TrainingClass
from app.utils.decorators import roles_required
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import uuid

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


def _allowed_file(filename):
    """校验文件扩展名是否在允许列表中（不区分大小写）"""
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'jpg', 'jpeg', 'png', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _save_upload(file):
    """保存上传文件，返回相对 static 目录的路径字符串，或在校验失败时抛出 ValueError"""
    if not file or not file.filename:
        raise ValueError('未选择文件')

    if not _allowed_file(file.filename):
        raise ValueError('不支持的文件格式，仅允许 jpg / jpeg / png / webp')

    # 通过 seek 获取文件大小，避免将全部内容读入内存
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    max_size = current_app.config.get('MAX_UPLOAD_SIZE', 5 * 1024 * 1024)
    if file_size > max_size:
        raise ValueError(f'文件大小超过限制（最大 {max_size // (1024 * 1024)} MB）')

    safe_name = secure_filename(file.filename)
    # 加 8 位随机前缀避免重名
    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"

    upload_dir = current_app.config.get('UPLOAD_FOLDER')
    os.makedirs(upload_dir, exist_ok=True)
    file.save(os.path.join(upload_dir, unique_name))

    # 返回相对 static 目录的路径，如 uploads/abc12345_photo.jpg
    return f"uploads/{unique_name}"


# ================= 页面路由 =================

@work_bp.route('/work/')
@roles_required('admin', 'staff', 'teacher', 'student')
def work_page():
    return render_template('work/index.html',
                           role_name=session.get('role_name'),
                           real_name=session.get('real_name'))


# 提供已上传文件的访问（带登录保护）
@work_bp.route('/work/uploads/<path:filename>')
@roles_required('admin', 'staff', 'teacher', 'student')
def serve_upload(filename):
    upload_dir = current_app.config.get('UPLOAD_FOLDER')
    return send_from_directory(upload_dir, filename)


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

        # 优先使用本地上传路径，其次使用外部 URL
        # file_path 格式固定为 "uploads/<filename>"，统一构造访问 URL
        file_url = ''
        file_path = ''
        if w.file_path:
            file_path = w.file_path
            filename = w.file_path[len('uploads/'):] if w.file_path.startswith('uploads/') else w.file_path
            file_url = f"/work/uploads/{filename}"
        elif w.file_url:
            file_url = w.file_url

        data.append({
            'id': w.id,
            'student_id': w.student_id,
            'student_name': w.student.name if w.student else '',
            'enrollment_id': w.enrollment_id,
            'title': w.title,
            'description': w.description or '',
            'file_url': file_url,
            'file_path': file_path,
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

    # 支持 multipart/form-data（含文件上传）和 application/json 两种提交方式
    is_multipart = request.content_type and 'multipart' in request.content_type

    if is_multipart:
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        deadline_str = request.form.get('deadline', '')
        enrollment_id = request.form.get('enrollment_id') or None
        upload_file = request.files.get('work_file')
    else:
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        deadline_str = data.get('deadline', '')
        enrollment_id = data.get('enrollment_id') or None
        upload_file = None

    if not title:
        return jsonify({'code': 400, 'msg': '作品标题为必填项'})

    # 处理文件上传
    saved_path = None
    if upload_file and upload_file.filename:
        try:
            saved_path = _save_upload(upload_file)
        except ValueError as upload_err:
            # 只返回我们自己抛出的受控错误消息，不泄露内部细节
            err_msg = upload_err.args[0] if upload_err.args else '文件上传失败'
            return jsonify({'code': 400, 'msg': err_msg})

    # 解析截止日期
    deadline = None
    if deadline_str:
        for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
            try:
                deadline = datetime.strptime(deadline_str, fmt)
                break
            except ValueError:
                continue
        if deadline is None:
            return jsonify({'code': 400, 'msg': '截止日期格式不正确，请使用 YYYY-MM-DD 格式'})

    work = Work(
        student_id=stu.id,
        enrollment_id=enrollment_id,
        title=title,
        description=description or None,
        file_path=saved_path,
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
