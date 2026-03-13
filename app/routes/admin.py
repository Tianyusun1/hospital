# 文件位置：app/routes/admin.py
from flask import Blueprint, request, jsonify, render_template
from app.extensions import db
from app.models.user import User
from app.models.equipment import BorrowRecord  # 确保导入审计日志模型
from app.utils.decorators import admin_required

# 创建名为 admin 的蓝图，并为其下所有路由统一添加 /admin 前缀
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# --- 1. 用户审核页面 (前端界面) ---
@admin_bp.route('/users/review', methods=['GET'])
@admin_required  # 仅限管理员访问
def review_page():
    return render_template('admin/review_users.html')


# --- 2. API：获取所有“待审核”状态的用户列表 ---
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


# --- 3. API：处理用户审核动作 (通过 或 拒绝) ---
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

    # 修改用户状态
    if action == 'approve':
        user.status = 'approved'
        msg = f'已通过 {user.real_name} 的入网申请'
    else:
        user.status = 'rejected'
        msg = f'已拒绝 {user.real_name} 的入网申请'

    db.session.commit()
    return jsonify({'code': 200, 'msg': msg})


# --- 4. 审计日志页面 (新增) ---
@admin_bp.route('/audit', methods=['GET'])
@admin_required
def audit_page():
    """展示设备借还审计日志界面"""
    return render_template('admin/audit.html')


# --- 5. API：获取全局借还审计日志 (新增) ---
@admin_bp.route('/api/audit/list', methods=['GET'])
@admin_required
def get_audit_logs():
    """获取所有设备的借还历史记录"""
    # 按照借出时间倒序排列
    records = BorrowRecord.query.order_by(BorrowRecord.borrow_time.desc()).all()

    log_list = []
    for r in records:
        log_list.append({
            'id': r.id,
            'equipment_name': r.equipment.name,
            'serial_number': r.equipment.serial_number,
            'user_name': r.user.real_name,
            'department': r.user.department,
            'borrow_time': r.borrow_time.strftime('%Y-%m-%d %H:%M:%S'),
            'return_time': r.return_time.strftime('%Y-%m-%d %H:%M:%S') if r.return_time else '尚未归还',
            'status': '借用中' if r.status == 'borrowing' else '已归还'
        })

    return jsonify({'code': 200, 'data': log_list})