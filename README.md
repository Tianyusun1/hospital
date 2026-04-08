# 摄影机构学员管理系统

基于 Python Flask 的摄影机构学员管理系统，适用于摄影培训机构的日常业务管理。

## 项目概述

本系统基于信息管理与信息系统专业知识，针对摄影机构学员管理低效的问题，设计并实现了一套集学员档案、课程班级、报名缴费、作品管理、风险审计于一体的信息化解决方案。

## 技术栈

- **后端框架**：Python Flask
- **ORM**：Flask-SQLAlchemy
- **前端**：Jinja2 模板 + 原生 HTML/CSS/JS
- **安全**：CSRFProtect、RBAC 角色权限、SysLog 审计
- **数据库**：MySQL（pymysql）

## 快速开始

### 1. 安装依赖

```bash
pip install flask flask-sqlalchemy flask-wtf pymysql werkzeug
```

### 2. 配置数据库

编辑 `config.py`，修改 MySQL 连接信息：

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:password@localhost/photo_sys'
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 启动系统

```bash
python run.py
```

访问 http://localhost:5000

## 演示账号

| 账号 | 密码 | 角色 | 权限说明 |
|------|------|------|---------|
| admin | 123456 | 超级管理员 | 全功能 + 审计/用户管理 |
| staff | 123456 | 教务/前台 | 学员档案、报名缴费、课程班级 |
| teacher | 123456 | 教师 | 查看授课班级、点评作品 |
| student | 123456 | 学员（李同学） | 查看报名/课表、提交/查看作品 |

## 系统功能

### 1. RBAC 权限管理
- **admin**：全权限，含用户审核、系统审计
- **staff**：学员档案 CRUD、课程班级、报名缴费
- **teacher**：查看授课班级/学员、点评学员作品
- **student**：个人报名/课表查看、提交作品、查看点评

### 2. 学员档案管理
- 学员信息录入（姓名、手机、身份证、地址）
- 支持关联登录账号（学员端自助查看）
- 学员详情：报名记录、缴费历史、提交作品

### 3. 课程与班级管理
- 课程 CRUD（名称、学费、课时）
- 班级 CRUD（班次编号、分配教师、开课/结束日期）
- 班级学员名单查看

### 4. 报名与缴费管理
- 报名创建/状态变更（在读/待付/退班/完成）
- 缴费流水录入（定金/尾款/退款，现金/微信/支付宝/转账）

### 5. 作品管理
- 学员端提交作品（标题、描述）
- **本地文件上传**：支持 jpg/jpeg/png/webp 格式，最大 5 MB，保存到 `app/static/uploads/`
- 教师端点评作品（评分、评语）
- 作品截止提醒（24小时内到期预警）
- **软删除**：删除作品保留审计记录，同时删除磁盘文件；已有点评的作品学员端禁止删除

### 6. 学员自助注册与审核
- 学员可在 `/register` 自助注册账号
- 注册后状态为 `pending`，无法使用核心功能
- 管理员在 `/admin/users/review` 后台审核（通过/拒绝）
- 登录拦截：`pending`/`rejected` 用户无法进入系统
- 注册/审核动作全部写入审计日志

### 6. 提醒系统
- 作品即将截止提醒（Dashboard 黄色横幅）
- 作品已逾期提醒（Dashboard 红色横幅）
- 管理员风险操作告警（24小时高风险操作统计）

### 7. 审计与风控
- 所有关键操作写入 SysLog（报名/缴费/作品/点评/用户管理）
- 非工作时间操作自动标记 risk_level=1（警告）
- 审计日志可按操作人、日期、风险等级筛选

## 项目结构

```
hospital/
├── app/
│   ├── __init__.py          # 应用工厂，注册蓝图
│   ├── extensions.py        # db 扩展
│   ├── models/
│   │   ├── user.py          # User, Role
│   │   ├── photography.py   # Student, Course, TrainingClass,
│   │   │                    # Enrollment, Payment, Work, WorkReview
│   │   └── log.py           # SysLog
│   ├── routes/
│   │   ├── auth.py          # 登录/登出/注册
│   │   ├── admin.py         # 用户管理/审计日志
│   │   ├── student.py       # 学员/报名/缴费
│   │   ├── course.py        # 课程/班级
│   │   └── work.py          # 作品/点评/提醒
│   ├── templates/
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── student/index.html
│   │   ├── course/index.html
│   │   ├── work/index.html
│   │   └── admin/
│   │       ├── review_users.html
│   │       ├── audit.html
│   │       └── statistics.html
│   └── utils/
│       ├── decorators.py    # login_required, admin_required, roles_required
│       └── security.py      # check_operation_risk
├── config.py                # 数据库配置
├── init_db.py               # 初始化数据库 + 示例数据
├── run.py                   # 应用入口
├── test_system.py           # 系统功能测试
└── docs/                    # 项目文档
    ├── requirements.md      # 需求说明
    ├── er_diagram.md        # ER 图与表结构
    ├── api_docs.md          # 接口说明
    ├── demo_accounts.md     # 演示账号说明
    └── thesis-mapping.md    # 论文功能映射说明
```

## 数据模型关系

```
Role (1) ←→ (N) User
User (1) ←→ (N) Student [user_account]
User (1) ←→ (N) TrainingClass [teacher]
Course (1) ←→ (N) TrainingClass
TrainingClass (1) ←→ (N) Enrollment
Student (1) ←→ (N) Enrollment
Enrollment (1) ←→ (N) Payment
Enrollment (1) ←→ (N) Work
Student (1) ←→ (N) Work
Work (1) ←→ (N) WorkReview
User (1) ←→ (N) WorkReview [teacher]
```

## 安全特性

- **CSRF 保护**：所有 POST 请求需携带 `X-CSRFToken` 请求头
- **密码哈希**：Werkzeug PBKDF2 哈希存储
- **登录防爆破**：连续失败 5 次自动锁定账号
- **RBAC 权限**：装饰器级别接口权限控制
- **XSS 防护**：Jinja2 模板自动转义 + 前端 escapeHtml
- **操作审计**：所有敏感操作记录 SysLog，含风险等级标注
