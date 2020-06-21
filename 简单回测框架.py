"""
搭建简答的交易回测框架
包括：上下文信息保存
获取数据
下单函数
用户接口
"""

# 缺点： 没实现t+1 或者单次 T+0 限制
# 双均线策略 均线算法不准确 影响交易质量

from datetime import *
import numpy as np
import baostock as bs
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]

# lg = bs.login()
# rs = bs.query_trade_dates(start_date="1988-01-01")
# data_list = []
# while (rs.error_code == '0') & rs.next():
#     # 获取一条记录，将记录合并在一起
#     data_list.append(rs.get_row_data())
# trade_cal = pd.DataFrame(data_list, columns=rs.fields)
# # print(trade_cal)
# trade_cal.to_csv("./trade_calender.csv")
# rs = bs.query_history_k_data_plus("sh.601318",
#                                   "date,open,high,low,close,volume",
#                                   start_date='2000-01-01',
#                                   frequency="d", adjustflag="3")
# while (rs.error_code == '0') & rs.next():
#     # 获取一条记录，将记录合并在一起
#     data_list.append(rs.get_row_data())
# result = pd.DataFrame(data_list, columns=rs.fields)
# result.to_csv("./sh.601318.csv")

# 用户输入
CASH = 1000000
START_DATE = "2017-01-01"
END_DATE = "2019-01-01"
SECURITY = "sh.601318"

trade_cal = pd.read_csv("./trade_calender.csv", header=0, index_col=0)
# print(trade_cal.head())
# print(trade_cal["calendar_date"].dtype) -- objective

# 到 2020-06-12
trade_cal["calendar_date"] = pd.to_datetime(trade_cal["calendar_date"])


# print(trade_cal["calendar_date"].dtype) datetime64[ns]


class Context:
    """上下文记录功能"""

    def __init__(self, cash, start_date, end_date):
        self.cash = cash
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.position = {}
        self.benchmark = None
        # 数组
        self.date_range = trade_cal[(trade_cal["is_trading_day"] == 1) &
                                    (trade_cal["calendar_date"] >= self.start_date) &
                                    (trade_cal["calendar_date"] <= self.end_date)]["calendar_date"].values
        self.true_today = self.date_range[-1]


context = Context(CASH, START_DATE, END_DATE)
# print(context.date_range[-10:])
# print(context.end_date, type(context.end_date))
# print(context.date_range.dtype)


class G:
    """自定义创建新的属性"""
    pass


def attribute_history_data(security, count, fileds=("open", "close", "high", "low", "volume")):
    """
    获取历史数据
    :param security: 股票代码
    :param count: 获取count 天前的数据
    :param fileds:
    :return:
    """
    # 今天的数据可能不是历史
    # date_df = pd.DataFrame(context.date_range)
    end_date = context.true_today
    # end_date = np.datetime64(end_date)
    start_date = context.date_range[context.date_range <= end_date][-count:][0]
    # start_date = datetime.strptime(str(start_date), "%Y-%m-%d")
    # print(start_date, end_date)

    return attribute_date_history(security, start_date, end_date, fileds)


def attribute_date_history(security, start_date, end_date, fileds=("open", "close", "high", "low", "volume")):
    data = pd.read_csv(security + ".csv", header=0, index_col="date", parse_dates=["date"]).loc[start_date: end_date, :]
    # print(data.head())
    return data[list(fileds)]


def set_benchmark(security):
    # 只支持一只股票
    context.benchmark = security

# 下单函数


def get_today_data(security):
    today = context.true_today
    today_df = pd.read_csv(security + ".csv", header=0, index_col="date", parse_dates=["date"])
    del today_df["Unnamed: 0"]
    try:
        today_data = today_df.loc[today, :]
    except KeyError:
        today_data = pd.Series()
    return today_data


def _order(today_data, security, amount):
    price = today_data["open"]
    if len(today_data) == 0:
        print("今日停牌")
        return

    if context.cash - amount * price < 0:
        amount = int(context.cash / price)
        print("现金不足买不起%d股" % amount)

    if amount % 100 != 0:
        if amount != -context.position.get(security, 0):
            amount = int(amount/100) * 100
            print("不是一百的倍数，自动调整为%d" % amount)

    if context.position.get(security, 0) < -amount:
        amount = -context.position.get(security, 0)
        print("卖出股票不能超过持仓股票，已调整为%d" % amount)

    context.position[security] = context.position.get(security, 0) + amount

    context.cash -= amount * price

    if context.position[security] == 0:
        del context.position[security]


def order(security, amount):
    today_data = get_today_data(security)
    _order(today_data, security, amount)


def order_target(security, amount):
    """
    卖剩多少股
    :param security:
    :param amount:
    :return:
    """
    if amount < 0:
        print("不能为负")
    today_data = get_today_data(security)
    hold = context.position.get(security, 0)
    sell_amount = hold - amount
    _order(today_data, security, sell_amount)


def order_value(security, value):
    today_data = get_today_data(security)
    amount = int(value / today_data["open"])
    _order(today_data, security, amount)


def order_target_value(security, target_value):
    today_data = get_today_data(security)
    hold_value = context.position.get(security, 0) * today_data["open"]
    delta_value = target_value - hold_value
    order_value(security, delta_value)


def run():
    """
    回测框架主函数
    :return:
    """
    plt_df = pd.DataFrame(index=pd.DatetimeIndex(context.date_range), columns=["value"], dtype=np.float64)
    initialize(context)
    init_cash = context.cash
    last_price = {}
    for dt in context.date_range:
        context.true_today = dt
        handle_data(context)
        value = context.cash
        for stock in context.position:
            today_data = get_today_data(stock)
            if len(today_data) == 0:
                price = last_price[stock]
            else:
                price = today_data["open"]
                last_price[stock] = price
            value += context.position[stock] * price
        plt_df.loc[dt, "value"] = value
    plt_df["ratio"] = (plt_df["value"] - init_cash)/init_cash

    benchmark_data = attribute_date_history(context.benchmark, context.start_date, context.end_date)
    benchmark_data_init = benchmark_data["open"][0]
    plt_df["benchmark_ratio"] = (benchmark_data["open"] - benchmark_data_init) / benchmark_data_init
    fig = plt.figure(figsize=(10, 8), dpi=100)
    plt.plot(plt_df.index, plt_df["ratio"], label="ratio")
    plt_df["benchmark_ratio"].plot(label="benchmark_ratio")
    # x_ticks_label = [i for i in context.date_range]
    # plt.xticks(x_ticks_label[::3])
    plt.legend()
    plt.title(SECURITY + "收益率曲线")
    plt.show()


g = G()


def initialize(context):
    set_benchmark("sh.601318")
    g.ma5 = 5
    g.ma60 = 240
    g.security = "sh.601318"


def handle_data(context):
    """用户自定义"""
    hist = attribute_history_data(g.security, g.ma60)
    ma5 = hist["open"][-g.ma5:].mean()
    ma60 = hist["open"].mean()

    if ma5 > ma60 and g.security not in context.position:
        order_value(g.security, context.cash)

    if ma5 < ma60 and g.security in context.position:
        order_target_value(g.security, 0)

    print(ma5, ma60)


if __name__ == '__main__':
    # data = attribute_history_data("sh.601318", 10)
    # data = attribute_date_history(SECURITY, START_DATE, END_DATE)
    # print(data)
    run()


    
