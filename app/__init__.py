from flask import Flask
from config import Config
from app.extensions import db
from flask_wtf.csrf import CSRFProtect
import os

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    db.init_app(app)
    csrf.init_app(app)

    # 确保文件上传目录存在
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.student import student_bp
    app.register_blueprint(student_bp)

    from app.routes.course import course_bp
    app.register_blueprint(course_bp)

    from app.routes.work import work_bp
    app.register_blueprint(work_bp)

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login_page'))

    return app
