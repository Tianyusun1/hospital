# 摄影机构学员管理系统

**基于 Python 的摄影机构学员管理系统设计与实现**  
皖江工学院本科毕业设计（论文）— 信息管理与信息系统专业

---

## 项目简介

本项目是一套面向小微摄影机构的学员全生命周期管理系统，采用 **Flask + SQLAlchemy + MySQL + Jinja2** 技术栈实现。系统从学员建档、课程班级管理、报名缴费、作品提交与点评，到审计日志与风险预警，覆盖摄影机构日常运营的完整业务闭环。

---

## 功能模块

| 模块 | 说明 | 相关角色 |
|-----|------|---------|
| 用户认证与权限 | 注册审核、登录防爆破、账号锁定、四级 RBAC | 所有角色 |
| 学员管理 | 学员建档（姓名/手机/身份证/地址）、信息维护 | admin / staff |
| 课程管理 | 课程信息（名称/价格/时长）的增删改查 | admin / staff |
| 班级管理 | 班次（编号/教师/开班结班日期/容量）的增删改查 | admin / staff |
| 报名管理 | 学员报名班级、服务周期跟踪、状态流转 | admin / staff |
| 缴费管理 | 定金/尾款/退款记录，多种支付方式 | admin / staff |
| 作品管理 | 学员提交作品（标题/链接/截止日期）、教师在线点评评分 | student / teacher |
| 作品提醒 | 截止 24 小时预警（warning）、逾期告警（danger） | 所有角色 |
| 系统审计 | 全业务操作写入 SysLog，支持按操作人/时间/风险等级筛选 | admin |
| 风险告警 | 非工作时间操作自动标记，管理员首页 24 小时实时告警 | admin |

---

## 角色说明

| 角色 | 标识 | 权限范围 |
|-----|------|---------|
| 超级管理员 | `admin` | 全部功能 + 用户审核 + 系统审计 |
| 教务/前台 | `staff` | 学员档案、报名、缴费、课程班级 |
| 教师 | `teacher` | 查看课程班级、作品点评 |
| 学员 | `student` | 查看本人档案、提交作品、查看点评 |

---

## 技术架构

```
前端：HTML5 + CSS3 + 原生 JavaScript（Jinja2 模板渲染）
后端：Python 3.x + Flask 蓝图架构
ORM：SQLAlchemy（Flask-SQLAlchemy）
数据库：MySQL 8.x（数据库名：photo_sys）
安全：Flask-WTF CSRFProtect（全局 CSRF 防护）+ 密码哈希（Werkzeug）
```

---

## 快速开始

### 环境要求

- Python 3.8+
- MySQL 8.0+

### 安装依赖

```bash
pip install flask flask-sqlalchemy flask-wtf pymysql werkzeug
```

### 配置数据库

修改 `config.py` 中的数据库连接信息（或通过环境变量 `SECRET_KEY` / `DATABASE_URL` 配置）：

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:你的密码@localhost/photo_sys'
```

### 初始化数据库

```bash
python init_db.py
```

初始化后生成以下演示账号（密码均为 `123456`）：

| 账号 | 角色 | 说明 |
|-----|------|------|
| `admin` | 超级管理员 | 全功能访问 |
| `staff` | 教务/前台 | 学员档案、报名缴费 |
| `teacher` | 教师 | 课程班级、作品点评 |
| `student` | 学员 | 个人档案、作品提交 |

### 启动系统

```bash
python run.py
```

访问 http://localhost:5000

---

## 项目结构

```
.
├── app/
│   ├── __init__.py          # Flask 工厂函数，注册蓝图
│   ├── extensions.py        # SQLAlchemy 实例
│   ├── models/
│   │   ├── user.py          # User, Role 模型
│   │   ├── photography.py   # Student, Course, TrainingClass,
│   │   │                    # Enrollment, Payment, Work, WorkReview
│   │   └── log.py           # SysLog 审计日志模型
│   ├── routes/
│   │   ├── auth.py          # 认证蓝图（登录/注册/退出）
│   │   ├── student.py       # 学员、报名、缴费蓝图
│   │   ├── course.py        # 课程、班级蓝图
│   │   ├── work.py          # 作品、点评蓝图
│   │   └── admin.py         # 管理员蓝图（用户管理/审计）
│   ├── templates/           # Jinja2 HTML 模板
│   └── utils/
│       ├── decorators.py    # 权限装饰器（login_required, roles_required）
│       └── security.py      # 风控工具（工作时间检测、风险等级）
├── config.py                # 应用配置
├── init_db.py               # 数据库初始化脚本（含演示数据）
├── run.py                   # 启动入口
├── test_system.py           # 功能验证脚本
└── docs/
    └── thesis-mapping.md    # 开题任务书 → 系统实现映射文档
```

---

## 论文相关文档

详见 [`docs/thesis-mapping.md`](docs/thesis-mapping.md)，包含：

- 开题任务书各条目 → 现有系统功能/代码的完整映射
- ER 图数据关系说明
- 进度安排 → 代码模块对应关系
- 待补齐交付件清单（需求规格说明书、系统设计说明书、ER图、DFD、测试报告、用户手册、答辩PPT）
- 代码改进建议

---

*皖江工学院 · 信息管理与信息系统专业 · 220550222 费泽耀*
