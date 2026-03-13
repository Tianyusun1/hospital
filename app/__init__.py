# 文件位置：app/__init__.py
from flask import Flask
from config import Config
from app.extensions import db
from flask_wtf.csrf import CSRFProtect  # 【核心新增】：导入 CSRF 保护工具

# 实例化 CSRF 保护工具
csrf = CSRFProtect()


def create_app():
    # template_folder 和 static_folder 明确指向，确保资源加载正确
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # 加载配置 (包含数据库 URI, SECRET_KEY 等)
    app.config.from_object(Config)

    # ==========================
    # 初始化扩展 (Extensions)
    # ==========================
    db.init_app(app)

    # 【核心新增】：启用全局 CSRF 防护。
    # 启用后，前端所有 POST 请求需要在 Header 或表单中携带 X-CSRFToken。
    csrf.init_app(app)

    # ==========================
    # 注册蓝图 (Blueprints)
    # ==========================
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.equipment import equipment_bp
    app.register_blueprint(equipment_bp)

    # ==========================
    # 根路由：自动跳转至登录页
    # ==========================
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login_page'))

    return app