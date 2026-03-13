# 文件位置：app/routes/auth.py
from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.user import User, Role
from app.extensions import db

auth_bp = Blueprint('auth', __name__)


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

    user = User.query.filter_by(username=username).first()

    if user is None:
        return jsonify({'code': 401, 'msg': '该工号不存在，请先注册'})

    # 【新增拦截逻辑】检查账号状态
    if user.status == 'pending':
        return jsonify({'code': 403, 'msg': '账号正在等待管理员审核，请耐心等待'})
    elif user.status == 'rejected':
        return jsonify({'code': 403, 'msg': '账号审核未通过，请联系信息科'})

    # 验证密码
    if check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['username'] = user.username
        session['real_name'] = user.real_name  # 存入真实姓名
        session['role_id'] = user.role_id
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

    # 基础校验
    if not all([username, password, real_name, department]):
        return jsonify({'code': 400, 'msg': '请填写所有必填项'})

    # 检查工号是否已被注册
    if User.query.filter_by(username=username).first():
        return jsonify({'code': 400, 'msg': '该工号已注册，请直接登录或联系管理员'})

    # 获取默认的普通用户角色 (如果数据库没有 user 角色，需要先创建)
    default_role = Role.query.filter_by(role_name='user').first()
    if not default_role:
        default_role = Role(role_name='user', description='普通医护人员')
        db.session.add(default_role)
        db.session.commit()

    # 创建新用户，状态默认为 'pending' (待审核)
    hashed_pw = generate_password_hash(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        real_name=real_name,
        department=department,
        phone=phone,
        role_id=default_role.id,
        status='pending'  # 新注册用户待审核
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '注册提交成功，请等待管理员审核'})


# ================= 其他 =================
@auth_bp.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'code': 200, 'msg': '已安全退出'})


# 【关键修改】：将原来的硬编码返回改为了渲染 dashboard.html 模板
@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))

    # 渲染真实的 HTML 模板，并把用户的角色和姓名传给前端
    return render_template('dashboard.html',
                           real_name=session.get('real_name', session.get('username')),
                           role_id=session.get('role_id'))