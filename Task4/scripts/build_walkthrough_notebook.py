from __future__ import annotations

from pathlib import Path

import nbformat as nbf
import pandas as pd

from config import DEFAULT_PARAMS, parameter_label


TASK_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = TASK_DIR / "Task4_process_walkthrough.ipynb"
OUTPUT_DIR = TASK_DIR / "outputs"


def markdown(text: str):
    return nbf.v4.new_markdown_cell(text.strip())


def code(text: str):
    return nbf.v4.new_code_cell(text.strip())


def build_notebook() -> Path:
    default_oos = pd.read_csv(OUTPUT_DIR / "default_summary.csv")
    default_oos = default_oos.loc[default_oos["sample_period"] == "out_of_sample"]
    median_return = default_oos["cumulative_return"].median()
    median_sharpe = default_oos["sharpe_ratio"].median()
    positive_count = int((default_oos["cumulative_return"] > 0).sum())

    notebook = nbf.v4.new_notebook()
    notebook["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    }
    notebook["cells"] = [
        markdown(
            f"""
# Task4 教学流程：海龟交易策略与回测

## Goal

本 Notebook 从本地前复权日线出发，逐步计算高低点通道、Wilder ATR、突破信号、ATR 止损、风险定仓和绩效指标，并演示如何比较不同股票及参数。

### 当前结果概览

默认参数 `{parameter_label(DEFAULT_PARAMS)}` 在2024年以后的10只股票中有 **{positive_count}/10** 取得正累计回报；跨股票中位累计回报为 **{median_return:.1%}**，中位夏普比率为 **{median_sharpe:.2f}**。这些结果用于教学和稳健性比较，不构成投资建议。
"""
        ),
        markdown(
            """
## Setup

### Key Assumptions

- 日线前复权价格；只做多、不加杠杆、不加仓。
- 入场通道20日、离场通道10日、ATR周期20日、止损距离2ATR。
- 通道全部向后移动1日，收盘产生通道信号，下一交易日开盘执行。
- 每笔交易计划风险为账户权益的1%，资金占用不超过100%，允许教学用小数股。
- 买卖单边综合交易成本均为0.1%，无风险利率设为0。
"""
        ),
        code(
            """
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path.cwd()
if not (ROOT / "Task4").exists():
    ROOT = ROOT.parent
SCRIPTS = ROOT / "Task4" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from config import DEFAULT_PARAMS, PARAMETER_SETS, UNIVERSE, parameter_label
from turtle_backtest import add_turtle_indicators, load_prices, run_backtest, summarize_backtest

pd.set_option("display.max_columns", 30)
pd.set_option("display.float_format", lambda value: f"{value:.4f}")
"""
        ),
        markdown("## Steps\n\n### 1. 加载已保存的行情数据"),
        code(
            """
stock = UNIVERSE[0]  # 平安银行，可替换为 UNIVERSE 中的其他股票
prices = load_prices(stock)
print(stock)
print(f"数据区间：{prices['trade_date'].min().date()} 至 {prices['trade_date'].max().date()}，共 {len(prices)} 个交易日")
prices[["trade_date", "open", "high", "low", "close", "vol"]].head()
"""
        ),
        markdown("### 2. 计算前20日最高通道、前10日最低通道和ATR20"),
        code(
            """
indicators = add_turtle_indicators(prices, DEFAULT_PARAMS)
indicators[[
    "trade_date", "close", "entry_high", "exit_low", "true_range", "atr",
    "entry_signal", "channel_exit_signal"
]].dropna().head(10)
"""
        ),
        markdown(
            """
`entry_high` 和 `exit_low` 使用 `shift(1)`，因此当日通道不包含当日最高价或最低价。真实波幅同时考虑日内波幅和相对昨收的跳空，ATR 使用 Wilder 递推平均。
"""
        ),
        markdown("### 3. 执行海龟策略和ATR风险定仓"),
        code(
            """
result, trades = run_backtest(prices, DEFAULT_PARAMS)
result.loc[result["execution"].ne("HOLD"), [
    "trade_date", "execution", "fill_price", "entry_high", "exit_low",
    "atr", "stop_price", "exit_reason", "exposure", "strategy_equity"
]].head(12)
"""
        ),
        markdown("### 4. 绘制价格、通道、止损和买卖信号"),
        code(
            """
buys = result["execution"].eq("BUY")
sells = result["execution"].eq("SELL")

fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True, gridspec_kw={"height_ratios": [2.2, 0.8]})
axes[0].plot(result["trade_date"], result["close"], color="#1f2937", linewidth=1.1, label="收盘价")
axes[0].plot(result["trade_date"], result["entry_high"], color="#2563eb", label="前20日最高通道")
axes[0].plot(result["trade_date"], result["exit_low"], color="#d97706", label="前10日最低通道")
axes[0].plot(result["trade_date"], result["stop_price"], color="#be123c", linestyle="--", label="2ATR止损线")
axes[0].scatter(result.loc[buys, "trade_date"], result.loc[buys, "fill_price"], marker="^", color="#0f766e", label="买入")
axes[0].scatter(result.loc[sells, "trade_date"], result.loc[sells, "fill_price"], marker="v", color="#be123c", label="卖出")
axes[0].set_title(f"{stock.stock_name} 海龟策略价格与交易信号")
axes[0].set_ylabel("价格（元）")
axes[0].legend(ncol=3)
axes[0].grid(alpha=0.3)

axes[1].plot(result["trade_date"], result["atr"], color="#7c3aed")
axes[1].set_title("Wilder ATR20")
axes[1].set_ylabel("ATR")
axes[1].set_xlabel("交易日期")
axes[1].grid(alpha=0.3)
plt.tight_layout()
plt.show()
"""
        ),
        markdown("### 5. 计算累计回报、MDD、夏普比率等指标"),
        code(
            """
metrics = summarize_backtest(result, trades)
pd.Series(metrics, name=parameter_label(DEFAULT_PARAMS))
"""
        ),
        markdown("### 6. 比较不同通道和止损参数的样本外表现"),
        code(
            """
comparison = pd.read_csv(ROOT / "Task4" / "outputs" / "parameter_comparison.csv")
stock_oos = comparison.loc[
    (comparison["ts_code"] == stock.ts_code) &
    (comparison["sample_period"] == "out_of_sample"),
    ["parameter", "cumulative_return", "max_drawdown", "sharpe_ratio", "completed_trades", "win_rate"]
].sort_values("sharpe_ratio", ascending=False)
stock_oos
"""
        ),
        markdown("## Checks\n\n下面独立重算关键公式，并检查信号时序、资金恒等式和指标范围。"),
        code(
            """
expected_upper = prices["high"].rolling(DEFAULT_PARAMS.entry_window).max().shift(1)
expected_lower = prices["low"].rolling(DEFAULT_PARAMS.exit_window).min().shift(1)
previous_close = prices["close"].shift(1)
expected_tr = pd.concat([
    prices["high"] - prices["low"],
    (prices["high"] - previous_close).abs(),
    (prices["low"] - previous_close).abs(),
], axis=1).max(axis=1)

np.testing.assert_allclose(result["entry_high"], expected_upper, equal_nan=True)
np.testing.assert_allclose(result["exit_low"], expected_lower, equal_nan=True)
np.testing.assert_allclose(result["true_range"], expected_tr, equal_nan=True)
np.testing.assert_allclose(result["strategy_equity"], result["cash"] + result["shares"] * result["close"], rtol=1e-10)
assert result.loc[:DEFAULT_PARAMS.entry_window - 1, "execution"].eq("HOLD").all()
assert result["drawdown"].between(-1, 0).all()
assert (result["transaction_cost"] >= 0).all()
assert set(result.loc[result["execution"].eq("SELL"), "exit_reason"]) <= {"ATR_STOP", "CHANNEL_EXIT"}

print("检查通过：通道错位、TR公式、资金恒等式、回撤范围和退出原因均符合预期。")
"""
        ),
        markdown(
            """
## Next Steps

1. 修改 `stock = UNIVERSE[0]`，比较不同股票和行业。
2. 修改 `PARAMETER_SETS`，观察短通道、长通道和不同ATR止损倍数的变化。
3. 优先比较2024年以后的样本外结果，同时检查最大回撤、交易次数和基准收益。
4. 进一步加入100股整手、涨跌停、滑点、停牌和组合级风险预算，使模型更接近A股实盘。
"""
        ),
    ]
    nbf.write(notebook, NOTEBOOK_PATH)
    return NOTEBOOK_PATH


if __name__ == "__main__":
    print(build_notebook())
