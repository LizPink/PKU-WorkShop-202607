# -*- coding: utf-8 -*-
"""
TASK7 JoinQuant strategy

Logic:
1. Rebalance on the first trading day of each month.
2. Rank a fixed, liquid A-share universe by prior-close momentum.
3. Keep stocks above their long moving average.
4. Allocate with inverse-volatility weights, capped by single-name exposure.
5. Check a trailing stop every trading day.

Recommended backtest settings:
- Frequency: daily
- Initial cash: CNY 1,000,000
- Benchmark: CSI 300 Index
- Locked parameters: M20 / T60 / top 3 / 8% trailing stop
"""

import numpy as np


def initialize(context):
    g.stocks = [
        "000001.XSHE",  # Ping An Bank
        "600036.XSHG",  # China Merchants Bank
        "600519.XSHG",  # Kweichow Moutai
        "000858.XSHE",  # Wuliangye
        "002594.XSHE",  # BYD
        "300750.XSHE",  # CATL
        "002371.XSHE",  # NAURA
        "600584.XSHG",  # JCET
        "600031.XSHG",  # SANY Heavy Industry
        "000425.XSHE",  # XCMG Machinery
    ]

    # These values may be overwritten by create_backtest(..., extras={...})
    # after initialize finishes, which is convenient for parameter searches.
    g.momentum_window = 20
    g.trend_window = 60
    g.volatility_window = 20
    g.top_n = 3
    g.stop_loss = 0.08
    g.target_exposure = 0.90
    g.max_weight = 0.40
    g.high_watermark = {}
    g.stopped_today = set()

    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    try:
        set_option("avoid_future_data", True)
    except Exception:
        pass
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0.0005,
            open_commission=0.0003,
            close_commission=0.0003,
            close_today_commission=0,
            min_commission=5,
        ),
        type="stock",
    )
    set_slippage(PriceRelatedSlippage(0.002))
    log.set_level("order", "error")

    run_daily(reset_daily_state, time="before_open")
    run_daily(check_trailing_stop, time="open")
    run_monthly(rebalance, 1, time="open+5m")
    run_daily(record_risk_state, time="after_close")


def reset_daily_state(context):
    g.stopped_today = set()


def is_tradeable(security, current_data):
    item = current_data[security]
    name = item.name or ""
    return not (
        item.paused
        or item.is_st
        or "ST" in name
        or "*" in name
        or "退" in name
        or np.isnan(item.last_price)
    )


def check_trailing_stop(context):
    current_data = get_current_data()
    for security in list(context.portfolio.positions.keys()):
        position = context.portfolio.positions[security]
        if position.total_amount <= 0 or not is_tradeable(security, current_data):
            continue
        history_data = attribute_history(
            security,
            2,
            unit="1d",
            fields=["high", "close"],
            skip_paused=True,
            df=True,
        )
        if len(history_data) < 1:
            continue
        yesterday_high = float(history_data["high"].iloc[-1])
        yesterday_close = float(history_data["close"].iloc[-1])
        old_peak = g.high_watermark.get(security, yesterday_high)
        new_peak = max(old_peak, yesterday_high)
        g.high_watermark[security] = new_peak

        if yesterday_close <= new_peak * (1.0 - g.stop_loss):
            order = order_target_value(security, 0)
            if order is not None:
                g.stopped_today.add(security)
                g.high_watermark.pop(security, None)
                log.info(
                    "Trailing stop: %s, close=%.3f, peak=%.3f"
                    % (security, yesterday_close, new_peak)
                )


def capped_inverse_volatility_weights(selected, volatility):
    if not selected:
        return {}
    inverse = dict((security, 1.0 / volatility[security]) for security in selected)
    remaining = set(selected)
    remaining_exposure = g.target_exposure
    weights = dict((security, 0.0) for security in selected)

    while remaining:
        denominator = sum(inverse[security] for security in remaining)
        provisional = dict(
            (
                security,
                inverse[security] / denominator * remaining_exposure,
            )
            for security in remaining
        )
        capped = [
            security
            for security, weight in provisional.items()
            if weight > g.max_weight
        ]
        if not capped:
            for security, weight in provisional.items():
                weights[security] = weight
            break
        for security in capped:
            weights[security] = g.max_weight
            remaining.remove(security)
            remaining_exposure -= g.max_weight
        if remaining_exposure <= 0:
            break
    return weights


def rebalance(context):
    current_data = get_current_data()
    momentum = {}
    volatility = {}

    required = max(
        g.momentum_window + 1,
        g.trend_window,
        g.volatility_window + 1,
    )
    for security in g.stocks:
        if security in g.stopped_today or not is_tradeable(security, current_data):
            continue
        history_data = attribute_history(
            security,
            required,
            unit="1d",
            fields=["close"],
            skip_paused=True,
            df=True,
        )
        if len(history_data) < required:
            continue
        closes = history_data["close"].astype(float)
        latest = float(closes.iloc[-1])
        trend_average = float(closes.tail(g.trend_window).mean())
        momentum_value = latest / float(closes.iloc[-g.momentum_window - 1]) - 1.0
        daily_returns = closes.pct_change().dropna().tail(g.volatility_window)
        annual_volatility = float(daily_returns.std() * np.sqrt(252))
        if (
            momentum_value > 0
            and latest > trend_average
            and np.isfinite(annual_volatility)
            and annual_volatility > 0
        ):
            momentum[security] = momentum_value
            volatility[security] = annual_volatility

    selected = sorted(momentum, key=momentum.get, reverse=True)[: g.top_n]
    weights = capped_inverse_volatility_weights(selected, volatility)

    # Sell or reduce first, so cash is available for the target portfolio.
    for security in list(context.portfolio.positions.keys()):
        if security not in selected:
            order = order_target_value(security, 0)
            if order is not None:
                g.high_watermark.pop(security, None)

    portfolio_value = context.portfolio.total_value
    for security in selected:
        item = current_data[security]
        if item.last_price >= item.high_limit:
            log.info("Skip limit-up security: %s" % security)
            continue
        target_value = portfolio_value * weights[security]
        order = order_target_value(security, target_value)
        if order is not None and security not in g.high_watermark:
            recent = attribute_history(
                security,
                1,
                unit="1d",
                fields=["close"],
                skip_paused=True,
                df=True,
            )
            if len(recent):
                g.high_watermark[security] = float(recent["close"].iloc[-1])

    log.info(
        "Monthly selection: %s"
        % ", ".join(
            "%s(%.1f%%)" % (security, 100.0 * weights[security])
            for security in selected
        )
    )


def record_risk_state(context):
    portfolio_value = context.portfolio.total_value
    market_value = sum(
        position.value
        for position in context.portfolio.positions.values()
        if position.total_amount > 0
    )
    exposure = market_value / portfolio_value if portfolio_value > 0 else 0.0
    cash_ratio = context.portfolio.cash / portfolio_value if portfolio_value > 0 else 0.0
    holding_count = sum(
        1
        for position in context.portfolio.positions.values()
        if position.total_amount > 0
    )
    record(
        exposure=exposure,
        cash_ratio=cash_ratio,
        holding_count=holding_count,
    )
