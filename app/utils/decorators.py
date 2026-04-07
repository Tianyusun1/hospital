from functools import wraps
from flask import session, jsonify, redirect, url_for, request
from app.models.user import Role


def login_required(f):
    """基础登录检查拦截器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 401, 'msg': '请先登录'})
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """RBAC 核心拦截器：仅限超级管理员访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 401, 'msg': '请先登录'})
            return redirect(url_for('auth.login_page'))

        role_id = session.get('role_id')
        role = Role.query.get(role_id)

        if not role or role.role_name != 'admin':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 403, 'msg': '越权操作拦截：仅超级管理员可执行此操作！'})
            else:
                return "<h2>403 权限拒绝</h2><p>抱歉，您没有访问此页面的权限。此行为已被记录。</p>", 403

        return f(*args, **kwargs)
    return decorated_function


def roles_required(*allowed_roles):
    """允许指定的多个角色访问"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 401, 'msg': '请先登录'})
                return redirect(url_for('auth.login_page'))

            role_id = session.get('role_id')
            role = Role.query.get(role_id)

            if not role or role.role_name not in allowed_roles:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'code': 403, 'msg': f'权限不足：需要 {"/".join(allowed_roles)} 角色！'})
                else:
                    return "<h2>403 权限拒绝</h2><p>抱歉，您没有对应的角色权限。此行为已被记录。</p>", 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
