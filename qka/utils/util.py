from xtquant import xtconstant
from datetime import datetime
from qka.utils.anis import RED, GREEN, YELLOW, BLUE, RESET

def add_stock_suffix(stock_code):
    """
    为给定的股票代码添加相应的后缀。
    """
    # 检查股票代码是否为6位数字
    if len(stock_code) != 6 or not stock_code.isdigit():
        raise ValueError("股票代码必须是6位数字")

    # 根据股票代码的前缀添加相应的后缀
    if stock_code.startswith("00") or stock_code.startswith("30") or stock_code.startswith("15") or stock_code.startswith("16") or stock_code.startswith("18") or stock_code.startswith("12"):
        return f"{stock_code}.SZ"  # 深圳证券交易所
    elif stock_code.startswith("60") or stock_code.startswith("68") or stock_code.startswith("11"):
        return f"{stock_code}.SH"  # 上海证券交易所
    elif stock_code.startswith("83") or stock_code.startswith("43"):
        return f"{stock_code}.BJ"  # 北京证券交易所

    raise ValueError(f"无法识别股票代码前缀: {stock_code}")

def timestamp_to_datetime_string(timestamp):
    """
    将时间戳转换为时间字符串。

    :param timestamp: 时间戳（秒级）
    :return: 格式化的时间字符串 'YYYY-MM-DD HH:MM:SS'
    """
    dt_object = datetime.fromtimestamp(timestamp)
    time_string = dt_object.strftime('%Y-%m-%d %H:%M:%S')
    return time_string

def parse_order_type(order_type):
    if order_type == xtconstant.STOCK_BUY:
        return f"{RED}买入{RESET}"
    elif order_type == xtconstant.STOCK_SELL:
        return f"{GREEN}卖出{RESET}"
    return f"未知({order_type})"

def convert_to_current_date(timestamp):
    """
    将时间戳转换为秒级时间戳，保留原始日期和时间。

    :param timestamp: 时间戳（秒级或毫秒级）
    :return: 秒级时间戳
    """
    # 处理毫秒级时间戳
    if timestamp > 1e12:
        timestamp = timestamp / 1000
    return timestamp