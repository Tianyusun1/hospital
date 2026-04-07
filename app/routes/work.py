from flask import Blueprint, request, jsonify, session, render_template
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
