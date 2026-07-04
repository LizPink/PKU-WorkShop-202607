from __future__ import annotations


INDICATOR_GUIDE = [
    {
        "指标": "RSI",
        "名称": "Relative Strength Index / 相对强弱指数",
        "计算方法": "先计算每日收盘价变化，U=max(涨跌幅, 0)，D=max(-涨跌幅, 0)；RS=WilderAvg(U, 14)/WilderAvg(D, 14)；RSI=100-100/(1+RS)。",
        "金融应用": "衡量上涨动能与下跌动能的相对强弱。常用 70 以上观察超买、30 以下观察超卖，也常配合价格背离判断动能衰减。",
        "解读提醒": "RSI 是动量指标，不是单独买卖信号。强趋势中 RSI 可以长时间维持高位或低位，需要结合趋势和成交量判断。",
    },
    {
        "指标": "MACD",
        "名称": "Moving Average Convergence Divergence / 指数平滑异同移动平均线",
        "计算方法": "EMA_n 使用 alpha=2/(n+1) 递推；DIF=EMA12(收盘价)-EMA26(收盘价)；Signal/DEA=EMA9(DIF)；本 demo 的柱状图= DIF-Signal。",
        "金融应用": "识别趋势动量变化。常看 DIF 与 Signal 的金叉/死叉、零轴上方或下方的位置，以及价格与 MACD 的背离。",
        "解读提醒": "MACD 本质上来自移动平均，天然滞后；震荡行情里交叉信号容易反复。一些行情软件会把柱状图写成 2*(DIF-DEA)，本项目没有乘以 2。",
    },
    {
        "指标": "Bollinger Bands",
        "名称": "布林带",
        "计算方法": "中轨=SMA20(收盘价)；标准差=收盘价的 20 日滚动标准差；上轨=中轨+2*标准差；下轨=中轨-2*标准差。",
        "金融应用": "用均线和波动率描述价格运行区间。带宽收窄常表示波动压缩，突破后可能进入趋势扩张；价格靠近上下轨可辅助观察短期偏热或偏冷。",
        "解读提醒": "触及上轨不等于必须卖出，触及下轨也不等于必须买入。趋势行情中价格可能沿上轨或下轨运行，需要结合方向和带宽变化。",
    },
    {
        "指标": "ATR",
        "名称": "Average True Range / 平均真实波幅",
        "计算方法": "TR=max(high-low, abs(high-前收盘), abs(low-前收盘))；ATR=WilderAvg(TR, 14)。",
        "金融应用": "衡量价格波动幅度，常用于设置止损距离、比较不同股票的波动水平、辅助仓位管理。",
        "解读提醒": "ATR 只衡量波动大小，不判断涨跌方向。ATR 上升说明波动变大，但不代表一定上涨或下跌。",
    },
]


def indicator_markdown() -> str:
    lines: list[str] = []
    for item in INDICATOR_GUIDE:
        lines.extend(
            [
                f"### {item['指标']}：{item['名称']}",
                f"- 计算方法：{item['计算方法']}",
                f"- 金融应用：{item['金融应用']}",
                f"- 解读提醒：{item['解读提醒']}",
                "",
            ]
        )
    return "\n".join(lines).strip()
