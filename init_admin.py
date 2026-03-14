# 文件位置：根目录 / init_admin.py
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 1. 先检查是否已经有角色，没有则创建
    admin_role = Role.query.filter_by(role_name='admin').first()
    if not admin_role:
        admin_role = Role(role_name='admin', description='系统管理员')
        db.session.add(admin_role)
        db.session.commit()  # 提交生成 ID

    # 2. 检查是否已经有 admin 用户，没有则创建
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        hashed_password = generate_password_hash('123456')  # 初始化密码为 123456

        # 【核心修复】：补全了 User 模型要求的必填字段，并将状态设为 approved（已审核通过）
        admin_user = User(
            username='admin',
            password_hash=hashed_password,
            real_name='系统超级管理员',
            department='信息科',
            phone='13800000000',
            status='approved',
            role_id=admin_role.id
        )
        db.session.add(admin_user)
        db.session.commit()
        print("✅ 管理员账号初始化成功！账号: admin, 密码: 123456")
    else:
        print("⚠️ 管理员账号已存在，无需重复创建。")