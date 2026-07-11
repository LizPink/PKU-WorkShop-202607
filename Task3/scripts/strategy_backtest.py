from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import (
    DEFAULT_INITIAL_CAPITAL,
    DEFAULT_LONG_WINDOW,
    DEFAULT_SHORT_WINDOW,
    DEFAULT_TRANSACTION_COST,
    CROSS_TOLERANCE,
    OUT_OF_SAMPLE_START,
    PARAMETER_PAIRS,
    TRADING_DAYS_PER_YEAR,
    UNIVERSE,
    StockSpec,
    code_slug,
    parameter_label,
)


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
OUTPUT_DIR = TASK_DIR / "outputs"
NUMERIC_INPUTS = ["open", "high", "low", "close", "vol", "amount"]
COLORS = {
    "price": "#1f2937",
    "short": "#2563eb",
    "long": "#d97706",
    "buy": "#0f766e",
    "sell": "#be123c",
    "strategy": "#2563eb",
    "benchmark": "#64748b",
    "drawdown": "#d97706",
}


def setup_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "#fbfdff"
    plt.rcParams["axes.edgecolor"] = "#cbd5e1"
    plt.rcParams["grid.color"] = "#cbd5e1"
    plt.rcParams["grid.alpha"] = 0.35


def data_path(spec: StockSpec) -> Path:
    return DATA_DIR / f"{code_slug(spec.ts_code)}_daily_qfq.csv"


def load_prices(spec: StockSpec) -> pd.DataFrame:
    path = data_path(spec)
    if not path.exists():
        raise FileNotFoundError(f"缺少行情文件: {path}")
    frame = pd.read_csv(path)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame[NUMERIC_INPUTS] = frame[NUMERIC_INPUTS].apply(pd.to_numeric, errors="coerce")
    frame = frame.sort_values("trade_date").drop_duplicates("trade_date").reset_index(drop=True)
    if frame[NUMERIC_INPUTS + ["trade_date"]].isna().any().any():
        raise ValueError(f"{spec.ts_code} 存在关键字段缺失")
    return frame


def run_backtest(
    prices: pd.DataFrame,
    short_window: int = DEFAULT_SHORT_WINDOW,
    long_window: int = DEFAULT_LONG_WINDOW,
    transaction_cost: float = DEFAULT_TRANSACTION_COST,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
) -> pd.DataFrame:
    if short_window <= 0 or long_window <= 0 or short_window >= long_window:
        raise ValueError("均线周期必须满足 0 < short_window < long_window")
    if transaction_cost < 0:
        raise ValueError("交易成本不能为负")

    result = prices.copy()
    result["short_ma"] = result["close"].rolling(short_window, min_periods=short_window).mean()
    result["long_ma"] = result["close"].rolling(long_window, min_periods=long_window).mean()
    valid_signal = result["short_ma"].notna() & result["long_ma"].notna()
    result["target_position"] = np.where(
        valid_signal & (result["short_ma"] > result["long_ma"] + CROSS_TOLERANCE), 1, 0
    )

    target_change = result["target_position"].diff().fillna(result["target_position"])
    result["signal"] = np.select(
        [target_change.eq(1), target_change.eq(-1)],
        ["BUY", "SELL"],
        default="HOLD",
    )

    # t 日收盘生成目标仓位，t+1 日才应用；避免把当日已经发生的收益算入策略。
    result["position"] = result["target_position"].shift(1).fillna(0).astype(int)
    position_change = result["position"].diff().fillna(result["position"])
    result["execution"] = np.select(
        [position_change.eq(1), position_change.eq(-1)],
        ["BUY", "SELL"],
        default="HOLD",
    )

    result["market_return"] = result["close"].pct_change().fillna(0.0)
    result["gross_strategy_return"] = result["position"] * result["market_return"]
    result["turnover"] = position_change.abs()
    result["transaction_cost"] = result["turnover"] * transaction_cost
    result["strategy_return"] = result["gross_strategy_return"] - result["transaction_cost"]
    result["strategy_equity"] = initial_capital * (1 + result["strategy_return"]).cumprod()
    result["benchmark_equity"] = initial_capital * (1 + result["market_return"]).cumprod()
    result["drawdown"] = result["strategy_equity"] / result["strategy_equity"].cummax() - 1
    result["short_window"] = short_window
    result["long_window"] = long_window
    return result


def metrics_from_returns(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    positions: pd.Series,
    executions: pd.Series,
    costs: pd.Series,
) -> dict[str, float | int]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    benchmark = pd.to_numeric(benchmark_returns, errors="coerce").fillna(0.0)
    periods = len(clean)
    if periods == 0:
        raise ValueError("没有可用于绩效计算的收益数据")

    equity = (1 + clean).cumprod()
    benchmark_equity = (1 + benchmark).cumprod()
    cumulative_return = float(equity.iloc[-1] - 1)
    benchmark_return = float(benchmark_equity.iloc[-1] - 1)
    years = periods / TRADING_DAYS_PER_YEAR
    annualized_return = float(equity.iloc[-1] ** (1 / years) - 1) if years > 0 and equity.iloc[-1] > 0 else float("nan")
    annualized_volatility = float(clean.std(ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR)) if periods > 1 else float("nan")
    daily_std = clean.std(ddof=1)
    sharpe_ratio = float(clean.mean() / daily_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if periods > 1 and daily_std > 0 else float("nan")
    drawdown = equity / equity.cummax() - 1
    max_drawdown = float(drawdown.min())
    buy_count = int(executions.eq("BUY").sum())
    sell_count = int(executions.eq("SELL").sum())
    return {
        "observations": periods,
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "benchmark_return": benchmark_return,
        "excess_return": cumulative_return - benchmark_return,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "holding_ratio": float(pd.to_numeric(positions, errors="coerce").fillna(0).mean()),
        "total_cost_rate": float(pd.to_numeric(costs, errors="coerce").fillna(0).sum()),
    }


def summarize_backtest(result: pd.DataFrame, start_date: str | None = None, end_date: str | None = None) -> dict[str, float | int]:
    subset = result
    if start_date is not None:
        subset = subset.loc[subset["trade_date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        subset = subset.loc[subset["trade_date"] <= pd.Timestamp(end_date)]
    return metrics_from_returns(
        subset["strategy_return"],
        subset["market_return"],
        subset["position"],
        subset["execution"],
        subset["transaction_cost"],
    )


def plot_backtest(result: pd.DataFrame, spec: StockSpec, output: Path) -> None:
    setup_plot_style()
    buys = result["execution"].eq("BUY")
    sells = result["execution"].eq("SELL")
    short_window = int(result["short_window"].iloc[0])
    long_window = int(result["long_window"].iloc[0])
    fig, axes = plt.subplots(
        3,
        1,
        figsize=(13.5, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [2.25, 1.25, 0.85]},
    )

    axes[0].plot(result["trade_date"], result["close"], color=COLORS["price"], linewidth=1.25, label="前复权收盘价")
    axes[0].plot(result["trade_date"], result["short_ma"], color=COLORS["short"], linewidth=1.2, label=f"MA{short_window}")
    axes[0].plot(result["trade_date"], result["long_ma"], color=COLORS["long"], linewidth=1.2, label=f"MA{long_window}")
    axes[0].scatter(result.loc[buys, "trade_date"], result.loc[buys, "close"], marker="^", s=48, color=COLORS["buy"], label="买入执行", zorder=4)
    axes[0].scatter(result.loc[sells, "trade_date"], result.loc[sells, "close"], marker="v", s=48, color=COLORS["sell"], label="卖出执行", zorder=4)
    axes[0].set_title(f"{spec.stock_name}（{spec.ts_code}）双均线交易信号")
    axes[0].set_ylabel("价格（元）")
    axes[0].legend(loc="upper left", ncol=5, fontsize=9)

    normalized_strategy = result["strategy_equity"] / result["strategy_equity"].iloc[0]
    normalized_benchmark = result["benchmark_equity"] / result["benchmark_equity"].iloc[0]
    axes[1].plot(result["trade_date"], normalized_strategy, color=COLORS["strategy"], linewidth=1.5, label="双均线策略净值")
    axes[1].plot(result["trade_date"], normalized_benchmark, color=COLORS["benchmark"], linewidth=1.25, linestyle="--", label="买入持有净值")
    axes[1].set_title("策略净值与买入持有基准")
    axes[1].set_ylabel("归一化净值")
    axes[1].legend(loc="upper left")

    axes[2].fill_between(result["trade_date"], result["drawdown"] * 100, 0, color=COLORS["drawdown"], alpha=0.32)
    axes[2].plot(result["trade_date"], result["drawdown"] * 100, color=COLORS["drawdown"], linewidth=1)
    axes[2].set_title("策略回撤")
    axes[2].set_ylabel("回撤（%）")
    axes[2].set_xlabel("交易日期")

    for axis in axes:
        axis.grid(True)
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        f"{spec.industry}｜{parameter_label(short_window, long_window)}｜信号次日生效｜单边成本 {DEFAULT_TRANSACTION_COST:.2%}",
        fontsize=14,
        y=0.995,
    )
    fig.tight_layout()
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)


def run_all_backtests() -> tuple[pd.DataFrame, pd.DataFrame]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []

    for spec in UNIVERSE:
        prices = load_prices(spec)
        for short_window, long_window in PARAMETER_PAIRS:
            result = run_backtest(prices, short_window, long_window)
            pair = parameter_label(short_window, long_window)
            periods = {
                "全样本": (None, None),
                "样本内": (None, "2023-12-31"),
                "样本外": (OUT_OF_SAMPLE_START, None),
            }
            for sample_period, (start_date, end_date) in periods.items():
                metrics = summarize_backtest(result, start_date, end_date)
                summary_rows.append(
                    {
                        "ts_code": spec.ts_code,
                        "stock_name": spec.stock_name,
                        "industry": spec.industry,
                        "parameter": pair,
                        "short_window": short_window,
                        "long_window": long_window,
                        "sample_period": sample_period,
                        **metrics,
                    }
                )

            if (short_window, long_window) == (DEFAULT_SHORT_WINDOW, DEFAULT_LONG_WINDOW):
                result_path = OUTPUT_DIR / f"{code_slug(spec.ts_code)}_MA5_MA15_backtest.csv"
                chart_path = OUTPUT_DIR / f"{code_slug(spec.ts_code)}_MA5_MA15_strategy.png"
                result.to_csv(result_path, index=False, encoding="utf-8-sig")
                plot_backtest(result, spec, chart_path)

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUTPUT_DIR / "parameter_comparison.csv", index=False, encoding="utf-8-sig")

    industry_summary = (
        summary.groupby(["industry", "parameter", "sample_period"], as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            median_cumulative_return=("cumulative_return", "median"),
            median_sharpe_ratio=("sharpe_ratio", "median"),
            median_max_drawdown=("max_drawdown", "median"),
            positive_return_share=("cumulative_return", lambda values: float((values > 0).mean())),
            median_buy_count=("buy_count", "median"),
        )
    )
    industry_summary.to_csv(OUTPUT_DIR / "industry_parameter_summary.csv", index=False, encoding="utf-8-sig")
    return summary, industry_summary


if __name__ == "__main__":
    comparison, industries = run_all_backtests()
    print(f"Generated {len(comparison)} stock-parameter-period rows.")
    print(f"Generated {len(industries)} industry summary rows.")
