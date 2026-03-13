# 文件位置：根目录 / init_db.py
import pymysql
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.equipment import Equipment, BorrowRecord  # 引入设备与借还记录模型
from app.models.log import SysLog  # 【核心新增】：引入日志模型，确保审计日志表被创建
from werkzeug.security import generate_password_hash

# ==========================================
# 你的 MySQL 登录信息 (请根据实际情况修改)
# ==========================================
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = '123456'  # 你的数据库密码
DB_NAME = 'medical_sys'


def reset_database():
    print("⏳ 开始重置医疗设备系统数据库结构...")

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
        # 执行重置操作：先删后建，确保模型变更生效
        db.drop_all()
        db.create_all()
        print("✅ 1. 数据库表结构 (含 equipments, borrow_records, sys_logs) 重置成功！")

        # 3. 初始化角色表 (RBAC 基础)
        admin_role = Role(role_name='admin', description='系统管理员')
        user_role = Role(role_name='user', description='普通医护人员')
        db.session.add_all([admin_role, user_role])
        db.session.commit()
        print("✅ 2. 系统角色 (admin, user) 初始化成功。")

        # 4. 初始化超级管理员账号 (设置状态为 approved)
        hashed_pw = generate_password_hash('123456')
        admin_user = User(
            username='admin',
            password_hash=hashed_pw,
            real_name='系统主管',
            department='信息科',
            phone='13800000000',
            status='approved',  # 管理员账号默认通过审核
            role_id=admin_role.id
        )
        db.session.add(admin_user)
        db.session.commit()
        print("✅ 3. 超级管理员账号初始化完毕！(账号: admin, 密码: 123456)")

        # 5. 【核心更新】：初始化包含“规格信息”的测试医疗设备
        eq1 = Equipment(
            name="便携式心电图机",
            serial_number="EKG-2026-001",
            specification="12导联, 内置热敏打印, 支持无线传输",  # 新增规格字段
            status=0,
            added_by=admin_user.id
        )
        eq2 = Equipment(
            name="多参数监护仪",
            serial_number="MON-2026-002",
            specification="12.1寸高清触屏, 含心率/血氧/无创血压监测",  # 新增规格字段
            status=0,
            added_by=admin_user.id
        )
        eq3 = Equipment(
            name="自动体外除颤器 (AED)",
            serial_number="AED-2026-003",
            specification="双相波技术, 智能语音提示",
            status=0,
            added_by=admin_user.id
        )
        db.session.add_all([eq1, eq2, eq3])

        # 6. 【可选】：记录一条系统初始化日志
        init_log = SysLog(
            user_id=admin_user.id,
            action="系统初始化",
            target="数据库重置与基础数据录入",
            ip_address="127.0.0.1"
        )
        db.session.add(init_log)

        db.session.commit()
        print("✅ 4. 测试医疗设备及初始化审计日志已存入。")

    print("\n🎉 数据库重置大功告成，功能图中所有底层架构已就绪！")
    print("👉 请运行 python run.py 启动系统进行测试。")


if __name__ == '__main__':
    reset_database()