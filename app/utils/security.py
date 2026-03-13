# 文件位置：app/utils/security.py
from datetime import datetime, timedelta

# =================配置区域=================
# 定义正常办公时间 (24小时制)
WORKING_HOUR_START = 8  # 早上 8 点
WORKING_HOUR_END = 20  # 晚上 8 点

# 定义设备超长使用阈值 (天)
MAX_BORROW_DAYS = 14


# ==========================================

def check_operation_risk():
    """
    检查当前操作时间是否存在异常风险
    返回: (risk_level, message)
    risk_level: 0-正常, 1-警告(非工作时间操作)
    """
    now = datetime.now()
    current_hour = now.hour

    # 判断是否在非办公时间
    if current_hour < WORKING_HOUR_START or current_hour >= WORKING_HOUR_END:
        return 1, f"非工作时间异常操作 (当前时间: {now.strftime('%H:%M')})"

    return 0, "正常时间操作"


def check_borrow_duration_risk(borrow_time):
    """
    检查设备借用时长是否超标
    :param borrow_time: 设备借出的起始时间 (datetime对象)
    返回: (risk_level, message)
    risk_level: 0-正常, 2-危险(超长使用)
    """
    if not borrow_time:
        return 0, ""

    now = datetime.now()
    duration = now - borrow_time

    # 如果借用时长超过设定的阈值 (例如14天)
    if duration.days >= MAX_BORROW_DAYS:
        return 2, f"设备超长使用警告 (已借用 {duration.days} 天，建议核查设备安全状态)"

    return 0, "借用时长正常"


def get_combined_risk(risks):
    """
    综合多个风险判定结果，取最高级别
    :param risks: 列表，例如 [(1, 'msg1'), (2, 'msg2')]
    """
    if not risks:
        return 0, ""

    # 按风险等级排序，取最高的
    sorted_risks = sorted(risks, key=lambda x: x[0], reverse=True)
    return sorted_risks[0]