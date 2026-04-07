from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.user import User, Role
from app.models.log import SysLog
from app.extensions import db
from app.utils.security import check_operation_risk
from sqlalchemy.orm import joinedload

auth_bp = Blueprint('auth', __name__)


def get_real_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


# ================= 登录 =================

@auth_bp.route('/login', methods=['GET'])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard'))
    return render_template('login.html')


@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'code': 400, 'msg': '账号或密码不能为空'})

    user = User.query.options(joinedload(User.role)).filter_by(username=username).first()

    if user is None:
        return jsonify({'code': 401, 'msg': '该账号不存在，请先注册'})

    if user.is_locked:
        return jsonify({'code': 403, 'msg': '账号因多次输入错误已被安全锁定，请联系管理员解锁'})

    if user.status == 'pending':
        return jsonify({'code': 403, 'msg': '账号正在等待管理员审核，请耐心等待'})
    elif user.status == 'rejected':
        return jsonify({'code': 403, 'msg': '账号审核未通过，请联系管理员'})

    if check_password_hash(user.password_hash, password):
        user.failed_login_attempts = 0
        db.session.commit()

        session['user_id'] = user.id
        session['username'] = user.username
        session['real_name'] = user.real_name
        session['role_id'] = user.role_id
        session['role_name'] = user.role.role_name if user.role else 'student'

        risk_level, risk_msg = check_operation_risk()
        new_log = SysLog(
            user_id=user.id,
            action='登录',
            target=f"账号: {user.username}",
            ip_address=get_real_ip(),
            risk_level=risk_level,
            risk_msg=risk_msg
        )
        db.session.add(new_log)
        db.session.commit()
        return jsonify({'code': 200, 'msg': '登录成功'})
    else:
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.is_locked = True
            db.session.commit()
            return jsonify({'code': 401, 'msg': '密码连续错误5次，账号已被安全锁定！'})
        db.session.commit()
        return jsonify({'code': 401, 'msg': f'密码错误！连续错误5次将锁定，还剩 {5 - user.failed_login_attempts} 次机会'})


# ================= 注册 =================

@auth_bp.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    real_name = data.get('real_name')
    department = data.get('department', '学员')
    phone = data.get('phone')

    # Only 'student' role is allowed for self-registration
    requested_role_name = data.get('role_name', 'student')
    if requested_role_name != 'student':
        requested_role_name = 'student'

    if not all([username, password, real_name]):
        return jsonify({'code': 400, 'msg': '请填写所有必填项'})

    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'msg': '该账号已注册，请直接登录'})

    target_role = Role.query.filter_by(role_name=requested_role_name).first()
    if not target_role:
        target_role = Role(role_name=requested_role_name, description='学员')
        db.session.add(target_role)
        db.session.commit()

    hashed_pw = generate_password_hash(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        real_name=real_name,
        department=department,
        phone=phone,
        role_id=target_role.id,
        status='pending'
    )
    db.session.add(new_user)
    db.session.commit()

    r_risk_level, r_risk_msg = check_operation_risk()
    reg_log = SysLog(
        user_id=new_user.id,
        action='用户注册',
        target=f"账号: {username}, 角色: {requested_role_name}",
        ip_address=get_real_ip(),
        risk_level=r_risk_level,
        risk_msg=r_risk_msg
    )
    db.session.add(reg_log)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '注册提交成功，请等待管理员审核后登录'})


# ================= 退出 & 工作台 =================

@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    if 'user_id' in session:
        l_risk_level, l_risk_msg = check_operation_risk()
        logout_log = SysLog(
            user_id=session['user_id'],
            action='退出',
            target=f"账号: {session['username']}",
            ip_address=get_real_ip(),
            risk_level=l_risk_level,
            risk_msg=l_risk_msg
        )
        db.session.add(logout_log)
        db.session.commit()

    session.clear()
    return jsonify({'code': 200, 'msg': '已安全退出'})


@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('dashboard.html',
                           real_name=session.get('real_name', session.get('username')),
                           role_id=session.get('role_id'),
                           role_name=session.get('role_name'))
