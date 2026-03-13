# 文件位置：app / utils / decorators.py
from functools import wraps
from flask import session, jsonify, redirect, url_for, request
from app.models.user import Role


def admin_required(f):
    """
    RBAC 核心拦截器：仅限管理员访问
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 检查用户是否已登录 (会话校验)
        if 'user_id' not in session:
            # 如果是前端 fetch 发送的 API 请求，返回 JSON 错误
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 401, 'msg': '请先登录'})
            # 如果是浏览器直接访问页面，重定向到登录页
            return redirect(url_for('auth.login_page'))

        # 2. 检查用户角色权限 (后端校验)
        role_id = session.get('role_id')
        role = Role.query.get(role_id)

        # 如果找不到角色，或者角色名不是 'admin'
        if not role or role.role_name != 'admin':
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'code': 403, 'msg': '越权操作拦截：仅管理员可执行此操作！'})
            else:
                return "<h2>403 权限拒绝</h2><p>抱歉，您没有访问此页面的权限。此行为已被记录。</p>", 403

        # 3. 校验通过，放行到目标函数
        return f(*args, **kwargs)

    return decorated_function