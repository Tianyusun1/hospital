import os
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.log import SysLog
from app.models.photography import Student, Course, TrainingClass, Enrollment, Payment, Work, WorkReview

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("数据库表初始化完成")
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
