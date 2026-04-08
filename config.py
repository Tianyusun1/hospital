# 文件位置：根目录 / config.py
import os

# 项目根目录绝对路径
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    # 用于 Session 和加密的安全密钥，生产环境应使用环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_super_secret_key_888'

    # MySQL 数据库连接配置 (请把 root:123456 换成你本机的数据库账号密码)
    # 格式: mysql+pymysql://用户名:密码@主机地址:端口/数据库名
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/photo_sys'

    # 关闭对模型修改的跟踪，提升性能
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ===== 文件上传配置 =====
    # 上传目录（保存在 app/static/uploads，方便 Flask 静态文件直接访问）
    UPLOAD_FOLDER = os.path.join(_BASE_DIR, 'app', 'static', 'uploads')

    # 允许上传的图片扩展名（小写）
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}

    # 单文件最大体积：5 MB；Flask 使用 MAX_CONTENT_LENGTH 在请求层面拦截超大请求
    MAX_UPLOAD_SIZE = 5 * 1024 * 1024        # 5 MB（应用层校验）
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024     # 6 MB（Flask 请求层硬限制，略大于应用层限制）