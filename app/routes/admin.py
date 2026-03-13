# 文件位置：app/routes/admin.py
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models.user import User
from app.utils.decorators import admin_required

# 创建名为 admin 的蓝图，并为其下所有路由统一添加 /admin 前缀
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# 1. 展示用户审核页面 (前端界面)
@admin_bp.route('/users/review', methods=['GET'])
@admin_required  # 核心！加上这行，非管理员直接被拦截
def review_page():
    return render_template('admin/review_users.html')


# 2. API：获取所有“待审核”状态的用户列表
@admin_bp.route('/api/users/pending', methods=['GET'])
@admin_required
def get_pending_users():
    # 查询数据库中 status 为 'pending' 的用户
    users = User.query.filter_by(status='pending').order_by(User.created_at.desc()).all()

    user_list = []
    for u in users:
        user_list.append({
            'id': u.id,
            'username': u.username,
            'real_name': u.real_name,
            'department': u.department,
            'phone': u.phone or '未留存',
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M')
        })
    return jsonify({'code': 200, 'data': user_list})


# 3. API：处理审核动作 (通过 或 拒绝)
@admin_bp.route('/api/users/do_review', methods=['POST'])
@admin_required
def do_review():
    data = request.get_json()
    user_id = data.get('user_id')
    action = data.get('action')  # 预期值为 'approve' 或 'reject'

    if not user_id or action not in ['approve', 'reject']:
        return jsonify({'code': 400, 'msg': '参数不合法'})

    user = User.query.get(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '找不到该用户'})

    if user.status != 'pending':
        return jsonify({'code': 400, 'msg': '该用户已处理过，请勿重复操作'})

    # 根据前端传来的动作修改状态
    if action == 'approve':
        user.status = 'approved'
        msg = f'已通过 {user.real_name} 的入网申请'
    else:
        user.status = 'rejected'
        msg = f'已拒绝 {user.real_name} 的入网申请'

    db.session.commit()
    return jsonify({'code': 200, 'msg': msg})