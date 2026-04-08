# ER 图与表结构说明

## 1. 概念 ER 图（文字描述）

```
┌─────────┐       ┌──────────┐       ┌──────────────┐
│  roles  │──1:N──│  users   │──1:N──│ training_    │
│         │       │          │       │ classes      │
└─────────┘       └──────────┘       └──────┬───────┘
                        │1                   │1
                        │N                   │N
                   ┌────────┐          ┌────────────┐
                   │students│──1:N─────│enrollments │
                   └────────┘          └──────┬─────┘
                        │1                    │1
                        │N              ┌─────┴─────┐
                   ┌────────┐       ┌──────┐  ┌────────┐
                   │ works  │       │pay-  │  │ works  │
                   └────────┘       │ments │  │(via    │
                        │1          └──────┘  │enroll) │
                        │N                    └────────┘
                  ┌──────────┐
                  │work_     │
                  │reviews   │
                  └──────────┘
```

## 2. 物理表结构

### roles（角色表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| role_name | VARCHAR(50) UNIQUE | 角色标识（admin/staff/teacher/student） |
| description | VARCHAR(255) | 角色描述 |

### users（用户表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| username | VARCHAR(50) UNIQUE | 登录账号 |
| password_hash | VARCHAR(255) | 密码哈希（PBKDF2） |
| real_name | VARCHAR(50) | 真实姓名 |
| department | VARCHAR(100) | 所属部门 |
| phone | VARCHAR(20) | 联系电话 |
| status | VARCHAR(20) | 账号状态（pending/approved/rejected） |
| failed_login_attempts | INT | 连续登录失败次数（防爆破） |
| is_locked | BOOLEAN | 账号是否锁定 |
| role_id | INT FK→roles | 所属角色 |
| created_at | DATETIME | 创建时间 |

### students（学员档案表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| name | VARCHAR(50) | 学员姓名 |
| phone | VARCHAR(20) UNIQUE | 手机号（唯一索引） |
| id_card | VARCHAR(30) | 身份证号 |
| address | VARCHAR(255) | 地址 |
| notes | TEXT | 备注 |
| user_id | INT FK→users | 关联的登录账号（可空） |
| created_by | INT FK→users | 录入人 |
| created_at | DATETIME | 创建时间 |

### courses（课程表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| name | VARCHAR(100) UNIQUE | 课程名称 |
| description | TEXT | 课程描述 |
| price | DECIMAL(10,2) | 学费 |
| duration_weeks | INT | 课时（周数） |
| status | VARCHAR(20) | 状态（active/inactive） |
| created_at | DATETIME | 创建时间 |

### training_classes（班级表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| class_no | VARCHAR(50) UNIQUE | 班级编号（唯一索引） |
| course_id | INT FK→courses | 所属课程 |
| teacher_id | INT FK→users | 授课教师 |
| start_date | DATE | 开课日期 |
| end_date | DATE | 结课日期 |
| capacity | INT | 班级容量 |
| status | VARCHAR(20) | 状态（open/closed/finished） |
| notes | TEXT | 备注 |
| created_at | DATETIME | 创建时间 |

### enrollments（报名表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| student_id | INT FK→students | 学员 |
| class_id | INT FK→training_classes | 所在班级 |
| status | VARCHAR(20) | 报名状态（active/pending/withdrawn/completed） |
| enrolled_at | DATETIME | 报名时间 |
| service_start | DATE | 服务起始日期 |
| service_end | DATE | 服务截止日期 |
| notes | TEXT | 备注 |
| created_by | INT FK→users | 录入人 |

### payments（缴费流水表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| enrollment_id | INT FK→enrollments | 关联报名 |
| amount | DECIMAL(10,2) | 金额 |
| pay_type | VARCHAR(20) | 类型（deposit定金/final尾款/refund退款） |
| pay_method | VARCHAR(20) | 方式（cash/wechat/alipay/transfer） |
| pay_time | DATETIME | 缴费时间 |
| notes | TEXT | 备注 |
| recorded_by | INT FK→users | 录入人 |

### works（作品表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| student_id | INT FK→students | 提交学员 |
| enrollment_id | INT FK→enrollments | 关联报名（可空） |
| title | VARCHAR(200) | 作品标题 |
| description | TEXT | 作品描述 |
| file_url | VARCHAR(500) | 作品 URL / 文件路径 |
| submitted_at | DATETIME | 提交时间 |
| deadline | DATETIME | 截止时间 |
| status | VARCHAR(20) | 状态（submitted/reviewed/overdue） |

### work_reviews（点评表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| work_id | INT FK→works | 关联作品 |
| teacher_id | INT FK→users | 点评教师 |
| score | INT | 评分（0-100） |
| comment | TEXT | 评语 |
| review_time | DATETIME | 点评时间 |
| status | VARCHAR(20) | 点评状态（done） |

### sys_logs（系统审计日志表）
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 主键 |
| user_id | INT FK→users | 操作人（可空，系统操作） |
| action | VARCHAR(100) | 操作行为 |
| target | VARCHAR(255) | 操作对象/详情 |
| ip_address | VARCHAR(50) | 客户端 IP |
| risk_level | INT | 风险等级（0正常/1警告/2危险） |
| risk_msg | VARCHAR(255) | 风险描述 |
| created_at | DATETIME | 操作时间 |
