# 文件位置：app/__init__.py
from flask import Flask
from config import Config
from app.extensions import db

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(Config)
    db.init_app(app)

    # ==========================
    # 注册蓝图 (Blueprints)
    # ==========================
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    # 【新增】：导入并注册医疗设备管理蓝图
    from app.routes.equipment import equipment_bp
    app.register_blueprint(equipment_bp)

    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login_page'))

    return app