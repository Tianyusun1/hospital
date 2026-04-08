# 开题任务书 → 系统实现映射文档

**项目**：基于 Python 的摄影机构学员管理系统设计与实现  
**学号**：220550222　**姓名**：费泽耀　**专业**：信息管理与信息系统  
**指导教师**：芮靖　**学校**：皖江工学院

---

## 一、当前系统主题吻合度评估

| 评估维度 | 任务书要求 | 当前实现状态 | 吻合度 |
|---------|-----------|------------|--------|
| 技术栈 | 基于 Python | Flask + SQLAlchemy + Jinja2 | ✅ 完全吻合 |
| 系统主题 | 摄影机构学员管理 | 已完成转型，数据库名 `photo_sys` | ✅ 完全吻合 |
| 学员管理模块 | 学员建档、状态跟踪 | `Student` 模型 + CRUD API 已实现 | ✅ 已实现 |
| 课程班级模块 | 课程/班次管理 | `Course` + `TrainingClass` 模型已实现 | ✅ 已实现 |
| 报名缴费模块 | 报名流程、缴费记录 | `Enrollment` + `Payment` 模型已实现 | ✅ 已实现 |
| 作品流程模块 | 学员作品提交与点评 | `Work` + `WorkReview` 模型已实现 | ✅ 已实现 |
| 服务周期跟踪 | 培训服务周期跟踪 | `service_start/service_end` 字段 + 截止提醒 API | ✅ 已实现 |
| 审计风控模块 | 行为审计与风险预警 | `SysLog` + RBAC 权限体系已实现 | ✅ 已实现 |
| RBAC 权限 | 多角色访问控制 | admin/staff/teacher/student 四角色 | ✅ 已实现 |

> **结论**：当前代码已完成从"医疗设备借还系统"到"摄影机构学员管理系统"的完整转型，
> 各核心功能模块均已对应任务书要求实现。

---

## 二、进度安排 → 代码模块映射

### 第 1–3 周：需求调研，确定系统功能清单

**交付成果**：需求规格说明书（待补齐，见第四节）

**对应已实现功能**：

| 需求功能点 | 对应文件/接口 | 状态 |
|-----------|-------------|------|
| 学员自助注册与管理员审核 | `auth.py` `/api/register` + `/admin/api/users/do_review` | ✅ 已实现 |
| 学员档案增删改查（教务） | `student.py` `/student/api/add/update/list` | ✅ 已实现 |
| 学员查看本人信息 | `student.py` `/student/api/my_info` | ✅ 已实现 |
| 多角色登录与权限控制 | `auth.py` + `decorators.py` + Role 表（admin/staff/teacher/student） | ✅ 已实现 |
| 登录安全（爆破防护、账号锁定） | `auth.py` `failed_login_attempts` / `is_locked` 字段 | ✅ 已实现 |

---

### 第 4–5 周：系统整体设计，数据库设计

**交付成果**：系统设计说明书、数据库 ER 图（待补齐，见第四节）

**对应已实现数据模型**（`app/models/photography.py`）：

| 数据表 | 模型类 | 核心字段 |
|-------|--------|---------|
| `roles` | `Role` | id, role_name, description |
| `users` | `User` | id, username, password_hash, real_name, department, phone, status, role_id |
| `students` | `Student` | id, name, phone, id_card, address, notes, user_id, created_by |
| `courses` | `Course` | id, name, description, price, duration_weeks, status |
| `training_classes` | `TrainingClass` | id, class_no, course_id, teacher_id, start_date, end_date, capacity, status |
| `enrollments` | `Enrollment` | id, student_id, class_id, status, service_start, service_end |
| `payments` | `Payment` | id, enrollment_id, amount, pay_type, pay_method, pay_time |
| `works` | `Work` | id, student_id, enrollment_id, title, file_url, deadline, status |
| `work_reviews` | `WorkReview` | id, work_id, teacher_id, score, comment, review_time |
| `sys_logs` | `SysLog` | id, user_id, action, target, ip_address, risk_level, risk_msg |

**ER 关系摘要**：

```
User ──1:N──> Student (user_account)
Student ──1:N──> Enrollment
Course ──1:N──> TrainingClass
TrainingClass ──1:N──> Enrollment
Enrollment ──1:N──> Payment
Enrollment ──1:N──> Work
Student ──1:N──> Work
Work ──1:N──> WorkReview
User(teacher) ──1:N──> WorkReview
User ──1:N──> SysLog
```

---

### 第 6–10 周：分模块编码开发，实现核心功能

**交付成果**：系统核心版本源码（**已实现**）

| 模块 | 蓝图文件 | 关键 API 路由 | 状态 |
|-----|---------|-------------|------|
| 认证 | `routes/auth.py` | POST `/api/login`, POST `/api/register`, POST `/api/logout` | ✅ |
| 学员管理 | `routes/student.py` | GET/POST `/student/api/list`, `/student/api/add`, `/student/api/update` | ✅ |
| 报名管理 | `routes/student.py` | GET/POST `/enrollment/api/list`, `/enrollment/api/add`, `/enrollment/api/update_status` | ✅ |
| 缴费管理 | `routes/student.py` | GET/POST `/payment/api/list`, `/payment/api/add` | ✅ |
| 课程管理 | `routes/course.py` | GET/POST `/course/api/list`, `/course/api/add`, `/course/api/update` | ✅ |
| 班级管理 | `routes/course.py` | GET/POST `/class/api/list`, `/class/api/add`, `/class/api/update` | ✅ |
| 作品管理 | `routes/work.py` | GET `/work/api/list`, POST `/work/api/submit`, POST `/work/api/review` | ✅ |
| 作品提醒 | `routes/work.py` | GET `/work/api/reminders`（截止 24h 预警、逾期告警） | ✅ |
| 用户管理 | `routes/admin.py` | GET/POST `/admin/api/users/pending`, `/admin/api/users/all`, `/admin/api/users/update`, `/admin/api/users/delete` | ✅ |
| 审计日志 | `routes/admin.py` | GET `/admin/api/audit/list`, `/admin/api/sys_logs/list`, `/admin/api/sys_logs/alerts` | ✅ |

---

### 第 11–12 周：前端界面开发与整合

**交付成果**：可运行的系统测试版（**已实现基础版本**）

| 页面 | 模板文件 | 功能描述 |
|-----|---------|---------|
| 登录页 | `templates/login.html` | 账号密码登录，CSRF 防护 |
| 注册页 | `templates/register.html` | 学员自助注册，等待审核 |
| 工作台首页 | `templates/dashboard.html` | 角色菜单、作品截止提醒横幅、风险告警横幅 |
| 学员管理页 | `templates/student/index.html` | 学员档案 CRUD、报名缴费管理 |
| 课程班级页 | `templates/course/index.html` | 课程/班级 CRUD、教师分配 |
| 作品管理页 | `templates/work/index.html` | 作品列表、提交作品、教师点评 |
| 用户审核页 | `templates/admin/review_users.html` | 审核注册申请、用户管理 |
| 审计日志页 | `templates/admin/audit.html` | 业务操作日志、系统日志、风险告警 |

---

### 第 13 周：全面测试系统功能

**交付成果**：系统测试报告（待补齐，见第四节）

**当前测试基础**：

- `test_system.py`：功能验证脚本，覆盖以下场景：
  - 场景 1：RBAC 账户状态安全拦截测试
  - 场景 2：非工作时间操作审计测试
  - 场景 3：作品逾期风险审计测试
  - 场景 4：作品截止提醒逻辑测试
  - 场景 5：报名缴费数据模型验证
  - 场景 6：Web 安全技术确认（SQL 注入、XSS、CSRF、RBAC）

---

### 第 14–15 周：论文撰写与答辩准备

**交付成果**：毕业论文初稿、用户手册、答辩 PPT（待补齐，见第四节）

---

## 三、任务书工作内容 → 系统实现映射

### Ⅱ-1 专业知识综合运用

| 课程知识点 | 系统中的体现 |
|-----------|------------|
| 管理信息系统（系统规划与分析） | 四层架构：展示层(HTML/JS) → 业务层(Flask蓝图) → 数据层(SQLAlchemy ORM) → 存储层(MySQL) |
| 系统工程（业务流程建模） | 学员注册→审核→报名→缴费→上课→作品提交→点评→结课的全生命周期流程 |
| 数据库原理（数据建模） | 10 张规范化数据表，满足第三范式，外键约束完整 |
| 信息资源管理（信息整合） | SysLog 审计表整合所有业务操作记录，支持风险等级分析 |

### Ⅱ-2 技术或观点创新

| 创新点 | 任务书描述 | 代码实现 |
|-------|-----------|---------|
| 轻量化业务嵌入式路径 | 适用于小微创意服务企业 | Flask 轻框架 + 单文件蓝图，部署简单 |
| 学员作品流程化管理 | 重视觉成果的行业特点 | `Work` + `WorkReview` 双表，状态机管理（submitted/reviewed/overdue） |
| 培训服务周期跟踪 | 融合学员作品与服务周期 | `Enrollment.service_start/service_end` + `/work/api/reminders` 提醒 API |
| 管理学视角设计 | 区别于纯软件开发视角 | 业务流程（DFD 准备）、ER 图、RBAC 角色模型体现管理信息系统理论 |

---

## 四、待补齐交付件清单

以下为任务书明确要求但代码仓库中尚未产出的文档/成果，需在对应周次内完成：

| 交付件 | 对应周次 | 建议内容/工具 | 状态 |
|-------|---------|-------------|------|
| **需求规格说明书** | 第 1–3 周 | 系统目标、功能清单、用例图（UML）、非功能需求（性能、安全）；使用 Word/Markdown 撰写 | ⬜ 待产出 |
| **系统设计说明书** | 第 4–5 周 | 总体架构图、模块划分、接口设计规范、数据库设计说明；使用 Word/Markdown | ⬜ 待产出 |
| **数据库 ER 图** | 第 4–5 周 | 基于本文件第二节的 10 张表关系，使用 Visio / ProcessOn / draw.io 绘制，包含主键、外键、字段类型 | ⬜ 待产出 |
| **业务流程图（AS-IS / TO-BE）** | 第 4–5 周 | 现状流程（线下表格+微信）与优化后流程（系统内闭环），使用 Visio/ProcessOn 绘制 | ⬜ 待产出 |
| **数据流图（DFD）** | 第 4–5 周 | 0 层图（系统与外部实体）+ 1 层图（主要处理过程），外部实体：学员/教务/教师/管理员 | ⬜ 待产出 |
| **系统测试报告** | 第 13 周 | 功能测试（每个 API 接口的用例）、安全测试（CSRF/XSS/SQL注入）、性能测试；基于 `test_system.py` 扩展 | ⬜ 待产出 |
| **用户手册** | 第 14 周 | 安装部署手册（`init_db.py` + `run.py`）、各角色操作指南（学员/教务/教师/管理员）、常见问题 FAQ | ⬜ 待产出 |
| **答辩 PPT 大纲** | 第 15 周 | 建议结构：①研究背景与问题②需求分析③系统设计(ER图+架构图)④核心功能演示⑤技术与管理学创新点⑥总结展望 | ⬜ 待产出 |

---

## 五、已有代码与论文框架的对应关系

论文建议采用经典信息系统分析与设计框架，与现有代码对应如下：

| 论文章节 | 内容要点 | 已有代码支撑 |
|---------|---------|------------|
| 第 1 章 绪论 | 研究背景、摄影机构管理痛点、系统目标 | README.md（需丰富）、本映射文档 |
| 第 2 章 相关理论 | 诺兰阶段模型、MIS 理论、Flask/SQLAlchemy 技术选型依据 | `config.py`、`app/__init__.py` 技术架构 |
| 第 3 章 需求分析 | 现状诊断、功能需求、数据需求 | 本映射文档第二节功能清单；需补：需求规格说明书 |
| 第 4 章 系统设计 | 功能结构图、数据库设计、ER 图、DFD | `app/models/photography.py`（10 张表）；需补：ER 图、DFD |
| 第 5 章 系统实现 | 关键功能截图、核心代码讲解 | `routes/`（student/course/work/admin）+ `templates/` |
| 第 6 章 系统测试 | 测试用例、测试结果 | `test_system.py`（需扩展为正式测试报告）|
| 第 7 章 可行性论证 | 技术、经济、操作可行性 | Flask 轻量化部署可行性；需在论文中论述 |
| 第 8 章 总结展望 | 成果总结、局限性、改进方向 | 本映射文档第四节待补齐清单可作为"局限性"依据 |

---

## 六、代码改进建议（向论文答辩前完善）

1. **`security.py` 工作时间逻辑**：`WORKING_HOUR_END = 24` 定义了但未使用，晚上 20-23 点的操作不会触发预警。建议修改为 `current_hour < WORKING_HOUR_START or current_hour >= 18` 以完整覆盖非办公时间。

2. **`config.py` 密码安全**：明文数据库密码和默认 SECRET_KEY 应通过环境变量或 `.env` 文件配置；建议添加 `.env.example` 示例文件并将真实配置加入 `.gitignore`。

3. **旧模块清理**：`app/routes/equipment.py` 和 `app/models/equipment.py` 是医疗设备借还系统的遗留文件，已不被主应用注册使用，可在下次提交中删除，以保持代码库整洁。

4. **分页功能**：`/admin/api/audit/list` 中 `limit(200)` 为硬限制，建议改为分页参数（`page` + `per_page`），以应对数据增长。

5. **`student.py` 中教师可见作品**：`work.py` 中教师角色通过 `class_ids → enrollment_ids` 间接查询作品，若某班级报名为空会提前返回空列表，建议加注释说明此设计意图。

---

*最后更新：2026 年 4 月*
