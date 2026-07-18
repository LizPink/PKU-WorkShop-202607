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
    DEFAULT_MAX_ALLOCATION,
    DEFAULT_PARAMS,
    DEFAULT_RISK_FRACTION,
    DEFAULT_TRANSACTION_COST,
    OUT_OF_SAMPLE_START,
    PARAMETER_SETS,
    TRADING_DAYS_PER_YEAR,
    UNIVERSE,
    StockSpec,
    TurtleParams,
    code_slug,
    parameter_label,
    parameter_slug,
)


TASK_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = TASK_DIR.parent
DATA_DIR = WORKSPACE_ROOT / "Task3" / "data"
OUTPUT_DIR = TASK_DIR / "outputs"
NUMERIC_INPUTS = ["open", "high", "low", "close", "vol", "amount"]

COLORS = {
    "price": "#1f2937",
    "upper": "#2563eb",
    "lower": "#d97706",
    "atr": "#7c3aed",
    "stop": "#be123c",
    "buy": "#0f766e",
    "sell": "#be123c",
    "strategy": "#2563eb",
    "benchmark": "#64748b",
    "drawdown": "#d97706",
}


def setup_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
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
    required = ["trade_date", *NUMERIC_INPUTS]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{spec.ts_code} 缺少字段: {missing}")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame[NUMERIC_INPUTS] = frame[NUMERIC_INPUTS].apply(pd.to_numeric, errors="coerce")
    frame = frame.sort_values("trade_date").drop_duplicates("trade_date").reset_index(drop=True)
    if frame[required].isna().any().any():
        raise ValueError(f"{spec.ts_code} 的日期或 OHLCV 关键字段存在缺失")
    if (frame[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"{spec.ts_code} 存在非正价格")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError(f"{spec.ts_code} 存在最高价小于其他价格的记录")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError(f"{spec.ts_code} 存在最低价大于其他价格的记录")
    return frame


def wilder_average(values: pd.Series, period: int) -> pd.Series:
    if period <= 0:
        raise ValueError("Wilder 平均周期必须为正整数")
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    output = np.full(len(numeric), np.nan, dtype=float)
    if len(numeric) < period:
        return pd.Series(output, index=values.index, name=values.name)
    first = numeric.iloc[:period]
    if first.isna().any():
        return pd.Series(output, index=values.index, name=values.name)
    output[period - 1] = float(first.mean())
    for index in range(period, len(numeric)):
        value = numeric.iloc[index]
        if pd.isna(value):
            output[index] = output[index - 1]
        else:
            output[index] = (output[index - 1] * (period - 1) + value) / period
    return pd.Series(output, index=values.index, name=values.name)


def add_turtle_indicators(prices: pd.DataFrame, params: TurtleParams) -> pd.DataFrame:
    if min(params.entry_window, params.exit_window, params.atr_window) <= 0:
        raise ValueError("通道和 ATR 周期必须为正整数")
    if params.exit_window >= params.entry_window:
        raise ValueError("离场通道周期必须小于入场通道周期")
    if params.stop_atr <= 0:
        raise ValueError("ATR 止损倍数必须大于 0")

    result = prices.copy()
    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["true_range"] = true_range
    result["atr"] = wilder_average(true_range, params.atr_window)

    # shift(1) 确保当日通道只使用上一交易日及更早的数据。
    result["entry_high"] = (
        result["high"].rolling(params.entry_window, min_periods=params.entry_window).max().shift(1)
    )
    result["exit_low"] = (
        result["low"].rolling(params.exit_window, min_periods=params.exit_window).min().shift(1)
    )
    result["entry_signal"] = (
        (result["close"] > result["entry_high"])
        & (result["close"].shift(1) <= result["entry_high"].shift(1))
        & result["atr"].notna()
    )
    result["channel_exit_signal"] = result["close"] < result["exit_low"]
    return result


def run_backtest(
    prices: pd.DataFrame,
    params: TurtleParams = DEFAULT_PARAMS,
    transaction_cost: float = DEFAULT_TRANSACTION_COST,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    risk_fraction: float = DEFAULT_RISK_FRACTION,
    max_allocation: float = DEFAULT_MAX_ALLOCATION,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if transaction_cost < 0:
        raise ValueError("交易成本不能为负")
    if initial_capital <= 0:
        raise ValueError("初始资金必须大于 0")
    if not 0 < risk_fraction <= 1:
        raise ValueError("单次风险比例必须位于 (0, 1]")
    if not 0 < max_allocation <= 1:
        raise ValueError("最大资金使用比例必须位于 (0, 1]")

    result = add_turtle_indicators(prices, params)
    row_count = len(result)
    cash_values = np.zeros(row_count)
    shares_values = np.zeros(row_count)
    equity_values = np.zeros(row_count)
    exposure_values = np.zeros(row_count)
    stop_values = np.full(row_count, np.nan)
    cost_values = np.zeros(row_count)
    turnover_values = np.zeros(row_count)
    executions = np.full(row_count, "HOLD", dtype=object)
    exit_reasons = np.full(row_count, "", dtype=object)
    fill_prices = np.full(row_count, np.nan)

    cash = float(initial_capital)
    shares = 0.0
    active_stop = float("nan")
    entry_price = float("nan")
    entry_atr = float("nan")
    entry_date: pd.Timestamp | None = None
    entry_index: int | None = None
    entry_value = 0.0
    entry_cost = 0.0
    trade_rows: list[dict[str, object]] = []

    for index, row in result.iterrows():
        open_price = float(row["open"])
        low_price = float(row["low"])
        close_price = float(row["close"])
        prior_equity = equity_values[index - 1] if index > 0 else initial_capital
        started_flat = shares == 0
        exited_today = False

        if index > 0 and shares > 0:
            prior = result.iloc[index - 1]
            exit_price: float | None = None
            exit_reason = ""
            if bool(prior["channel_exit_signal"]):
                exit_price = open_price
                exit_reason = "CHANNEL_EXIT"
            elif np.isfinite(active_stop) and low_price <= active_stop:
                exit_price = open_price if open_price <= active_stop else active_stop
                exit_reason = "ATR_STOP"

            if exit_price is not None:
                gross_proceeds = shares * exit_price
                exit_cost = gross_proceeds * transaction_cost
                cash += gross_proceeds - exit_cost
                cost_values[index] += exit_cost
                turnover_values[index] += gross_proceeds / prior_equity if prior_equity > 0 else 0.0
                executions[index] = "SELL"
                exit_reasons[index] = exit_reason
                fill_prices[index] = exit_price
                net_return = (gross_proceeds - exit_cost) / (entry_value + entry_cost) - 1
                trade_rows.append(
                    {
                        "entry_date": entry_date,
                        "exit_date": row["trade_date"],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "entry_atr": entry_atr,
                        "stop_price": active_stop,
                        "shares": shares,
                        "holding_days": index - int(entry_index),
                        "exit_reason": exit_reason,
                        "gross_return": exit_price / entry_price - 1,
                        "net_return": net_return,
                        "entry_cost": entry_cost,
                        "exit_cost": exit_cost,
                        "total_cost": entry_cost + exit_cost,
                    }
                )
                shares = 0.0
                active_stop = float("nan")
                entry_price = float("nan")
                entry_atr = float("nan")
                entry_date = None
                entry_index = None
                entry_value = 0.0
                entry_cost = 0.0
                exited_today = True

        if index > 0 and started_flat and not exited_today:
            prior = result.iloc[index - 1]
            signal_atr = float(prior["atr"]) if pd.notna(prior["atr"]) else float("nan")
            if bool(prior["entry_signal"]) and np.isfinite(signal_atr) and signal_atr > 0:
                stop_distance = params.stop_atr * signal_atr
                risk_quantity = (cash * risk_fraction) / stop_distance
                allocation_quantity = (cash * max_allocation) / (open_price * (1 + transaction_cost))
                quantity = min(risk_quantity, allocation_quantity)
                if quantity > 0:
                    entry_value = quantity * open_price
                    entry_cost = entry_value * transaction_cost
                    cash -= entry_value + entry_cost
                    shares = quantity
                    active_stop = open_price - stop_distance
                    entry_price = open_price
                    entry_atr = signal_atr
                    entry_date = row["trade_date"]
                    entry_index = index
                    cost_values[index] += entry_cost
                    turnover_values[index] += entry_value / prior_equity if prior_equity > 0 else 0.0
                    executions[index] = "BUY"
                    fill_prices[index] = open_price

        equity = cash + shares * close_price
        cash_values[index] = cash
        shares_values[index] = shares
        equity_values[index] = equity
        exposure_values[index] = shares * close_price / equity if equity > 0 else 0.0
        stop_values[index] = active_stop if shares > 0 else np.nan

    result["execution"] = executions
    result["exit_reason"] = exit_reasons
    result["fill_price"] = fill_prices
    result["cash"] = cash_values
    result["shares"] = shares_values
    result["position"] = (shares_values > 0).astype(int)
    result["exposure"] = exposure_values
    result["stop_price"] = stop_values
    result["transaction_cost"] = cost_values
    result["turnover"] = turnover_values
    result["strategy_equity"] = equity_values
    result["strategy_return"] = result["strategy_equity"].pct_change().fillna(
        result["strategy_equity"].iloc[0] / initial_capital - 1
    )
    result["market_return"] = result["close"].pct_change().fillna(0.0)
    result["benchmark_equity"] = initial_capital * (1 + result["market_return"]).cumprod()
    result["drawdown"] = result["strategy_equity"] / result["strategy_equity"].cummax() - 1
    result["entry_window"] = params.entry_window
    result["exit_window"] = params.exit_window
    result["atr_window"] = params.atr_window
    result["stop_atr"] = params.stop_atr
    result["risk_fraction"] = risk_fraction

    trades = pd.DataFrame(trade_rows)
    if not trades.empty:
        trades["entry_date"] = pd.to_datetime(trades["entry_date"])
        trades["exit_date"] = pd.to_datetime(trades["exit_date"])
    return result, trades


def summarize_backtest(
    result: pd.DataFrame,
    trades: pd.DataFrame,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, float | int]:
    subset = result
    if start_date is not None:
        subset = subset.loc[subset["trade_date"] >= pd.Timestamp(start_date)]
    if end_date is not None:
        subset = subset.loc[subset["trade_date"] <= pd.Timestamp(end_date)]
    if subset.empty:
        raise ValueError("没有可用于绩效计算的数据")

    returns = pd.to_numeric(subset["strategy_return"], errors="coerce").fillna(0.0)
    benchmark = pd.to_numeric(subset["market_return"], errors="coerce").fillna(0.0)
    periods = len(returns)
    equity = (1 + returns).cumprod()
    benchmark_equity = (1 + benchmark).cumprod()
    cumulative_return = float(equity.iloc[-1] - 1)
    benchmark_return = float(benchmark_equity.iloc[-1] - 1)
    years = periods / TRADING_DAYS_PER_YEAR
    annualized_return = (
        float(equity.iloc[-1] ** (1 / years) - 1)
        if years > 0 and equity.iloc[-1] > 0
        else float("nan")
    )
    daily_std = float(returns.std(ddof=1)) if periods > 1 else float("nan")
    annualized_volatility = daily_std * math.sqrt(TRADING_DAYS_PER_YEAR) if daily_std > 0 else 0.0
    sharpe_ratio = (
        float(returns.mean() / daily_std * math.sqrt(TRADING_DAYS_PER_YEAR))
        if daily_std > 0
        else float("nan")
    )
    drawdown = equity / equity.cummax() - 1

    completed = trades.copy()
    if not completed.empty:
        if start_date is not None:
            completed = completed.loc[completed["exit_date"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            completed = completed.loc[completed["exit_date"] <= pd.Timestamp(end_date)]

    trade_count = len(completed)
    win_rate = float((completed["net_return"] > 0).mean()) if trade_count else float("nan")
    average_holding_days = float(completed["holding_days"].mean()) if trade_count else float("nan")
    return {
        "observations": periods,
        "cumulative_return": cumulative_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": float(drawdown.min()),
        "benchmark_return": benchmark_return,
        "excess_return": cumulative_return - benchmark_return,
        "buy_count": int(subset["execution"].eq("BUY").sum()),
        "sell_count": int(subset["execution"].eq("SELL").sum()),
        "completed_trades": trade_count,
        "win_rate": win_rate,
        "average_holding_days": average_holding_days,
        "holding_ratio": float(subset["position"].mean()),
        "average_exposure": float(subset["exposure"].mean()),
        "total_transaction_cost": float(subset["transaction_cost"].sum()),
        "total_turnover": float(subset["turnover"].sum()),
        "atr_stop_exits": int(subset["exit_reason"].eq("ATR_STOP").sum()),
        "channel_exits": int(subset["exit_reason"].eq("CHANNEL_EXIT").sum()),
        "open_position_at_end": int(subset["position"].iloc[-1]),
    }


def plot_backtest(result: pd.DataFrame, spec: StockSpec, params: TurtleParams, output: Path) -> None:
    setup_plot_style()
    buys = result["execution"].eq("BUY")
    sells = result["execution"].eq("SELL")
    fig, axes = plt.subplots(
        4,
        1,
        figsize=(14, 12),
        sharex=True,
        gridspec_kw={"height_ratios": [2.4, 0.85, 1.15, 0.85]},
    )

    axes[0].plot(result["trade_date"], result["close"], color=COLORS["price"], linewidth=1.15, label="前复权收盘价")
    axes[0].plot(result["trade_date"], result["entry_high"], color=COLORS["upper"], linewidth=1.05, label=f"前{params.entry_window}日最高通道")
    axes[0].plot(result["trade_date"], result["exit_low"], color=COLORS["lower"], linewidth=1.05, label=f"前{params.exit_window}日最低通道")
    axes[0].plot(result["trade_date"], result["stop_price"], color=COLORS["stop"], linewidth=1.0, linestyle="--", label=f"{params.stop_atr:g}ATR止损线")
    axes[0].scatter(result.loc[buys, "trade_date"], result.loc[buys, "fill_price"], marker="^", s=48, color=COLORS["buy"], label="买入执行", zorder=4)
    axes[0].scatter(result.loc[sells, "trade_date"], result.loc[sells, "fill_price"], marker="v", s=48, color=COLORS["sell"], label="卖出执行", zorder=4)
    axes[0].set_ylabel("价格（元）")
    axes[0].legend(loc="upper left", ncol=3, fontsize=9)

    axes[1].plot(result["trade_date"], result["atr"], color=COLORS["atr"], linewidth=1.15)
    axes[1].set_ylabel(f"ATR{params.atr_window}")
    axes[1].set_title("平均真实波幅（Wilder ATR）", loc="left", fontsize=11)

    axes[2].plot(result["trade_date"], result["strategy_equity"] / result["strategy_equity"].iloc[0], color=COLORS["strategy"], linewidth=1.5, label="海龟策略")
    axes[2].plot(result["trade_date"], result["benchmark_equity"] / result["benchmark_equity"].iloc[0], color=COLORS["benchmark"], linewidth=1.2, linestyle="--", label="买入持有")
    axes[2].set_ylabel("归一化净值")
    axes[2].set_title("策略净值与买入持有基准", loc="left", fontsize=11)
    axes[2].legend(loc="upper left")

    axes[3].fill_between(result["trade_date"], result["drawdown"] * 100, 0, color=COLORS["drawdown"], alpha=0.28)
    axes[3].plot(result["trade_date"], result["drawdown"] * 100, color=COLORS["drawdown"], linewidth=1)
    axes[3].set_ylabel("回撤（%）")
    axes[3].set_xlabel("交易日期")
    axes[3].set_title("策略回撤", loc="left", fontsize=11)

    for axis in axes:
        axis.grid(True)
        axis.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"{spec.stock_name}（{spec.ts_code}）海龟交易策略", fontsize=15, y=0.995)
    fig.text(
        0.5,
        0.972,
        f"日线前复权｜{parameter_label(params)}｜1%账户风险定仓｜单边成本{DEFAULT_TRANSACTION_COST:.1%}",
        ha="center",
        va="top",
        fontsize=10,
        color="#475569",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(output, dpi=170, bbox_inches="tight")
    plt.close(fig)


def run_all_backtests() -> tuple[pd.DataFrame, pd.DataFrame]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, object]] = []

    for spec in UNIVERSE:
        prices = load_prices(spec)
        for params in PARAMETER_SETS:
            result, trades = run_backtest(prices, params=params)
            periods = {
                "full": (None, None),
                "in_sample": (None, "2023-12-31"),
                "out_of_sample": (OUT_OF_SAMPLE_START, None),
            }
            for sample_period, (start_date, end_date) in periods.items():
                metrics = summarize_backtest(result, trades, start_date, end_date)
                summary_rows.append(
                    {
                        "ts_code": spec.ts_code,
                        "stock_name": spec.stock_name,
                        "industry": spec.industry,
                        "parameter": parameter_label(params),
                        "entry_window": params.entry_window,
                        "exit_window": params.exit_window,
                        "atr_window": params.atr_window,
                        "stop_atr": params.stop_atr,
                        "sample_period": sample_period,
                        **metrics,
                    }
                )

            if params == DEFAULT_PARAMS:
                slug = f"{code_slug(spec.ts_code)}_{parameter_slug(params)}"
                result.to_csv(OUTPUT_DIR / f"{slug}_backtest.csv", index=False, encoding="utf-8-sig")
                trades.to_csv(OUTPUT_DIR / f"{slug}_trades.csv", index=False, encoding="utf-8-sig")
                plot_backtest(result, spec, params, OUTPUT_DIR / f"{slug}_strategy.png")

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUTPUT_DIR / "parameter_comparison.csv", index=False, encoding="utf-8-sig")
    default_summary = summary.loc[
        (summary["entry_window"] == DEFAULT_PARAMS.entry_window)
        & (summary["exit_window"] == DEFAULT_PARAMS.exit_window)
        & (summary["atr_window"] == DEFAULT_PARAMS.atr_window)
        & np.isclose(summary["stop_atr"], DEFAULT_PARAMS.stop_atr)
    ].copy()
    default_summary.to_csv(OUTPUT_DIR / "default_summary.csv", index=False, encoding="utf-8-sig")

    industry_summary = (
        summary.groupby(["industry", "parameter", "sample_period"], as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            median_cumulative_return=("cumulative_return", "median"),
            median_sharpe_ratio=("sharpe_ratio", "median"),
            median_max_drawdown=("max_drawdown", "median"),
            positive_return_share=("cumulative_return", lambda values: float((values > 0).mean())),
            median_completed_trades=("completed_trades", "median"),
            median_average_exposure=("average_exposure", "median"),
        )
    )
    industry_summary.to_csv(OUTPUT_DIR / "industry_parameter_summary.csv", index=False, encoding="utf-8-sig")
    return summary, industry_summary


if __name__ == "__main__":
    comparison, industries = run_all_backtests()
    print(f"Generated {len(comparison)} stock-parameter-period rows.")
    print(f"Generated {len(industries)} industry summary rows.")
