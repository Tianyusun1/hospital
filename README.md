# 摄影机构学员管理系统

**基于 Python Flask 的摄影机构学员管理系统设计与实现**

皖江工学院本科毕业设计（论文）— 信息管理与信息系统专业

> 本分支整合自 #2（文档/测试）、#3（完整系统改造）、#4（上传与注册审核）三个分支。

---

## 功能模块

| 模块 | 说明 | 相关角色 |
|-----|------|---------|
| 用户认证与权限 | 学员自助注册→管理员审核→批准/拒绝、登录防爆破、账号锁定、四级 RBAC | 所有角色 |
| 学员管理 | 学员建档（姓名/手机/身份证/地址）、信息维护 | admin / staff |
| 课程管理 | 课程信息（名称/价格/时长）的增删改查 | admin / staff |
| 班级管理 | 班次（编号/教师/开班结班日期/容量）的增删改查 | admin / staff |
| 报名管理 | 学员报名班级、服务周期跟踪、状态流转 | admin / staff |
| 缴费管理 | 定金/尾款/退款记录，多种支付方式 | admin / staff |
| 作品管理 | 学员本地上传图片（jpg/jpeg/png/webp，≤5 MB）、软删除（保留审计）、教师在线点评评分 | student / teacher / admin |
| 作品提醒 | 截止 24 小时预警（warning）、逾期告警（danger） | 所有角色 |
| 数据统计 | 在读学员数、活跃报名数、待审作品数、24 小时风险操作数、课程报名趋势 | admin |
| 系统审计 | 全业务操作写入 SysLog，支持按操作人/时间/风险等级筛选 | admin |
| 风险告警 | 非工作时间操作自动标记，管理员首页 24 小时实时告警 | admin |

---

## 角色说明

| 角色 | 标识 | 权限范围 |
|-----|------|---------|
| 超级管理员 | `admin` | 全部功能 + 用户审核 + 系统审计 + 统计大屏 |
| 教务/前台 | `staff` | 学员档案、报名、缴费、课程班级 |
| 教师 | `teacher` | 查看课程班级、作品点评 |
| 学员 | `student` | 查看本人档案、上传提交作品、查看点评、删除自己未被点评的作品 |

---

## 技术架构

- **后端**：Python 3.x + Flask 蓝图架构
- **ORM**：SQLAlchemy（Flask-SQLAlchemy）
- **数据库**：MySQL 8.x（数据库名：photo_sys）
- **前端**：HTML5 + CSS3 + 原生 JavaScript（Jinja2 模板渲染）
- **安全**：Flask-WTF CSRFProtect + 密码哈希（Werkzeug）
- **文件上传**：保存至 `app/static/uploads/`，安全文件名 + UUID 前缀

---

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

脚本自动创建所有表、写入四个演示角色和账号、插入示例学员/课程/班级/报名/缴费/作品数据。

### 4. 启动系统

```bash
python run.py
```

访问 http://localhost:5000

---

## 演示账号

| 账号 | 密码 | 角色 | 权限说明 |
|------|------|------|---------|
| `admin` | `123456` | 超级管理员 | 全功能 + 用户审核 + 审计日志 + 数据统计 |
| `staff` | `123456` | 教务/前台 | 学员档案、报名缴费、课程班级 |
| `teacher` | `123456` | 教师 | 查看授课班级/学员、点评作品 |
| `student` | `123456` | 学员（李同学） | 查看报名/课表、上传/查看作品 |

> 学员也可通过 `/register` 页面自助注册，注册后状态为 `pending`，  
> 必须由管理员在「用户管理」→「待审核」页面审核通过后才能登录。

---

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
│   │   ├── auth.py          # 登录/登出/注册（含自助注册待审核）
│   │   ├── admin.py         # 用户管理/审计日志/数据统计
│   │   ├── student.py       # 学员/报名/缴费
│   │   ├── course.py        # 课程/班级
│   │   └── work.py          # 作品上传/点评/提醒/软删除
│   ├── static/
│   │   └── uploads/         # 学员上传的作品文件（系统自动创建）
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
├── docs/
│   ├── requirements.md      # 需求说明
│   ├── er_diagram.md        # ER 图与表结构
│   ├── api_docs.md          # 接口说明
│   ├── demo_accounts.md     # 演示账号说明
│   └── thesis-mapping.md    # 论文章节与功能映射
├── config.py                # 数据库与文件上传配置
├── init_db.py               # 初始化数据库 + 示例数据
├── run.py                   # 应用入口
└── test_system.py           # 系统功能测试
```

---

## 数据模型关系

```
Role (1) <-> (N) User
User (1) <-> (N) Student [user_account]
User (1) <-> (N) TrainingClass [teacher]
Course (1) <-> (N) TrainingClass
TrainingClass (1) <-> (N) Enrollment
Student (1) <-> (N) Enrollment
Enrollment (1) <-> (N) Payment
Enrollment (1) <-> (N) Work
Student (1) <-> (N) Work
Work (1) <-> (N) WorkReview
User (1) <-> (N) WorkReview [teacher]
```

---

## 安全特性

- **CSRF 保护**：所有 POST 请求需携带 `X-CSRFToken` 请求头
- **密码哈希**：Werkzeug PBKDF2 哈希存储
- **登录防爆破**：连续失败 5 次自动锁定账号
- **注册审核**：学员自助注册后状态为 `pending`，管理员审核后方可登录
- **RBAC 权限**：装饰器级别接口权限控制
- **文件安全**：安全文件名 + UUID 前缀 + 扩展名白名单（jpg/jpeg/png/webp）+ 大小限制（5 MB）
- **软删除审计**：作品删除仅标记 `is_deleted=True`，磁盘文件同步删除，操作全部写入 SysLog
- **操作审计**：所有敏感操作记录 SysLog，含风险等级标注

---

## 整合来源

| PR | 分支 | 内容 |
|-----|------|------|
| #2 | `copilot/update-docs-thesis-mapping` | test_system.py 修复、thesis-mapping 文档、README 更新 |
| #3 | `copilot/complete-student-management-system` | 统计页面、docs 文档集、admin 统计 API、模板修复 |
| #4 | `copilot/update-upload-management-and-registration` | 作品本地上传、学员自助注册待审核 |
