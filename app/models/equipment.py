# 文件位置：app/routes/equipment.py
from flask import Blueprint, request, jsonify, render_template, session, redirect, url_for
from app.extensions import db
from app.models.equipment import Equipment
from app.utils.decorators import admin_required

# 创建医疗设备管理的蓝图
equipment_bp = Blueprint('equipment', __name__, url_prefix='/equipment')


# 1. 展示设备管理页面 (前端界面)
@equipment_bp.route('/', methods=['GET'])
def equipment_page():
    # 只要登录了就可以看页面，前端会根据 role_id 决定显不显示“新增”按钮
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('equipment/index.html', role_id=session.get('role_id'))


# 2. API：获取设备列表 (所有人均可查看)
@equipment_bp.route('/api/list', methods=['GET'])
def get_equipment_list():
    if 'user_id' not in session:
        return jsonify({'code': 401, 'msg': '请先登录'})

    # 按录入时间倒序查询所有设备
    equipments = Equipment.query.order_by(Equipment.created_at.desc()).all()

    data = []
    for eq in equipments:
        # 状态字典映射
        status_map = {0: '在库', 1: '已借出', 2: '维修中', 3: '报废'}

        data.append({
            'id': eq.id,
            'name': eq.name,
            'serial_number': eq.serial_number,
            'status_code': eq.status,
            'status_text': status_map.get(eq.status, '未知状态'),
            'added_by': eq.registrar.real_name if eq.registrar else '系统',
            'created_at': eq.created_at.strftime('%Y-%m-%d %H:%M')
        })

    return jsonify({'code': 200, 'data': data})


# 3. API：新增医疗设备 (RBAC拦截：仅限管理员)
@equipment_bp.route('/api/add', methods=['POST'])
@admin_required
def add_equipment():
    data = request.get_json()
    name = data.get('name')
    serial_number = data.get('serial_number')

    if not name or not serial_number:
        return jsonify({'code': 400, 'msg': '设备名称和设备编号不能为空'})

    # 检查设备编号是否在数据库中已存在 (防重复录入)
    existing_eq = Equipment.query.filter_by(serial_number=serial_number).first()
    if existing_eq:
        return jsonify({'code': 400, 'msg': f'录入失败！编号 {serial_number} 已被占用'})

    # 创建新设备实体，默认状态为 0 (在库)
    new_eq = Equipment(
        name=name,
        serial_number=serial_number,
        status=0,
        added_by=session['user_id']  # 记录是哪个管理员录入的
    )

    db.session.add(new_eq)
    db.session.commit()

    return jsonify({'code': 200, 'msg': '新设备录入成功！'})