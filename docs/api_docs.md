# 接口说明文档

> 所有 POST 接口均需在请求头中携带 `X-CSRFToken`（从页面 `<meta name="csrf-token">` 读取）。

## 1. 认证接口（auth）

### POST /api/login — 登录
**请求体（JSON）：**
```json
{ "username": "admin", "password": "123456" }
```
**响应：**
- `200` 登录成功，session 写入 user_id/role_name/real_name
- `401` 账号/密码错误
- `403` 待审核 / 已拒绝 / 账号锁定

### POST /api/logout — 登出
清空 session，重定向到登录页。

### GET /login — 登录页面
### GET /register — 注册页面
### POST /api/register — 提交注册
```json
{ "username": "newuser", "password": "123456", "real_name": "姓名", "department": "学员", "role_name": "student" }
```

---

## 2. 学员管理接口（student）

### GET /student/ — 学员管理页面（admin/staff/student）

### GET /student/api/list — 学员列表（admin/staff）
返回所有学员档案列表。

### GET /student/api/my_info — 我的档案（student）
返回当前登录学员的个人档案。

### POST /student/api/add — 新增学员（admin/staff）
```json
{ "name": "张三", "phone": "13900000001", "id_card": "...", "address": "...", "notes": "" }
```

### POST /student/api/update — 修改学员（admin/staff）
```json
{ "id": 1, "name": "张三改", "phone": "13900000001" }
```

---

## 3. 报名接口（enrollment）

### GET /enrollment/api/list — 报名列表（admin/staff/student）
- admin/staff：`?student_id=1` 可过滤
- student：自动返回当前学员的报名记录

### POST /enrollment/api/add — 新增报名（admin/staff）
```json
{ "student_id": 1, "class_id": 1, "status": "active", "service_start": "2024-03-01", "service_end": "2024-04-26", "notes": "" }
```

### POST /enrollment/api/update_status — 更新报名状态（admin/staff）
```json
{ "id": 1, "status": "withdrawn" }
```
允许状态：`active / pending / withdrawn / completed`

---

## 4. 缴费接口（payment）

### GET /payment/api/list — 缴费列表（admin/staff）
- `?enrollment_id=1` 按报名过滤

### POST /payment/api/add — 录入缴费（admin/staff）
```json
{ "enrollment_id": 1, "amount": 1000, "pay_type": "deposit", "pay_method": "wechat", "notes": "定金" }
```
- `pay_type`：`deposit`（定金）/ `final`（尾款）/ `refund`（退款）
- `pay_method`：`cash` / `wechat` / `alipay` / `transfer`

---

## 5. 课程接口（course）

### GET /course/ — 课程与班级管理页面（admin/staff/teacher）

### GET /course/api/list — 课程列表（admin/staff/teacher）
### POST /course/api/add — 新增课程（admin/staff）
```json
{ "name": "人像摄影班", "description": "...", "price": 2980, "duration_weeks": 8, "status": "active" }
```
### POST /course/api/update — 修改课程（admin/staff）
```json
{ "id": 1, "name": "新名称", "price": 3000 }
```

### GET /class/api/list — 班级列表（admin/staff/teacher）
### POST /class/api/add — 新增班级（admin/staff）
```json
{ "class_no": "RX-2024-01", "course_id": 1, "teacher_id": 2, "start_date": "2024-03-01", "end_date": "2024-04-26", "capacity": 15 }
```
### POST /class/api/update — 修改班级（admin/staff）

### GET /course/api/teachers — 教师列表（admin/staff/teacher）
返回所有 teacher 角色的已审核用户。

---

## 6. 作品接口（work）

### GET /work/ — 作品管理页面（all roles）

### GET /work/api/list — 作品列表（all roles）
- `student`：仅看自己的作品
- `teacher`：仅看所授班级的学员作品
- `admin/staff`：全部作品

### POST /work/api/submit — 提交作品（student）
```json
{ "title": "人像练习", "description": "...", "file_url": "https://...", "enrollment_id": 1, "deadline": "2024-04-10 23:59" }
```

### POST /work/api/review — 点评作品（admin/teacher）
```json
{ "work_id": 1, "score": 85, "comment": "构图不错，光线有待改进" }
```

### GET /work/api/reminders — 作品提醒（all roles）
返回 24 小时内即将截止或已逾期的作品列表。

---

## 7. 管理员接口（admin）

### GET /admin/users/review — 用户管理页面（admin）

### GET /admin/api/users/pending — 待审核用户列表（admin）
### POST /admin/api/users/do_review — 审核用户（admin）
```json
{ "user_id": 5, "action": "approve" }
```
action：`approve` / `reject`

### GET /admin/api/users/all — 全部用户列表（admin）
### POST /admin/api/users/update — 修改用户信息（admin）
```json
{ "user_id": 5, "role_id": 2, "new_password": "newpass", "unlock": true }
```
### POST /admin/api/users/delete — 删除用户（admin）
### GET /admin/api/users/roles — 所有角色列表（admin）

### GET /admin/audit — 审计日志页面（admin）
### GET /admin/api/audit/list — 业务流水审计（admin）
### GET /admin/api/sys_logs/list — 系统日志（admin）
- `?user_id=admin&start_date=2024-01-01&risk_level=1`
### GET /admin/api/sys_logs/alerts — 24小时风险统计（admin）

---

## 8. 错误响应格式

所有 API 接口使用统一 JSON 响应格式：

```json
{ "code": 200, "msg": "操作成功", "data": [...] }
```

错误状态码：
- `400`：参数错误 / 业务逻辑校验失败
- `401`：未登录
- `403`：权限不足 / 账号状态拦截
- `404`：资源不存在
