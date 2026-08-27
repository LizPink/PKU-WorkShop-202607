from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
TASK7_DIR = ROOT / "TASK7"
SOURCE_DIR = ROOT / "Task3" / "data"
DATA_DIR = TASK7_DIR / "data"
OUTPUT_DIR = TASK7_DIR / "outputs"

INITIAL_CASH = 1_000_000.0
DEVELOPMENT_START = pd.Timestamp("2020-01-01")
DEVELOPMENT_END = pd.Timestamp("2023-12-31")
VALIDATION_START = pd.Timestamp("2024-01-01")
VALIDATION_END = pd.Timestamp("2025-12-31")
PAPER_START = pd.Timestamp("2026-01-01")
PAPER_END = pd.Timestamp("2026-07-10")


@dataclass(frozen=True)
class StrategyParams:
    momentum_window: int
    trend_window: int
    top_n: int
    stop_loss: float
    volatility_window: int = 20
    target_exposure: float = 0.90
    max_weight: float = 0.40

    @property
    def label(self) -> str:
        return (
            f"M{self.momentum_window}/T{self.trend_window}/"
            f"N{self.top_n}/S{int(round(self.stop_loss * 100))}"
        )


@dataclass(frozen=True)
class CostModel:
    commission: float = 0.0003
    sell_tax: float = 0.0005
    min_commission: float = 5.0
    price_spread: float = 0.002


BASELINE_PARAMS = StrategyParams(
    momentum_window=60,
    trend_window=120,
    top_n=3,
    stop_loss=0.12,
)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def jq_code(ts_code: str) -> str:
    number, suffix = ts_code.split(".")
    return f"{number}.XSHE" if suffix == "SZ" else f"{number}.XSHG"


def load_market_data() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    universe = pd.read_csv(SOURCE_DIR / "universe.csv")
    market: dict[str, pd.DataFrame] = {}
    for row in universe.itertuples(index=False):
        frame = pd.read_csv(SOURCE_DIR / row.file)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        frame = (
            frame.set_index("trade_date")
            .sort_index()
            .loc[:, ["open", "high", "low", "close", "vol", "amount"]]
            .apply(pd.to_numeric, errors="coerce")
        )
        market[row.ts_code] = frame

    metadata = universe.loc[:, ["ts_code", "stock_name", "industry", "price_type", "source"]].copy()
    metadata["joinquant_code"] = metadata["ts_code"].map(jq_code)
    metadata.to_csv(DATA_DIR / "strategy_universe.csv", index=False, encoding="utf-8-sig")
    return market, metadata


def build_panels(market: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    calendar = sorted(set().union(*(frame.index for frame in market.values())))
    index = pd.DatetimeIndex(calendar, name="trade_date")
    panels: dict[str, pd.DataFrame] = {}
    for field in ("open", "high", "low", "close", "vol", "amount"):
        panels[field] = pd.DataFrame(
            {symbol: frame[field].reindex(index) for symbol, frame in market.items()},
            index=index,
        )
    panels["tradable"] = panels["open"].notna() & panels["close"].notna()
    panels["close_filled"] = panels["close"].ffill()
    panels["high_filled"] = panels["high"].fillna(panels["close"]).ffill()
    return panels


def first_trading_days(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    marker = pd.Series(index=index, data=index.to_period("M"))
    return set(marker.groupby(marker).head(1).index)


def capped_inverse_vol_weights(
    symbols: list[str],
    volatility: pd.Series,
    *,
    target_exposure: float,
    max_weight: float,
) -> dict[str, float]:
    if not symbols:
        return {}
    inv = 1.0 / volatility.reindex(symbols).replace(0, np.nan)
    inv = inv.replace([np.inf, -np.inf], np.nan).fillna(inv.dropna().median() if inv.notna().any() else 1.0)
    raw = inv / inv.sum() * target_exposure

    weights = pd.Series(0.0, index=symbols)
    remaining = set(symbols)
    remaining_exposure = target_exposure
    remaining_raw = raw.copy()
    while remaining:
        alloc = remaining_raw.loc[list(remaining)]
        alloc = alloc / alloc.sum() * remaining_exposure
        capped = alloc[alloc > max_weight]
        if capped.empty:
            weights.loc[alloc.index] = alloc
            break
        for symbol in capped.index:
            weights.loc[symbol] = max_weight
            remaining.remove(symbol)
            remaining_exposure -= max_weight
        if remaining_exposure <= 1e-12:
            break
    return weights.to_dict()


def fee_for_trade(value: float, side: str, cost: CostModel) -> float:
    commission = max(abs(value) * cost.commission, cost.min_commission)
    tax = abs(value) * cost.sell_tax if side == "sell" else 0.0
    return commission + tax


def metric_block(
    daily: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float | int | str]:
    sample = daily.loc[(daily.index >= start) & (daily.index <= end)].copy()
    if sample.empty:
        raise ValueError(f"No observations between {start.date()} and {end.date()}")
    strategy_returns = sample["strategy_return"].fillna(0.0)
    benchmark_returns = sample["benchmark_return"].fillna(0.0)
    n = len(sample)
    years = n / 252.0
    total = float((1.0 + strategy_returns).prod() - 1.0)
    benchmark_total = float((1.0 + benchmark_returns).prod() - 1.0)
    annual = float((1.0 + total) ** (1.0 / years) - 1.0) if years > 0 and total > -1 else np.nan
    benchmark_annual = (
        float((1.0 + benchmark_total) ** (1.0 / years) - 1.0)
        if years > 0 and benchmark_total > -1
        else np.nan
    )
    vol = float(strategy_returns.std(ddof=1) * np.sqrt(252))
    benchmark_vol = float(benchmark_returns.std(ddof=1) * np.sqrt(252))
    sharpe = float(strategy_returns.mean() / strategy_returns.std(ddof=1) * np.sqrt(252)) if strategy_returns.std(ddof=1) > 0 else np.nan
    downside = strategy_returns[strategy_returns < 0].std(ddof=1)
    sortino = float(strategy_returns.mean() / downside * np.sqrt(252)) if downside and downside > 0 else np.nan
    nav = (1.0 + strategy_returns).cumprod()
    drawdown = nav / nav.cummax() - 1.0
    max_drawdown = float(drawdown.min())
    calmar = float(annual / abs(max_drawdown)) if max_drawdown < 0 and pd.notna(annual) else np.nan
    active = strategy_returns - benchmark_returns
    tracking_error = float(active.std(ddof=1) * np.sqrt(252))
    information_ratio = float(active.mean() / active.std(ddof=1) * np.sqrt(252)) if active.std(ddof=1) > 0 else np.nan
    variance = float(benchmark_returns.var(ddof=1))
    beta = float(strategy_returns.cov(benchmark_returns) / variance) if variance > 0 else np.nan
    var_95 = float(strategy_returns.quantile(0.05))
    tail = strategy_returns[strategy_returns <= var_95]
    cvar_95 = float(tail.mean()) if not tail.empty else np.nan

    return {
        "start_date": sample.index.min().date().isoformat(),
        "end_date": sample.index.max().date().isoformat(),
        "observations": n,
        "cumulative_return": total,
        "annualized_return": annual,
        "annualized_volatility": vol,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar,
        "benchmark_return": benchmark_total,
        "benchmark_annualized_return": benchmark_annual,
        "benchmark_volatility": benchmark_vol,
        "excess_return": total - benchmark_total,
        "tracking_error": tracking_error,
        "information_ratio": information_ratio,
        "beta": beta,
        "daily_var_95": var_95,
        "daily_cvar_95": cvar_95,
        "positive_day_ratio": float((strategy_returns > 0).mean()),
        "average_exposure": float(sample["exposure"].mean()),
        "max_exposure": float(sample["exposure"].max()),
        "average_cash_ratio": float(sample["cash_ratio"].mean()),
        "annual_turnover": float(sample["turnover"].sum() / years) if years > 0 else np.nan,
        "transaction_cost": float(sample["transaction_cost"].sum()),
    }


def backtest(
    panels: dict[str, pd.DataFrame],
    params: StrategyParams,
    *,
    cost: CostModel = CostModel(),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    open_px = panels["open"]
    high_px = panels["high_filled"]
    close_px = panels["close_filled"]
    tradable = panels["tradable"]
    symbols = list(close_px.columns)
    calendar = close_px.index
    rebalances = first_trading_days(calendar)

    cash = INITIAL_CASH
    shares = pd.Series(0, index=symbols, dtype="int64")
    avg_cost = pd.Series(np.nan, index=symbols, dtype="float64")
    peak = pd.Series(np.nan, index=symbols, dtype="float64")
    entry_date: dict[str, pd.Timestamp] = {}
    rows: list[dict[str, float | str]] = []
    holdings_rows: list[dict[str, float | str]] = []
    trades: list[dict[str, float | str | int]] = []
    previous_close_value = INITIAL_CASH
    benchmark_nav = 1.0

    returns = close_px.pct_change(fill_method=None)
    benchmark_daily = returns.mean(axis=1, skipna=True).fillna(0.0)

    warmup = max(params.momentum_window + 1, params.trend_window, params.volatility_window + 1)

    for i, date in enumerate(calendar):
        day_open = open_px.loc[date]
        day_close = close_px.loc[date]
        day_high = high_px.loc[date]
        day_tradable = tradable.loc[date]
        open_mark = day_open.fillna(day_close)
        portfolio_at_open = float(cash + (shares * open_mark).sum())
        total_cost = 0.0
        total_turnover = 0.0
        stopped_today: set[str] = set()

        if i > 0:
            previous_close = close_px.iloc[i - 1]
            for symbol in symbols:
                if shares[symbol] <= 0 or not day_tradable[symbol]:
                    continue
                peak[symbol] = max(float(peak[symbol]), float(high_px.iloc[i - 1][symbol]))
                if float(previous_close[symbol]) <= float(peak[symbol]) * (1.0 - params.stop_loss):
                    execution_price = float(day_open[symbol]) * (1.0 - cost.price_spread / 2.0)
                    quantity = int(shares[symbol])
                    gross = quantity * execution_price
                    trade_fee = fee_for_trade(gross, "sell", cost)
                    cash += gross - trade_fee
                    realized_return = execution_price / float(avg_cost[symbol]) - 1.0 if pd.notna(avg_cost[symbol]) else np.nan
                    trades.append(
                        {
                            "trade_date": date.date().isoformat(),
                            "symbol": symbol,
                            "side": "sell",
                            "quantity": quantity,
                            "execution_price": execution_price,
                            "gross_value": gross,
                            "fee": trade_fee,
                            "reason": "trailing_stop",
                            "realized_return": realized_return,
                            "holding_days": (date - entry_date.get(symbol, date)).days,
                        }
                    )
                    shares[symbol] = 0
                    avg_cost[symbol] = np.nan
                    peak[symbol] = np.nan
                    entry_date.pop(symbol, None)
                    total_cost += trade_fee
                    total_turnover += gross
                    stopped_today.add(symbol)

        if date in rebalances and i >= warmup:
            hist = close_px.iloc[:i]
            last = hist.iloc[-1]
            momentum = last / hist.iloc[-(params.momentum_window + 1)] - 1.0
            trend = hist.tail(params.trend_window).mean()
            recent_returns = hist.pct_change(fill_method=None).tail(params.volatility_window)
            volatility = recent_returns.std(ddof=1) * np.sqrt(252)
            eligible = (
                (momentum > 0)
                & (last > trend)
                & volatility.notna()
                & (volatility > 0)
                & day_tradable
            )
            ranked = momentum[eligible].sort_values(ascending=False)
            selected = [symbol for symbol in ranked.index[: params.top_n] if symbol not in stopped_today]
            target_weights = capped_inverse_vol_weights(
                selected,
                volatility,
                target_exposure=params.target_exposure,
                max_weight=params.max_weight,
            )

            portfolio_at_open = float(cash + (shares * open_mark).sum())
            target_shares = pd.Series(0, index=symbols, dtype="int64")
            for symbol, weight in target_weights.items():
                if day_tradable[symbol] and day_open[symbol] > 0:
                    target_value = portfolio_at_open * weight
                    buy_price = float(day_open[symbol]) * (1.0 + cost.price_spread / 2.0)
                    target_shares[symbol] = int(math.floor(target_value / buy_price / 100.0) * 100)

            for symbol in symbols:
                quantity = int(max(shares[symbol] - target_shares[symbol], 0))
                if quantity <= 0 or not day_tradable[symbol]:
                    continue
                execution_price = float(day_open[symbol]) * (1.0 - cost.price_spread / 2.0)
                gross = quantity * execution_price
                trade_fee = fee_for_trade(gross, "sell", cost)
                cash += gross - trade_fee
                realized_return = execution_price / float(avg_cost[symbol]) - 1.0 if pd.notna(avg_cost[symbol]) else np.nan
                reason = "rebalance_exit" if target_shares[symbol] == 0 else "rebalance_reduce"
                trades.append(
                    {
                        "trade_date": date.date().isoformat(),
                        "symbol": symbol,
                        "side": "sell",
                        "quantity": quantity,
                        "execution_price": execution_price,
                        "gross_value": gross,
                        "fee": trade_fee,
                        "reason": reason,
                        "realized_return": realized_return,
                        "holding_days": (date - entry_date.get(symbol, date)).days,
                    }
                )
                shares[symbol] -= quantity
                if shares[symbol] == 0:
                    avg_cost[symbol] = np.nan
                    peak[symbol] = np.nan
                    entry_date.pop(symbol, None)
                total_cost += trade_fee
                total_turnover += gross

            for symbol in selected:
                quantity = int(max(target_shares[symbol] - shares[symbol], 0))
                if quantity <= 0 or not day_tradable[symbol]:
                    continue
                execution_price = float(day_open[symbol]) * (1.0 + cost.price_spread / 2.0)
                gross = quantity * execution_price
                trade_fee = fee_for_trade(gross, "buy", cost)
                if gross + trade_fee > cash:
                    affordable = int(math.floor(max(cash - cost.min_commission, 0.0) / execution_price / 100.0) * 100)
                    quantity = min(quantity, affordable)
                    gross = quantity * execution_price
                    trade_fee = fee_for_trade(gross, "buy", cost) if quantity > 0 else 0.0
                if quantity <= 0:
                    continue
                old_quantity = int(shares[symbol])
                old_cost_value = 0.0 if old_quantity == 0 or pd.isna(avg_cost[symbol]) else old_quantity * float(avg_cost[symbol])
                cash -= gross + trade_fee
                shares[symbol] += quantity
                avg_cost[symbol] = (old_cost_value + gross + trade_fee) / shares[symbol]
                if old_quantity == 0:
                    entry_date[symbol] = date
                    peak[symbol] = float(day_high[symbol])
                else:
                    peak[symbol] = max(float(peak[symbol]), float(day_high[symbol]))
                trades.append(
                    {
                        "trade_date": date.date().isoformat(),
                        "symbol": symbol,
                        "side": "buy",
                        "quantity": quantity,
                        "execution_price": execution_price,
                        "gross_value": gross,
                        "fee": trade_fee,
                        "reason": "rebalance_entry" if old_quantity == 0 else "rebalance_add",
                        "realized_return": np.nan,
                        "holding_days": 0,
                    }
                )
                total_cost += trade_fee
                total_turnover += gross

        for symbol in symbols:
            if shares[symbol] > 0:
                peak[symbol] = max(
                    float(peak[symbol]) if pd.notna(peak[symbol]) else float(day_high[symbol]),
                    float(day_high[symbol]),
                )

        holding_values = shares.astype(float) * day_close
        close_value = float(cash + holding_values.sum())
        strategy_return = close_value / previous_close_value - 1.0 if rows else 0.0
        benchmark_return = float(benchmark_daily.loc[date]) if rows else 0.0
        benchmark_nav *= 1.0 + benchmark_return
        gross_exposure = float(holding_values.sum() / close_value) if close_value > 0 else 0.0
        cash_ratio = float(cash / close_value) if close_value > 0 else 0.0

        rows.append(
            {
                "trade_date": date,
                "portfolio_value": close_value,
                "strategy_return": strategy_return,
                "strategy_nav": close_value / INITIAL_CASH,
                "benchmark_return": benchmark_return,
                "benchmark_nav": benchmark_nav,
                "exposure": gross_exposure,
                "cash_ratio": cash_ratio,
                "turnover": total_turnover / previous_close_value if previous_close_value > 0 else 0.0,
                "transaction_cost": total_cost,
                "holding_count": int((shares > 0).sum()),
            }
        )
        for symbol in symbols:
            if shares[symbol] > 0:
                holdings_rows.append(
                    {
                        "trade_date": date.date().isoformat(),
                        "symbol": symbol,
                        "shares": int(shares[symbol]),
                        "close": float(day_close[symbol]),
                        "market_value": float(holding_values[symbol]),
                        "weight": float(holding_values[symbol] / close_value),
                    }
                )
        previous_close_value = close_value

    daily = pd.DataFrame(rows).set_index("trade_date")
    trades_df = pd.DataFrame(trades)
    holdings_df = pd.DataFrame(holdings_rows)
    return daily, trades_df, holdings_df


def period_metrics(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float | int | str]:
    metrics = metric_block(daily, start, end)
    metrics["period"] = label
    if trades.empty:
        period_trades = trades
    else:
        trade_dates = pd.to_datetime(trades["trade_date"])
        period_trades = trades.loc[(trade_dates >= start) & (trade_dates <= end)].copy()
    sells = period_trades.loc[period_trades["side"] == "sell"] if not period_trades.empty else period_trades
    realized = pd.to_numeric(sells.get("realized_return", pd.Series(dtype=float)), errors="coerce").dropna()
    metrics["trade_orders"] = int(len(period_trades))
    metrics["sell_events"] = int(len(sells))
    metrics["win_rate"] = float((realized > 0).mean()) if not realized.empty else np.nan
    metrics["average_holding_days"] = (
        float(pd.to_numeric(sells["holding_days"], errors="coerce").mean())
        if not sells.empty
        else np.nan
    )
    metrics["stop_exit_share"] = (
        float((sells["reason"] == "trailing_stop").mean()) if not sells.empty else np.nan
    )
    return metrics


def parameter_grid() -> Iterable[StrategyParams]:
    for momentum in (20, 60, 120):
        for trend in (60, 120, 200):
            for top_n in (2, 3, 4):
                for stop in (0.08, 0.12, 0.16):
                    yield StrategyParams(momentum, trend, top_n, stop)


def run_parameter_search(panels: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, StrategyParams]:
    records: list[dict[str, float | int | str]] = []
    for params in parameter_grid():
        daily, trades, _ = backtest(panels, params)
        development = period_metrics(
            daily,
            trades,
            "development",
            DEVELOPMENT_START,
            DEVELOPMENT_END,
        )
        validation = period_metrics(
            daily,
            trades,
            "validation",
            VALIDATION_START,
            VALIDATION_END,
        )
        paper = period_metrics(daily, trades, "paper_observation", PAPER_START, PAPER_END)
        row: dict[str, float | int | str] = {
            "parameter": params.label,
            "momentum_window": params.momentum_window,
            "trend_window": params.trend_window,
            "top_n": params.top_n,
            "stop_loss": params.stop_loss,
        }
        for prefix, block in (
            ("development", development),
            ("validation", validation),
            ("paper", paper),
        ):
            for field in (
                "cumulative_return",
                "annualized_return",
                "annualized_volatility",
                "sharpe_ratio",
                "max_drawdown",
                "excess_return",
                "annual_turnover",
                "average_exposure",
                "trade_orders",
            ):
                row[f"{prefix}_{field}"] = block[field]
        records.append(row)

    results = pd.DataFrame(records)
    eligible = results.loc[
        (results["development_trade_orders"] >= 10)
        & (results["development_sharpe_ratio"] > 0)
        & (results["development_max_drawdown"] > -0.55)
        & (results["validation_max_drawdown"] > -0.30)
    ].copy()
    eligible["selection_score"] = eligible["validation_sharpe_ratio"]
    winner = eligible.sort_values(
        ["selection_score", "validation_max_drawdown", "validation_annual_turnover"],
        ascending=[False, False, True],
    ).iloc[0]
    chosen = StrategyParams(
        momentum_window=int(winner["momentum_window"]),
        trend_window=int(winner["trend_window"]),
        top_n=int(winner["top_n"]),
        stop_loss=float(winner["stop_loss"]),
    )
    results["shortlisted"] = results["parameter"].isin(eligible["parameter"])
    results["selected"] = results["parameter"] == chosen.label
    return results.sort_values(
        ["selected", "validation_sharpe_ratio"],
        ascending=[False, False],
    ), chosen


def cost_sensitivity(
    panels: dict[str, pd.DataFrame],
    params: StrategyParams,
) -> pd.DataFrame:
    rows = []
    for label, multiplier in (("0.5倍成本", 0.5), ("基准成本", 1.0), ("2倍成本", 2.0)):
        model = CostModel(
            commission=0.0003 * multiplier,
            sell_tax=0.0005 * multiplier,
            min_commission=5.0,
            price_spread=0.002 * multiplier,
        )
        daily, trades, _ = backtest(panels, params, cost=model)
        metrics = period_metrics(
            daily,
            trades,
            "validation_plus_paper",
            VALIDATION_START,
            PAPER_END,
        )
        rows.append(
            {
                "scenario": label,
                "multiplier": multiplier,
                "cumulative_return": metrics["cumulative_return"],
                "annualized_return": metrics["annualized_return"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "transaction_cost": metrics["transaction_cost"],
                "annual_turnover": metrics["annual_turnover"],
            }
        )
    return pd.DataFrame(rows)


def exposure_summary(
    holdings: pd.DataFrame,
    metadata: pd.DataFrame,
    daily: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if holdings.empty:
        return pd.DataFrame(), pd.DataFrame()
    paper_dates = daily.loc[
        (daily.index >= PAPER_START) & (daily.index <= PAPER_END)
    ].index
    paper = holdings.loc[
        (pd.to_datetime(holdings["trade_date"]) >= PAPER_START)
        & (pd.to_datetime(holdings["trade_date"]) <= PAPER_END)
    ].copy()
    paper = paper.merge(metadata.loc[:, ["ts_code", "stock_name", "industry"]], left_on="symbol", right_on="ts_code", how="left")
    paper["trade_date"] = pd.to_datetime(paper["trade_date"])
    stock_matrix = (
        paper.pivot_table(index="trade_date", columns="symbol", values="weight", aggfunc="sum")
        .reindex(paper_dates)
        .fillna(0.0)
    )
    stock_lookup = metadata.set_index("ts_code")
    stock_rows = []
    for symbol in stock_matrix.columns:
        series = stock_matrix[symbol]
        stock_rows.append(
            {
                "symbol": symbol,
                "stock_name": stock_lookup.loc[symbol, "stock_name"],
                "industry": stock_lookup.loc[symbol, "industry"],
                "average_weight": float(series.mean()),
                "active_day_average_weight": float(series[series > 0].mean()),
                "max_weight": float(series.max()),
                "holding_days": int((series > 0).sum()),
            }
        )
    stock = pd.DataFrame(stock_rows).sort_values("average_weight", ascending=False)

    industry_daily = paper.groupby(["trade_date", "industry"], as_index=False)["weight"].sum()
    industry_matrix = (
        industry_daily.pivot(index="trade_date", columns="industry", values="weight")
        .reindex(paper_dates)
        .fillna(0.0)
    )
    industry_rows = []
    for industry_name in industry_matrix.columns:
        series = industry_matrix[industry_name]
        industry_rows.append(
            {
                "industry": industry_name,
                "average_weight": float(series.mean()),
                "active_day_average_weight": float(series[series > 0].mean()),
                "max_weight": float(series.max()),
                "holding_days": int((series > 0).sum()),
            }
        )
    industry = pd.DataFrame(industry_rows).sort_values("average_weight", ascending=False)
    return stock, industry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-search", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    market, metadata = load_market_data()
    panels = build_panels(market)

    if args.skip_search and (OUTPUT_DIR / "selected_parameters.json").exists():
        selected_json = json.loads((OUTPUT_DIR / "selected_parameters.json").read_text(encoding="utf-8"))
        selected = StrategyParams(**selected_json)
        search_results = pd.read_csv(OUTPUT_DIR / "parameter_search.csv")
    else:
        search_results, selected = run_parameter_search(panels)
        search_results.to_csv(OUTPUT_DIR / "parameter_search.csv", index=False, encoding="utf-8-sig")
        (OUTPUT_DIR / "selected_parameters.json").write_text(
            json.dumps(
                {
                    "momentum_window": selected.momentum_window,
                    "trend_window": selected.trend_window,
                    "top_n": selected.top_n,
                    "stop_loss": selected.stop_loss,
                    "volatility_window": selected.volatility_window,
                    "target_exposure": selected.target_exposure,
                    "max_weight": selected.max_weight,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    comparison_rows: list[dict[str, float | int | str]] = []
    final_daily = None
    final_trades = None
    final_holdings = None
    for strategy_name, params in (("基础模板", BASELINE_PARAMS), ("锁定参数", selected)):
        daily, trades, holdings = backtest(panels, params)
        for period, start, end in (
            ("开发期", DEVELOPMENT_START, DEVELOPMENT_END),
            ("验证期", VALIDATION_START, VALIDATION_END),
            ("模拟观察期", PAPER_START, PAPER_END),
            ("全样本", DEVELOPMENT_START, PAPER_END),
        ):
            row = period_metrics(daily, trades, period, start, end)
            row["strategy"] = strategy_name
            row["parameter"] = params.label
            comparison_rows.append(row)
        if strategy_name == "锁定参数":
            final_daily = daily
            final_trades = trades
            final_holdings = holdings
        else:
            daily.to_csv(OUTPUT_DIR / "baseline_daily_backtest.csv", encoding="utf-8-sig")
            trades.to_csv(OUTPUT_DIR / "baseline_trade_log.csv", index=False, encoding="utf-8-sig")

    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(OUTPUT_DIR / "strategy_comparison.csv", index=False, encoding="utf-8-sig")
    assert final_daily is not None and final_trades is not None and final_holdings is not None
    final_daily.to_csv(OUTPUT_DIR / "daily_backtest.csv", encoding="utf-8-sig")
    final_trades.to_csv(OUTPUT_DIR / "trade_log.csv", index=False, encoding="utf-8-sig")
    final_holdings.to_csv(OUTPUT_DIR / "daily_holdings.csv", index=False, encoding="utf-8-sig")

    sensitivity = cost_sensitivity(panels, selected)
    sensitivity.to_csv(OUTPUT_DIR / "cost_sensitivity.csv", index=False, encoding="utf-8-sig")
    stock_exposure, industry_exposure = exposure_summary(final_holdings, metadata, final_daily)
    stock_exposure.to_csv(OUTPUT_DIR / "stock_exposure.csv", index=False, encoding="utf-8-sig")
    industry_exposure.to_csv(OUTPUT_DIR / "industry_exposure.csv", index=False, encoding="utf-8-sig")

    data_quality = {
        "source": "TASK3前复权日线数据；原始来源见strategy_universe.csv",
        "calendar_start": min(frame.index.min() for frame in market.values()).date().isoformat(),
        "calendar_end": max(frame.index.max() for frame in market.values()).date().isoformat(),
        "security_count": len(market),
        "row_count": int(sum(len(frame) for frame in market.values())),
        "common_latest_date": min(frame.index.max() for frame in market.values()).date().isoformat(),
        "known_limitations": [
            "固定十只股票池存在幸存者偏差与样本选择偏差",
            "缺少历史ST、停牌、涨跌停和盘口冲击的完整逐日复原",
            "本地撮合为日频近似，不等同于JoinQuant官方回测引擎",
            "模拟观察期是锁参后的历史纸上推演，不是已运行多日的JoinQuant模拟账户",
        ],
    }
    (OUTPUT_DIR / "data_quality.json").write_text(
        json.dumps(data_quality, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Selected parameters: {selected.label}")
    print(comparison.loc[:, ["strategy", "parameter", "period", "cumulative_return", "sharpe_ratio", "max_drawdown", "benchmark_return"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
