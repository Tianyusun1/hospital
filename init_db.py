# 文件位置：根目录 / init_db.py
import pymysql
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.equipment import Equipment  # 【关键新增】：引入设备模型，让系统知道要建这张表
from werkzeug.security import generate_password_hash

# ==========================================
# 你的 MySQL 登录信息
# ==========================================
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = '123456'  # 你的数据库密码
DB_NAME = 'medical_sys'

def reset_database():
    print("⏳ 开始重置数据库结构...")

    # 1. 确保数据库存在
    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ 连接 MySQL 失败，请检查账号密码: {e}")
        return

    # 2. 利用 Flask 上下文重置表结构
    app = create_app()
    with app.app_context():
        # 【关键代码】：先删掉所有的旧表，再根据最新的 model 重新创建
        db.drop_all()
        db.create_all()
        print("✅ 1. 旧表已清理，新表 (包含 equipments 设备表) 已成功创建！")

        # 3. 初始化角色表
        admin_role = Role(role_name='admin', description='系统管理员')
        user_role = Role(role_name='user', description='普通医护人员')
        db.session.add_all([admin_role, user_role])
        db.session.commit()
        print("✅ 2. 角色 (admin, user) 初始化成功。")

        # 4. 初始化超级管理员账号 (填入所有必填的新字段)
        hashed_pw = generate_password_hash('123456')
        admin_user = User(
            username='admin',
            password_hash=hashed_pw,
            real_name='超管',  # 新字段
            department='信息科',  # 新字段
            phone='13800000000',  # 新字段
            status='approved',  # 新字段：管理员直接是"已通过"状态
            role_id=admin_role.id
        )
        db.session.add(admin_user)
        db.session.commit()
        print("✅ 3. 超级管理员账号初始化完毕！(账号: admin, 密码: 123456)")

        # 5. 【新增】：初始化几台测试用的医疗设备
        eq1 = Equipment(name="便携式心电图机", serial_number="EKG-2026-001", status=0, added_by=admin_user.id)
        eq2 = Equipment(name="多参数监护仪", serial_number="MON-2026-002", status=0, added_by=admin_user.id)
        db.session.add_all([eq1, eq2])
        db.session.commit()
        print("✅ 4. 测试医疗设备 (心电图机, 监护仪) 初始化完毕！")

    print("\n🎉 数据库重置大功告成，请重新启动 run.py 测试！")

if __name__ == '__main__':
    reset_database()