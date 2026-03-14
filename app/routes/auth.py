# 文件位置：app/routes/auth.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.user import User, Role
from app.models.log import SysLog
from app.extensions import db
from app.utils.security import check_operation_risk
# --- 【核心新增】：导入 joinedload 优化关联查询 ---
from sqlalchemy.orm import joinedload

auth_bp = Blueprint('auth', __name__)


# --- 【核心新增】：获取真实 IP 辅助函数 ---
def get_real_ip():
    """获取客户端真实 IP 地址，防代理穿透"""
    return request.headers.get('X-Forwarded-For', request.remote_addr)


# ================= 登录相关 =================
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

    # 【性能优化】：使用 joinedload 提前查出 Role 表，避免访问 user.role 时触发二次查询
    user = User.query.options(joinedload(User.role)).filter_by(username=username).first()

    if user is None:
        return jsonify({'code': 401, 'msg': '该工号不存在，请先注册'})

    # 检查账号状态 (RBAC 核心逻辑)
    if user.status == 'pending':
        return jsonify({'code': 403, 'msg': '账号正在等待管理员审核，请耐心等待'})
    elif user.status == 'rejected':
        return jsonify({'code': 403, 'msg': '账号审核未通过，请联系信息科'})

    # 验证密码
    if check_password_hash(user.password_hash, password):
        # 1. 设置 Session 保持登录状态
        session['user_id'] = user.id
        session['username'] = user.username
        session['real_name'] = user.real_name
        session['role_id'] = user.role_id
        # 【核心修复】：将会话中存入 role_name，配合后续通过字符串判断管理员权限的安全策略
        session['role_name'] = user.role.role_name if user.role else 'user'

        # --- 进行行为安全检测 ---
        risk_level, risk_msg = check_operation_risk()

        # 2. 记录登录审计日志（带风险判定）
        new_log = SysLog(
            user_id=user.id,
            action='登录',
            target=f"工号: {user.username}",
            ip_address=get_real_ip(),  # 【安全修复】：使用真实 IP
            risk_level=risk_level,
            risk_msg=risk_msg
        )
        db.session.add(new_log)
        db.session.commit()

        return jsonify({'code': 200, 'msg': '登录成功'})
    else:
        return jsonify({'code': 401, 'msg': '密码错误'})


# ================= 注册相关 =================
@auth_bp.route('/register', methods=['GET'])
def register_page():
    return render_template('register.html')


@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    real_name = data.get('real_name')
    department = data.get('department')
    phone = data.get('phone')

    # 简单的输入验证
    if not all([username, password, real_name, department]):
        return jsonify({'code': 400, 'msg': '请填写所有必填项'})

    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'msg': '该工号已注册，请直接登录或联系管理员'})

    default_role = Role.query.filter_by(role_name='user').first()
    if not default_role:
        default_role = Role(role_name='user', description='普通医护人员')
        db.session.add(default_role)
        db.session.commit()

    hashed_pw = generate_password_hash(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        real_name=real_name,
        department=department,
        phone=phone,
        role_id=default_role.id,
        status='pending'
    )

    # 【逻辑修复】：先 commit() 将用户存入数据库，这样才能拿到自增的 new_user.id
    db.session.add(new_user)
    db.session.commit()

    # 记录注册行为日志（带上刚刚生成的用户 ID）
    r_risk_level, r_risk_msg = check_operation_risk()
    reg_log = SysLog(
        user_id=new_user.id,  # 【核心修复】：精准绑定操作人为刚注册的用户
        action='用户注册',
        target=f"工号: {username}",
        ip_address=get_real_ip(),  # 【安全修复】：使用真实 IP
        risk_level=r_risk_level,
        risk_msg=r_risk_msg
    )
    db.session.add(reg_log)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '注册提交成功，请等待管理员审核'})


# ================= 其他 =================
@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    if 'user_id' in session:
        # 退出也进行时间风险检测
        l_risk_level, l_risk_msg = check_operation_risk()
        logout_log = SysLog(
            user_id=session['user_id'],
            action='退出',
            target=f"工号: {session['username']}",
            ip_address=get_real_ip(),  # 【安全修复】：使用真实 IP
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
                           role_name=session.get('role_name'))  # 模板中可能也需要用到角色名