# 文件位置：根目录 / init_db.py
import pymysql
from app import create_app
from app.extensions import db
from app.models.user import Role, User
from app.models.log import SysLog
from app.models.photography import Student, Course, TrainingClass, Enrollment, Payment, Work, WorkReview
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta

DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASS = '123456'
DB_NAME = 'photo_sys'

def reset_database():
    print("开始初始化摄影机构学员管理系统数据库...")

    try:
        conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"连接 MySQL 失败: {e}")
        return

    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("1. 数据库表结构重置成功！")

        admin_role = Role(role_name='admin', description='超级管理员')
        staff_role = Role(role_name='staff', description='教务/前台')
        teacher_role = Role(role_name='teacher', description='教师')
        student_role = Role(role_name='student', description='学员')
        db.session.add_all([admin_role, staff_role, teacher_role, student_role])
        db.session.commit()
        print("2. 系统角色初始化成功。")

        pw = generate_password_hash('123456')
        admin_user = User(username='admin', password_hash=pw, real_name='超级管理员', department='系统管理', phone='13800000000', status='approved', role_id=admin_role.id)
        staff_user = User(username='staff', password_hash=pw, real_name='教务张老师', department='教务处', phone='13800000001', status='approved', role_id=staff_role.id)
        teacher_user = User(username='teacher', password_hash=pw, real_name='摄影王老师', department='摄影教研组', phone='13800000002', status='approved', role_id=teacher_role.id)
        student_user = User(username='student', password_hash=pw, real_name='李同学', department='学员', phone='13800000003', status='approved', role_id=student_role.id)
        # 第二个示例学员账号（approved），用于演示自主注册后审核通过的全流程
        student_user2 = User(username='student2', password_hash=pw, real_name='陈小华', department='学员', phone='13800000004', status='approved', role_id=student_role.id)
        db.session.add_all([admin_user, staff_user, teacher_user, student_user, student_user2])
        db.session.commit()
        print("3. 示例账号初始化完毕！(账号: admin/staff/teacher/student/student2, 密码均为: 123456)")

        course1 = Course(name='人像摄影基础班', description='学习人像摄影构图、光线运用与后期处理', price=2980, duration_weeks=8, status='active')
        course2 = Course(name='风光摄影进阶班', description='掌握风光摄影的拍摄技法与后期调色', price=3580, duration_weeks=10, status='active')
        course3 = Course(name='商业产品摄影班', description='学习商品摄影布光与商业修图技术', price=4200, duration_weeks=12, status='active')
        db.session.add_all([course1, course2, course3])
        db.session.commit()
        print("4. 示例课程录入完毕。")

        class1 = TrainingClass(class_no='RX-2024-01', course_id=course1.id, teacher_id=teacher_user.id, start_date=date(2024, 3, 1), end_date=date(2024, 4, 26), capacity=15, status='open')
        class2 = TrainingClass(class_no='FK-2024-01', course_id=course2.id, teacher_id=teacher_user.id, start_date=date(2024, 4, 1), end_date=date(2024, 6, 10), capacity=12, status='open')
        db.session.add_all([class1, class2])
        db.session.commit()
        print("5. 示例班级录入完毕。")

        stu1 = Student(name='李同学', phone='13900000001', id_card='340000200001010001', address='安徽省芜湖市', user_id=student_user.id, created_by=staff_user.id)
        stu2 = Student(name='王小明', phone='13900000002', id_card='340000200002020002', address='安徽省合肥市', created_by=staff_user.id)
        stu3 = Student(name='赵丽华', phone='13900000003', id_card='340000200003030003', address='安徽省马鞍山市', created_by=staff_user.id)
        stu4 = Student(name='陈小华', phone='13900000004', id_card='340000200004040004', address='安徽省宣城市', user_id=student_user2.id, created_by=staff_user.id)
        db.session.add_all([stu1, stu2, stu3, stu4])
        db.session.commit()
        print("6. 示例学员档案录入完毕。")

        enroll1 = Enrollment(student_id=stu1.id, class_id=class1.id, status='active', service_start=date(2024,3,1), service_end=date(2024,4,26), created_by=staff_user.id)
        enroll2 = Enrollment(student_id=stu2.id, class_id=class1.id, status='active', service_start=date(2024,3,1), service_end=date(2024,4,26), created_by=staff_user.id)
        enroll3 = Enrollment(student_id=stu3.id, class_id=class2.id, status='active', service_start=date(2024,4,1), service_end=date(2024,6,10), created_by=staff_user.id)
        db.session.add_all([enroll1, enroll2, enroll3])
        db.session.commit()
        print("7. 示例报名记录录入完毕。")

        pay1 = Payment(enrollment_id=enroll1.id, amount=1000, pay_type='deposit', pay_method='wechat', notes='定金', recorded_by=staff_user.id)
        pay2 = Payment(enrollment_id=enroll1.id, amount=1980, pay_type='final', pay_method='alipay', notes='尾款', recorded_by=staff_user.id)
        pay3 = Payment(enrollment_id=enroll2.id, amount=2980, pay_type='final', pay_method='cash', notes='全款', recorded_by=staff_user.id)
        db.session.add_all([pay1, pay2, pay3])
        db.session.commit()
        print("8. 示例缴费记录录入完毕。")

        upcoming_deadline = datetime.utcnow() + timedelta(hours=12)
        work1 = Work(student_id=stu1.id, enrollment_id=enroll1.id, title='人像光影练习作品', description='使用自然光拍摄的人像照片', deadline=upcoming_deadline, status='submitted')
        work2 = Work(student_id=stu2.id, enrollment_id=enroll2.id, title='城市街拍练习', description='街头人文摄影练习', deadline=datetime.utcnow() + timedelta(days=3), status='submitted')
        db.session.add_all([work1, work2])
        db.session.commit()
        print("9. 示例作品录入完毕。")

        review1 = WorkReview(work_id=work1.id, teacher_id=teacher_user.id, score=85, comment='构图不错，光线运用有待改进，建议多练习用光技巧。', status='done')
        db.session.add(review1)
        work1.status = 'reviewed'
        db.session.commit()
        print("10. 示例点评录入完毕。")

        init_log = SysLog(user_id=admin_user.id, action='系统初始化', target='摄影机构学员管理系统数据库初始化完成', ip_address='127.0.0.1')
        db.session.add(init_log)
        db.session.commit()
        print("11. 初始化日志写入完毕。")

    print("\n数据库初始化完成！")
    print("演示账号（密码均为 123456）：")
    print("   admin    - 超级管理员")
    print("   staff    - 教务/前台")
    print("   teacher  - 教师")
    print("   student  - 学员（李同学，已审核通过）")
    print("   student2 - 学员（陈小华，已审核通过，可演示注册审核流程）")
    print("\n运行 `python run.py` 启动系统")

if __name__ == '__main__':
    reset_database()
