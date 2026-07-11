from __future__ import annotations

from pathlib import Path

import nbformat as nbf


TASK_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = TASK_DIR / "Task3_process_walkthrough.ipynb"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def build_notebook() -> Path:
    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    }
    notebook["cells"] = [
        markdown(
            """
# Task3 教学流程：双均线策略与回测

## Goal

本 Notebook 演示如何从本地前复权行情出发，计算 MA5/MA15、识别金叉与死叉、将信号转换为下一交易期仓位，并计算累计回报、最大回撤和夏普比率。
            """
        ),
        markdown(
            """
## Setup

### Key Assumptions

- 初始资金 100,000 元，只做多，不加杠杆。
- 当日收盘后形成信号，下一交易期才应用仓位。
- 单边综合交易成本设为 0.1%，无风险利率设为 0。
- 使用前复权日线价格，避免除权除息造成机械跳空。
            """
        ),
        code(
            """
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path.cwd()
if not (ROOT / "Task3").exists():
    ROOT = ROOT.parent
SCRIPTS = ROOT / "Task3" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from config import CROSS_TOLERANCE, DEFAULT_TRANSACTION_COST, PARAMETER_PAIRS, UNIVERSE, parameter_label
from strategy_backtest import load_prices, run_backtest, summarize_backtest

pd.set_option("display.max_columns", 20)
pd.set_option("display.float_format", lambda value: f"{value:.4f}")
            """
        ),
        markdown("## Steps\n\n### 1. 加载本地行情数据"),
        code(
            """
stock = UNIVERSE[0]  # 平安银行
prices = load_prices(stock)
print(stock)
print(f"数据区间：{prices['trade_date'].min().date()} 至 {prices['trade_date'].max().date()}，共 {len(prices)} 个交易日")
prices[["trade_date", "open", "high", "low", "close", "vol"]].head()
            """
        ),
        markdown("### 2. 计算 MA5、MA15 和交易信号"),
        code(
            """
result = run_backtest(prices, short_window=5, long_window=15)
signal_rows = result.loc[result["execution"].ne("HOLD"), [
    "trade_date", "close", "short_ma", "long_ma", "signal", "execution", "position"
]]
signal_rows.head(10)
            """
        ),
        markdown(
            """
`signal` 是收盘后观察到的金叉或死叉；`execution` 是错后一日实际应用的仓位变化。两列分开可以清楚证明回测没有把信号日已经发生的收益算进去。
            """
        ),
        markdown("### 3. 绘制价格、均线和买卖执行点"),
        code(
            """
buys = result["execution"].eq("BUY")
sells = result["execution"].eq("SELL")

fig, axis = plt.subplots(figsize=(13, 5))
axis.plot(result["trade_date"], result["close"], label="前复权收盘价", color="#1f2937", linewidth=1.2)
axis.plot(result["trade_date"], result["short_ma"], label="MA5", color="#2563eb")
axis.plot(result["trade_date"], result["long_ma"], label="MA15", color="#d97706")
axis.scatter(result.loc[buys, "trade_date"], result.loc[buys, "close"], marker="^", color="#0f766e", label="买入执行")
axis.scatter(result.loc[sells, "trade_date"], result.loc[sells, "close"], marker="v", color="#be123c", label="卖出执行")
axis.set_title(f"{stock.stock_name} MA5/MA15 双均线信号")
axis.set_ylabel("价格（元）")
axis.grid(alpha=0.3)
axis.legend(ncol=5)
plt.show()
            """
        ),
        markdown("### 4. 计算策略绩效"),
        code(
            """
metrics = summarize_backtest(result)
pd.Series(metrics, name="MA5/MA15")
            """
        ),
        markdown("### 5. 比较不同均线周期"),
        code(
            """
parameter_rows = []
for short_window, long_window in PARAMETER_PAIRS:
    parameter_result = run_backtest(prices, short_window, long_window)
    parameter_metrics = summarize_backtest(parameter_result, start_date="2024-01-01")
    parameter_rows.append({
        "参数": parameter_label(short_window, long_window),
        "累计回报": parameter_metrics["cumulative_return"],
        "最大回撤": parameter_metrics["max_drawdown"],
        "夏普比率": parameter_metrics["sharpe_ratio"],
        "买入次数": parameter_metrics["buy_count"],
    })

parameter_comparison = pd.DataFrame(parameter_rows).sort_values("夏普比率", ascending=False)
parameter_comparison
            """
        ),
        markdown("## Checks\n\n下面用简单断言检查交易规则、信号错位和绩效指标范围。"),
        code(
            """
expected_target = ((result["short_ma"] > result["long_ma"] + CROSS_TOLERANCE) & result["long_ma"].notna()).astype(int)
expected_position = expected_target.shift(1).fillna(0).astype(int)

assert result["target_position"].equals(expected_target)
assert result["position"].equals(expected_position)
assert result.loc[:13, "position"].eq(0).all()
assert -1 <= metrics["max_drawdown"] <= 0
assert metrics["buy_count"] >= metrics["sell_count"]
assert (result["transaction_cost"] >= 0).all()

print("检查通过：信号规则、次日仓位、最大回撤范围和交易成本均符合预期。")
            """
        ),
        markdown(
            """
## Next Steps

1. 将 `stock = UNIVERSE[0]` 改成其他股票，观察行业差异。
2. 修改 `PARAMETER_PAIRS`，但不要只根据全样本最高收益挑参数。
3. 优先比较 2024 年以后的样本外结果，并同时查看回撤、交易次数和买入持有基准。
4. 进一步研究可加入滚动样本外检验、波动率过滤和更真实的成交约束。
            """
        ),
    ]
    nbf.write(notebook, NOTEBOOK_PATH)
    return NOTEBOOK_PATH


if __name__ == "__main__":
    print(build_notebook())
