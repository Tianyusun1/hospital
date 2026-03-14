# 文件位置：app/utils/security.py
from datetime import datetime, timedelta

# =================配置区域=================
# 定义正常办公时间 (24小时制)
WORKING_HOUR_START = 8  # 早上 8 点
WORKING_HOUR_END = 24  # 晚上 12 点


# ==========================================

def check_operation_risk():
    """
    检查当前操作时间是否存在异常风险
    返回: (risk_level, message)
    risk_level: 0-正常, 1-警告(非工作时间操作)
    """
    # 获取 UTC 时间并转为北京时间 (UTC+8) 来准确判断办公时间
    now_utc = datetime.utcnow()
    now_beijing = now_utc + timedelta(hours=8)
    current_hour = now_beijing.hour

    # 判断是否在非办公时间
    if current_hour < WORKING_HOUR_START:
        return 1, f"非工作时间异常操作 (当前时间: {now_beijing.strftime('%H:%M')})"

    return 0, "正常时间操作"


def check_borrow_duration_risk(borrow_record):
    """
    【核心重构】：根据用户自定义的归还期限检查是否逾期
    :param borrow_record: BorrowRecord 模型对象
    返回: (risk_level, message)
    risk_level: 0-正常, 2-危险(逾期使用)
    """
    if not borrow_record or not borrow_record.due_time:
        return 0, ""

    now_utc = datetime.utcnow()

    # 逻辑：如果当前 UTC 时间已经超过了记录中的截止 UTC 时间
    if now_utc > borrow_record.due_time:
        # 计算逾期了多久（天）
        overdue_delta = now_utc - borrow_record.due_time
        overdue_days = overdue_delta.days

        # 格式化截止时间用于显示 (转北京时间)
        due_beijing = borrow_record.due_time + timedelta(hours=8)
        due_str = due_beijing.strftime('%Y-%m-%d')

        return 2, f"逾期归还警告 (约定归还日期: {due_str}，已逾期 {overdue_days} 天)"

    return 0, "借用时长正常"


def get_combined_risk(risks):
    """
    综合多个风险判定结果，取最高级别
    :param risks: 列表，例如 [(1, 'msg1'), (2, 'msg2')]
    """
    if not risks:
        return 0, ""

    # 按风险等级排序，取等级最高(0-正常, 1-警告, 2-危险)的那一个
    sorted_risks = sorted(risks, key=lambda x: x[0], reverse=True)
    return sorted_risks[0]