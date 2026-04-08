# 文件位置：根目录 / config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # 用于 Session 和加密的安全密钥，生产环境应使用环境变量
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your_super_secret_key_888'

    # MySQL 数据库连接配置 (请把 root:123456 换成你本机的数据库账号密码)
    # 格式: mysql+pymysql://用户名:密码@主机地址:端口/数据库名
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:123456@localhost/photo_sys'

    # 关闭对模型修改的跟踪，提升性能
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 作品文件上传目录（保存到 app/static/uploads/，浏览器可直接访问）
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads')

    # 单文件最大大小：5 MB
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # 允许上传的文件后缀（小写）
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}