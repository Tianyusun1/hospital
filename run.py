# 修改后的 run.py
from app import create_app
from app.extensions import db

# 引入所有模型，确保 create_all() 能找到它们
from app.models.user import Role, User
from app.models.equipment import Equipment  # 新增：确保设备表能被创建

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("✅ 数据库表初始化完成")

    app.run(debug=True, port=5000)