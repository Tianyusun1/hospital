# 文件位置：根目录 / run.py
from app import create_app
from app.extensions import db

# 引入模型，确保 create_all() 能找到它们
from app.models.user import Role, User

app = create_app()

if __name__ == '__main__':
    # 借助应用上下文，在启动前检查并创建数据库表
    with app.app_context():
        # 这行代码会在你的 MySQL 'medical_sys' 库中自动生成 roles 和 users 表
        db.create_all() 
        print("✅ 数据库表初始化完成 (如果表已存在则忽略)")

    # 启动 Flask 服务
    app.run(debug=True, port=5000)