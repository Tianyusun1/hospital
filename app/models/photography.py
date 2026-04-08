from app.extensions import db
from datetime import datetime

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    id_card = db.Column(db.String(30), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_account = db.relationship('User', foreign_keys=[user_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    enrollments = db.relationship('Enrollment', back_populates='student', lazy=True)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    duration_weeks = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    classes = db.relationship('TrainingClass', back_populates='course', lazy=True)

class TrainingClass(db.Model):
    __tablename__ = 'training_classes'
    id = db.Column(db.Integer, primary_key=True)
    class_no = db.Column(db.String(50), unique=True, nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    capacity = db.Column(db.Integer, default=20)
    status = db.Column(db.String(20), default='open', nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    course = db.relationship('Course', back_populates='classes')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
    enrollments = db.relationship('Enrollment', back_populates='training_class', lazy=True)

class Enrollment(db.Model):
    __tablename__ = 'enrollments'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('training_classes.id'), nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    service_start = db.Column(db.Date, nullable=True)
    service_end = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    student = db.relationship('Student', back_populates='enrollments')
    training_class = db.relationship('TrainingClass', back_populates='enrollments')
    creator = db.relationship('User', foreign_keys=[created_by])
    payments = db.relationship('Payment', back_populates='enrollment', lazy=True)
    works = db.relationship('Work', back_populates='enrollment', lazy=True)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    pay_type = db.Column(db.String(20), nullable=False)
    pay_method = db.Column(db.String(20), nullable=False)
    pay_time = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    enrollment = db.relationship('Enrollment', back_populates='payments')
    recorder = db.relationship('User', foreign_keys=[recorded_by])

class Work(db.Model):
    __tablename__ = 'works'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('enrollments.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    file_url = db.Column(db.String(500), nullable=True)   # 外部链接（兼容旧数据）
    file_path = db.Column(db.String(500), nullable=True)  # 本地上传文件相对 static 目录的路径
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='submitted', nullable=False)

    student = db.relationship('Student', foreign_keys=[student_id])
    enrollment = db.relationship('Enrollment', back_populates='works')
    reviews = db.relationship('WorkReview', back_populates='work', lazy=True)

class WorkReview(db.Model):
    __tablename__ = 'work_reviews'
    id = db.Column(db.Integer, primary_key=True)
    work_id = db.Column(db.Integer, db.ForeignKey('works.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    review_time = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='done', nullable=False)

    work = db.relationship('Work', back_populates='reviews')
    teacher = db.relationship('User', foreign_keys=[teacher_id])
