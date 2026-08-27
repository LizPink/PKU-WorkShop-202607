from __future__ import annotations

import itertools
import json
import math
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from matplotlib import font_manager
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeRegressor

from config import (
    COLORS,
    COST_SCENARIOS,
    FEATURE_COLUMNS,
    FIGURE_DIR,
    MODEL_NAMES_ZH,
    MODEL_ORDER,
    ONE_WAY_COST,
    OUTPUT_DIR,
    PROCESSED_DIR,
    RANDOM_STATE,
    RAW_DIR,
    TEST_QUARTERS,
    TITLE,
    TOP_N,
    VALIDATION_QUARTERS,
    ensure_directories,
)


@dataclass(frozen=True)
class Candidate:
    model: str
    params: dict[str, object]


def configure_plot_style() -> None:
    for path in (Path(r"C:\Windows\Fonts\simsun.ttc"), Path(r"C:\Windows\Fonts\msyh.ttc")):
        if path.exists():
            try:
                font_manager.fontManager.addfont(path)
            except RuntimeError:
                pass
    plt.rcParams.update(
        {
            "font.sans-serif": ["SimSun", "Microsoft YaHei", "Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "text.color": COLORS["ink"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "axes.titleweight": "bold",
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "legend.frameon": False,
            "savefig.dpi": 240,
        }
    )


def rolling_series(frame: pd.DataFrame, column: str, window: int, operation: str, min_periods: int | None = None) -> pd.Series:
    min_periods = min_periods or max(5, int(window * 0.8))
    grouped = frame.groupby("ts_code", sort=False)[column]
    rolling = grouped.rolling(window, min_periods=min_periods)
    result = getattr(rolling, operation)().reset_index(level=0, drop=True)
    return result.reindex(frame.index)


def load_daily_data() -> pd.DataFrame:
    path = RAW_DIR / "csi300_current_constituents_daily_hfq.csv"
    if not path.exists():
        raise SystemExit(f"Missing raw data: {path}. Run fetch_data.py first.")
    daily = pd.read_csv(path, dtype={"ts_code": str}, parse_dates=["trade_date"])
    daily["ts_code"] = daily["ts_code"].str.zfill(6)
    numeric = [
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude_pct",
        "pct_change",
        "price_change",
        "turnover_rate",
    ]
    daily[numeric] = daily[numeric].apply(pd.to_numeric, errors="coerce")
    daily = daily.dropna(subset=["ts_code", "trade_date", "open", "close"])
    daily = daily.sort_values(["ts_code", "trade_date"]).drop_duplicates(["ts_code", "trade_date"], keep="last")
    daily = daily.reset_index(drop=True)
    return daily


def build_quarterly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    daily = daily.copy()
    grouped = daily.groupby("ts_code", sort=False)
    daily["observation_number"] = grouped.cumcount() + 1
    daily["daily_return"] = grouped["close"].pct_change(fill_method=None)

    for days in (5, 21, 63, 126, 252):
        daily[f"ret_{days}d"] = grouped["close"].pct_change(days, fill_method=None)
    daily["momentum_12_1"] = grouped["close"].shift(21) / grouped["close"].shift(252) - 1

    daily["volatility_20d"] = rolling_series(daily, "daily_return", 20, "std") * math.sqrt(252)
    daily["volatility_60d"] = rolling_series(daily, "daily_return", 60, "std") * math.sqrt(252)
    daily["negative_squared_return"] = daily["daily_return"].where(daily["daily_return"] < 0, 0.0).pow(2)
    daily["downside_volatility_60d"] = rolling_series(
        daily, "negative_squared_return", 60, "mean"
    ).pow(0.5) * math.sqrt(252)

    rolling_high = rolling_series(daily, "close", 126, "max")
    daily["drawdown_from_high"] = daily["close"] / rolling_high - 1
    daily["max_drawdown_126d"] = rolling_series(daily, "drawdown_from_high", 126, "min")

    daily["turnover_20d"] = rolling_series(daily, "turnover_rate", 20, "mean")
    daily["turnover_60d"] = rolling_series(daily, "turnover_rate", 60, "mean")
    daily["amount_20d"] = rolling_series(daily, "amount", 20, "mean")
    daily["log_amount_20d"] = np.log1p(daily["amount_20d"].clip(lower=0))
    daily["amihud_daily"] = daily["daily_return"].abs() / daily["amount"].where(daily["amount"] > 0) * 1e8
    daily["amihud_20d"] = rolling_series(daily, "amihud_daily", 20, "mean")
    daily["volume_20d"] = rolling_series(daily, "volume", 20, "mean")
    daily["volume_60d"] = rolling_series(daily, "volume", 60, "mean")
    daily["volume_ratio_20_60"] = daily["volume_20d"] / daily["volume_60d"].replace(0, np.nan)
    daily["ma20"] = rolling_series(daily, "close", 20, "mean")
    daily["ma60"] = rolling_series(daily, "close", 60, "mean")
    daily["price_to_ma20"] = daily["close"] / daily["ma20"].replace(0, np.nan) - 1
    daily["price_to_ma60"] = daily["close"] / daily["ma60"].replace(0, np.nan) - 1
    daily["intraday_range"] = (daily["high"] - daily["low"]) / daily["close"].replace(0, np.nan)
    daily["intraday_range_20d"] = rolling_series(daily, "intraday_range", 20, "mean")

    daily["quarter"] = daily["trade_date"].dt.to_period("Q")
    daily["quarter_index"] = daily["quarter"].dt.year * 4 + daily["quarter"].dt.quarter

    signal_columns = [
        "ts_code",
        "stock_name",
        "quarter",
        "quarter_index",
        "trade_date",
        "close",
        "observation_number",
        *FEATURE_COLUMNS,
    ]
    signals = daily.groupby(["ts_code", "quarter_index"], sort=False, as_index=False).tail(1)[signal_columns].copy()
    signals = signals.rename(columns={"trade_date": "signal_date", "close": "signal_close"})

    entries = daily.groupby(["ts_code", "quarter_index"], sort=False, as_index=False).head(1)[
        ["ts_code", "quarter_index", "trade_date", "open"]
    ].copy()
    entry_table = entries.rename(
        columns={"quarter_index": "entry_quarter_index", "trade_date": "entry_date", "open": "entry_open"}
    )
    exit_table = entries.rename(
        columns={"quarter_index": "exit_quarter_index", "trade_date": "exit_date", "open": "exit_open"}
    )
    signals["entry_quarter_index"] = signals["quarter_index"] + 1
    signals["exit_quarter_index"] = signals["quarter_index"] + 2
    panel = signals.merge(entry_table, on=["ts_code", "entry_quarter_index"], how="left")
    panel = panel.merge(exit_table, on=["ts_code", "exit_quarter_index"], how="left")
    panel["forward_return"] = panel["exit_open"] / panel["entry_open"] - 1
    panel["quarter"] = panel["quarter"].astype(str)

    panel[FEATURE_COLUMNS] = panel[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)
    panel["feature_non_null_count"] = panel[FEATURE_COLUMNS].notna().sum(axis=1)
    panel["eligible"] = (
        (panel["observation_number"] >= 252)
        & (panel["feature_non_null_count"] >= 14)
        & panel["entry_open"].gt(0)
        & panel["exit_open"].gt(0)
        & panel["forward_return"].between(-0.9, 5.0)
    )
    panel = panel.loc[panel["eligible"]].copy()

    processed_feature_columns: list[str] = []
    for feature in FEATURE_COLUMNS:
        processed = f"x_{feature}"
        processed_feature_columns.append(processed)

        def transform_cross_section(series: pd.Series) -> pd.Series:
            values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)
            if values.notna().sum() < 5:
                return pd.Series(0.5, index=values.index)
            low, high = values.quantile([0.01, 0.99])
            clipped = values.clip(lower=low, upper=high).fillna(values.median())
            return clipped.rank(method="average", pct=True)

        panel[processed] = panel.groupby("quarter_index", group_keys=False)[feature].transform(transform_cross_section)

    panel["target_rank"] = panel.groupby("quarter_index")["forward_return"].rank(method="average", pct=True)
    panel = panel.dropna(subset=["target_rank", *processed_feature_columns]).copy()
    panel = panel.sort_values(["quarter_index", "ts_code"]).reset_index(drop=True)
    panel.to_csv(PROCESSED_DIR / "quarterly_panel.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    return panel


def rank_ic(actual: pd.Series | np.ndarray, prediction: pd.Series | np.ndarray) -> float:
    actual_series = pd.Series(np.asarray(actual)).rank(method="average")
    prediction_series = pd.Series(np.asarray(prediction)).rank(method="average")
    return float(actual_series.corr(prediction_series))


def build_model(model_key: str, params: dict[str, object]):
    if model_key == "ridge":
        return Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=float(params["alpha"]))),
            ]
        )
    if model_key == "decision_tree":
        return DecisionTreeRegressor(random_state=RANDOM_STATE, **params)
    if model_key == "random_forest":
        return RandomForestRegressor(
            n_estimators=300,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            bootstrap=True,
            **params,
        )
    raise KeyError(model_key)


def parameter_candidates() -> list[Candidate]:
    candidates = [Candidate("ridge", {"alpha": alpha}) for alpha in (0.1, 1.0, 10.0)]
    candidates.extend(
        Candidate("decision_tree", {"max_depth": depth, "min_samples_leaf": leaf})
        for depth, leaf in itertools.product((3, 5, 7), (10, 25, 50))
    )
    candidates.extend(
        [
            Candidate("random_forest", {"max_depth": 5, "min_samples_leaf": 10, "max_features": 0.7}),
            Candidate("random_forest", {"max_depth": 8, "min_samples_leaf": 10, "max_features": 0.7}),
            Candidate("random_forest", {"max_depth": None, "min_samples_leaf": 10, "max_features": "sqrt"}),
            Candidate("random_forest", {"max_depth": None, "min_samples_leaf": 25, "max_features": 0.7}),
        ]
    )
    return candidates


def select_time_splits(panel: pd.DataFrame) -> tuple[list[int], list[int], list[int]]:
    quarter_counts = panel.groupby("quarter_index").size()
    usable = quarter_counts.loc[quarter_counts >= 60].index.astype(int).tolist()
    if len(usable) < TEST_QUARTERS + VALIDATION_QUARTERS + 8:
        raise RuntimeError(f"Only {len(usable)} usable quarters; at least 20 are required.")
    test = usable[-TEST_QUARTERS:]
    validation = usable[-(TEST_QUARTERS + VALIDATION_QUARTERS) : -TEST_QUARTERS]
    train = usable[: -(TEST_QUARTERS + VALIDATION_QUARTERS)]
    return train, validation, test


def tune_models(panel: pd.DataFrame, feature_columns: list[str], train_quarters: list[int], validation_quarters: list[int]) -> tuple[dict[str, dict[str, object]], pd.DataFrame]:
    train = panel.loc[panel["quarter_index"].isin(train_quarters)]
    validation = panel.loc[panel["quarter_index"].isin(validation_quarters)]
    search_rows: list[dict[str, object]] = []
    best: dict[str, dict[str, object]] = {}

    for candidate in parameter_candidates():
        model = build_model(candidate.model, candidate.params)
        model.fit(train[feature_columns], train["target_rank"])
        predicted = model.predict(validation[feature_columns])
        scored = validation[["quarter_index", "target_rank"]].copy()
        scored["prediction"] = predicted
        quarterly_ics = scored.groupby("quarter_index").apply(
            lambda group: rank_ic(group["target_rank"], group["prediction"]), include_groups=False
        )
        search_rows.append(
            {
                "model": candidate.model,
                "model_zh": MODEL_NAMES_ZH[candidate.model],
                "params": json.dumps(candidate.params, ensure_ascii=False, sort_keys=True),
                "validation_mean_rank_ic": quarterly_ics.mean(),
                "validation_ic_std": quarterly_ics.std(ddof=1),
                "validation_positive_ic_ratio": (quarterly_ics > 0).mean(),
                "validation_mae": mean_absolute_error(validation["target_rank"], predicted),
            }
        )
    search = pd.DataFrame(search_rows)
    for model_key in MODEL_ORDER:
        subset = search.loc[search["model"] == model_key].sort_values(
            ["validation_mean_rank_ic", "validation_mae"], ascending=[False, True]
        )
        best[model_key] = json.loads(subset.iloc[0]["params"])
    search.to_csv(OUTPUT_DIR / "hyperparameter_search.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    (OUTPUT_DIR / "selected_parameters.json").write_text(
        json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return best, search


def expanding_predictions(panel: pd.DataFrame, feature_columns: list[str], test_quarters: list[int], selected: dict[str, dict[str, object]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    prediction_frames: list[pd.DataFrame] = []
    importance_rows: list[dict[str, object]] = []
    for quarter_index in test_quarters:
        train = panel.loc[panel["quarter_index"] < quarter_index]
        test = panel.loc[panel["quarter_index"] == quarter_index].copy()
        for model_key in MODEL_ORDER:
            model = build_model(model_key, selected[model_key])
            model.fit(train[feature_columns], train["target_rank"])
            test[f"prediction_{model_key}"] = model.predict(test[feature_columns])
            if model_key == "random_forest":
                for feature, value in zip(feature_columns, model.feature_importances_):
                    importance_rows.append(
                        {"quarter_index": quarter_index, "quarter": test["quarter"].iloc[0], "feature": feature, "importance": value}
                    )
        keep = [
            "ts_code",
            "stock_name",
            "quarter",
            "quarter_index",
            "signal_date",
            "entry_date",
            "exit_date",
            "forward_return",
            "target_rank",
            *[f"prediction_{key}" for key in MODEL_ORDER],
        ]
        prediction_frames.append(test[keep])
    predictions = pd.concat(prediction_frames, ignore_index=True)
    predictions.to_csv(OUTPUT_DIR / "test_predictions.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    importance = pd.DataFrame(importance_rows)
    importance_summary = importance.groupby("feature", as_index=False).agg(
        mean_importance=("importance", "mean"),
        std_importance=("importance", "std"),
    )
    importance_summary = importance_summary.sort_values("mean_importance", ascending=False)
    importance_summary.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    return predictions, importance_summary


def evaluate_predictions(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    model_rows: list[dict[str, object]] = []
    ic_rows: list[dict[str, object]] = []
    for model_key in MODEL_ORDER:
        pred_col = f"prediction_{model_key}"
        quarter_ics: list[float] = []
        for (quarter_index, quarter), group in predictions.groupby(["quarter_index", "quarter"], sort=True):
            ic = rank_ic(group["target_rank"], group[pred_col])
            quarter_ics.append(ic)
            ic_rows.append(
                {
                    "model": model_key,
                    "model_zh": MODEL_NAMES_ZH[model_key],
                    "quarter_index": quarter_index,
                    "quarter": quarter,
                    "rank_ic": ic,
                    "stock_count": len(group),
                }
            )
        ic_array = np.asarray(quarter_ics, dtype=float)
        model_rows.append(
            {
                "model": model_key,
                "model_zh": MODEL_NAMES_ZH[model_key],
                "mae_rank": mean_absolute_error(predictions["target_rank"], predictions[pred_col]),
                "rmse_rank": mean_squared_error(predictions["target_rank"], predictions[pred_col]) ** 0.5,
                "r2_rank": r2_score(predictions["target_rank"], predictions[pred_col]),
                "mean_rank_ic": np.nanmean(ic_array),
                "ic_std": np.nanstd(ic_array, ddof=1),
                "icir_quarterly": np.nanmean(ic_array) / np.nanstd(ic_array, ddof=1) if np.nanstd(ic_array, ddof=1) else np.nan,
                "positive_ic_ratio": np.nanmean(ic_array > 0),
                "test_quarters": len(ic_array),
            }
        )
    model_metrics = pd.DataFrame(model_rows)
    quarterly_ic = pd.DataFrame(ic_rows)
    model_metrics.to_csv(OUTPUT_DIR / "model_metrics.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    quarterly_ic.to_csv(OUTPUT_DIR / "quarterly_ic.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    return model_metrics, quarterly_ic


def calculate_turnover(
    new_weights: dict[str, float],
    previous_weights: dict[str, float] | None,
    previous_returns: dict[str, float] | None,
) -> float:
    if not previous_weights:
        return 1.0
    previous_returns = previous_returns or {}
    growth = {
        code: weight * (1.0 + float(previous_returns.get(code, 0.0)))
        for code, weight in previous_weights.items()
    }
    total = sum(growth.values())
    drifted = {code: value / total for code, value in growth.items()} if total > 0 else previous_weights
    union = set(new_weights) | set(drifted)
    return 0.5 * sum(abs(new_weights.get(code, 0.0) - drifted.get(code, 0.0)) for code in union)


def backtest(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    holding_rows: list[dict[str, object]] = []
    for model_key in MODEL_ORDER:
        previous_weights: dict[str, float] | None = None
        previous_returns: dict[str, float] | None = None
        for (quarter_index, quarter), group in predictions.groupby(["quarter_index", "quarter"], sort=True):
            ordered = group.sort_values(f"prediction_{model_key}", ascending=False).copy()
            selected = ordered.head(min(TOP_N, len(ordered))).copy()
            weight = 1.0 / len(selected)
            new_weights = dict(zip(selected["ts_code"], np.repeat(weight, len(selected))))
            turnover = calculate_turnover(new_weights, previous_weights, previous_returns)
            gross_return = float(np.average(selected["forward_return"], weights=np.repeat(weight, len(selected))))
            benchmark_return = float(group["forward_return"].mean())
            trading_cost = turnover * ONE_WAY_COST
            net_return = gross_return - trading_cost
            rows.append(
                {
                    "model": model_key,
                    "model_zh": MODEL_NAMES_ZH[model_key],
                    "quarter_index": quarter_index,
                    "quarter": quarter,
                    "signal_date": group["signal_date"].max(),
                    "entry_date": group["entry_date"].min(),
                    "exit_date": group["exit_date"].max(),
                    "universe_count": len(group),
                    "selected_count": len(selected),
                    "gross_return": gross_return,
                    "turnover": turnover,
                    "trading_cost": trading_cost,
                    "net_return": net_return,
                    "benchmark_return": benchmark_return,
                    "gross_excess_return": gross_return - benchmark_return,
                    "net_excess_return": net_return - benchmark_return,
                }
            )
            selected = selected.assign(
                model=model_key,
                model_zh=MODEL_NAMES_ZH[model_key],
                weight=weight,
                prediction_rank=np.arange(1, len(selected) + 1),
            )
            holding_rows.extend(
                selected[
                    [
                        "model",
                        "model_zh",
                        "quarter_index",
                        "quarter",
                        "ts_code",
                        "stock_name",
                        "prediction_rank",
                        "weight",
                        f"prediction_{model_key}",
                        "forward_return",
                    ]
                ]
                .rename(columns={f"prediction_{model_key}": "prediction_score"})
                .to_dict("records")
            )
            previous_weights = new_weights
            previous_returns = dict(zip(selected["ts_code"], selected["forward_return"]))

    quarterly = pd.DataFrame(rows).sort_values(["model", "quarter_index"])
    holdings = pd.DataFrame(holding_rows).sort_values(["model", "quarter_index", "prediction_rank"])
    metrics_rows: list[dict[str, object]] = []
    cost_rows: list[dict[str, object]] = []
    for model_key, group in quarterly.groupby("model", sort=False):
        group = group.sort_values("quarter_index")
        metrics_rows.append(performance_metrics(model_key, group["net_return"], group["benchmark_return"], group["turnover"]))
        for scenario in COST_SCENARIOS:
            scenario_returns = group["gross_return"] - group["turnover"] * scenario
            item = performance_metrics(model_key, scenario_returns, group["benchmark_return"], group["turnover"])
            item["one_way_cost"] = scenario
            cost_rows.append(item)
    metrics = pd.DataFrame(metrics_rows)
    cost_sensitivity = pd.DataFrame(cost_rows)
    quarterly.to_csv(OUTPUT_DIR / "quarterly_returns.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    holdings.to_csv(OUTPUT_DIR / "holdings.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    metrics.to_csv(OUTPUT_DIR / "backtest_metrics.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    cost_sensitivity.to_csv(OUTPUT_DIR / "cost_sensitivity.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    return quarterly, holdings, metrics, cost_sensitivity


def performance_metrics(model_key: str, returns: pd.Series, benchmark: pd.Series, turnover: pd.Series) -> dict[str, object]:
    returns = pd.Series(returns, dtype=float).reset_index(drop=True)
    benchmark = pd.Series(benchmark, dtype=float).reset_index(drop=True)
    periods = len(returns)
    nav = (1 + returns).cumprod()
    benchmark_nav = (1 + benchmark).cumprod()
    drawdown = nav / nav.cummax() - 1
    annualized_return = nav.iloc[-1] ** (4 / periods) - 1
    annualized_volatility = returns.std(ddof=1) * 2
    excess = returns - benchmark
    tracking_error = excess.std(ddof=1) * 2
    benchmark_annualized = benchmark_nav.iloc[-1] ** (4 / periods) - 1
    return {
        "model": model_key,
        "model_zh": MODEL_NAMES_ZH[model_key],
        "quarters": periods,
        "cumulative_return": nav.iloc[-1] - 1,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_rf0": returns.mean() / returns.std(ddof=1) * 2 if returns.std(ddof=1) else np.nan,
        "max_drawdown": drawdown.min(),
        "calmar": annualized_return / abs(drawdown.min()) if drawdown.min() < 0 else np.nan,
        "quarterly_win_rate": (returns > 0).mean(),
        "excess_win_rate": (excess > 0).mean(),
        "average_turnover": pd.Series(turnover, dtype=float).mean(),
        "benchmark_cumulative_return": benchmark_nav.iloc[-1] - 1,
        "benchmark_annualized_return": benchmark_annualized,
        "annualized_excess_return": annualized_return - benchmark_annualized,
        "tracking_error": tracking_error,
        "information_ratio": excess.mean() / excess.std(ddof=1) * 2 if excess.std(ddof=1) else np.nan,
    }


def save_figure(fig: plt.Figure, filename: str) -> None:
    fig.savefig(FIGURE_DIR / filename, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_sample_coverage(panel: pd.DataFrame, train_q: list[int], validation_q: list[int], test_q: list[int]) -> None:
    coverage = panel.groupby(["quarter_index", "quarter"]).size().reset_index(name="stock_count")
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.plot(coverage["quarter"], coverage["stock_count"], color=COLORS["blue"], marker="o", markersize=3.5, linewidth=1.8)
    if validation_q:
        val_start = coverage.index[coverage["quarter_index"] == validation_q[0]][0]
        test_start = coverage.index[coverage["quarter_index"] == test_q[0]][0]
        ax.axvspan(val_start - 0.5, test_start - 0.5, color=COLORS["gold"], alpha=0.12, label="验证期")
        ax.axvspan(test_start - 0.5, len(coverage) - 0.5, color=COLORS["pink"], alpha=0.10, label="测试期")
    tick_positions = np.arange(0, len(coverage), max(1, len(coverage) // 10))
    ax.set_xticks(tick_positions, coverage.iloc[tick_positions]["quarter"], rotation=45, ha="right")
    ax.set_ylabel("可用股票数")
    ax.set_title("图 1 每季度模型样本覆盖", pad=28)
    ax.text(0, 1.02, "当前中证 300 成分股中满足 252 日历史、特征和未来收益要求的股票数", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right")
    save_figure(fig, "figure_1_sample_coverage.png")


def plot_factor_correlation(panel: pd.DataFrame) -> None:
    features = [f"x_{feature}" for feature in FEATURE_COLUMNS]
    labels = [feature.replace("x_", "") for feature in features]
    corr = panel[features].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(8.4, 7.2))
    image = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)), labels, rotation=55, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(labels)), labels, fontsize=7.5)
    ax.set_title("图 2 模型因子 Spearman 相关性", pad=28)
    ax.text(0, 1.02, "横截面百分位因子；颜色仅表示相关方向与强度", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    for spine in ax.spines.values():
        spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label("相关系数")
    save_figure(fig, "figure_2_factor_correlation.png")


def plot_quarterly_ic(quarterly_ic: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    palette = {"ridge": COLORS["blue"], "decision_tree": COLORS["gold"], "random_forest": COLORS["pink"]}
    styles = {"ridge": "-", "decision_tree": "--", "random_forest": "-."}
    quarters = sorted(quarterly_ic["quarter"].unique())
    x = np.arange(len(quarters))
    for model_key in MODEL_ORDER:
        subset = quarterly_ic.loc[quarterly_ic["model"] == model_key].set_index("quarter").reindex(quarters)
        ax.plot(x, subset["rank_ic"], color=palette[model_key], linestyle=styles[model_key], marker="o", linewidth=1.8, label=MODEL_NAMES_ZH[model_key])
    ax.axhline(0, color=COLORS["ink"], linestyle=":", linewidth=1)
    ax.set_xticks(x, quarters, rotation=40, ha="right")
    ax.set_ylabel("Spearman Rank IC")
    ax.set_title("图 3 三种模型测试期季度 Rank IC", pad=28)
    ax.text(0, 1.02, "Rank IC > 0 表示预测排序与实际下一季度收益排序同向", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(ncol=3, loc="lower left")
    save_figure(fig, "figure_3_quarterly_rank_ic.png")


def plot_model_excess(quarterly: pd.DataFrame) -> None:
    summary = quarterly.groupby(["model", "model_zh"], as_index=False)["net_excess_return"].mean().sort_values("net_excess_return")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    color_map = {"ridge": COLORS["blue"], "decision_tree": COLORS["gold"], "random_forest": COLORS["pink"]}
    bars = ax.barh(summary["model_zh"], summary["net_excess_return"] * 100, color=[color_map[key] for key in summary["model"]], edgecolor=COLORS["ink"], linewidth=0.6)
    ax.axvline(0, color=COLORS["ink"], linewidth=1)
    ax.bar_label(
        bars,
        labels=[f"{value:+.2f}%" for value in summary["net_excess_return"] * 100],
        label_type="center",
        fontsize=9,
        color="white",
        fontweight="bold",
    )
    ax.set_xlabel("平均季度净超额收益（%）")
    ax.set_title("图 4 三种模型 Top 30 组合平均季度净超额收益", pad=28)
    ax.text(0, 1.03, f"相对同季度可投资样本等权平均；单边成本 {ONE_WAY_COST:.1%}", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    save_figure(fig, "figure_4_model_excess_return.png")


def nav_and_drawdown(group: pd.DataFrame) -> pd.DataFrame:
    result = group.sort_values("quarter_index")[["quarter", "net_return", "benchmark_return"]].copy()
    result["strategy_nav"] = (1 + result["net_return"]).cumprod()
    result["benchmark_nav"] = (1 + result["benchmark_return"]).cumprod()
    result["strategy_drawdown"] = result["strategy_nav"] / result["strategy_nav"].cummax() - 1
    result["benchmark_drawdown"] = result["benchmark_nav"] / result["benchmark_nav"].cummax() - 1
    return result


def plot_cumulative_nav(quarterly: pd.DataFrame, best_model: str) -> None:
    data = nav_and_drawdown(quarterly.loc[quarterly["model"] == best_model])
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.plot(x, data["strategy_nav"], color=COLORS["blue"], marker="o", linewidth=2.2, label=f"{MODEL_NAMES_ZH[best_model]} Top 30（净）")
    ax.plot(x, data["benchmark_nav"], color=COLORS["ink"], marker="s", linestyle="--", linewidth=1.8, label="可投资样本等权平均")
    ax.set_xticks(x, data["quarter"], rotation=40, ha="right")
    ax.set_ylabel("累计净值（起点=1）")
    ax.set_title("图 5 最优排序模型策略与市场平均组合累计净值", pad=28)
    ax.text(0, 1.02, f"测试期；最优模型按测试期平均 Rank IC 识别，仅用于结果展示", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="best")
    save_figure(fig, "figure_5_cumulative_nav.png")


def plot_quarterly_returns(quarterly: pd.DataFrame, best_model: str) -> None:
    data = quarterly.loc[quarterly["model"] == best_model].sort_values("quarter_index")
    x = np.arange(len(data))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.8, 4.8))
    bars_strategy = ax.bar(x - width / 2, data["net_return"] * 100, width, color=COLORS["blue"], edgecolor=COLORS["ink"], linewidth=0.5, label=f"{MODEL_NAMES_ZH[best_model]} Top 30（净）")
    bars_market = ax.bar(x + width / 2, data["benchmark_return"] * 100, width, color=COLORS["gold"], edgecolor=COLORS["ink"], linewidth=0.5, label="样本等权平均")
    ax.axhline(0, color=COLORS["ink"], linewidth=0.9)
    ax.set_xticks(x, data["quarter"], rotation=40, ha="right")
    ax.set_ylabel("季度收益率（%）")
    ax.set_title("图 6 最优模型策略与市场平均组合季度收益", pad=28)
    ax.text(0, 1.02, "并列柱展示逐季度差异，避免只依据累计终值判断", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="best")
    save_figure(fig, "figure_6_quarterly_returns.png")


def plot_drawdown(quarterly: pd.DataFrame, best_model: str) -> None:
    data = nav_and_drawdown(quarterly.loc[quarterly["model"] == best_model])
    x = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    ax.plot(x, data["strategy_drawdown"] * 100, color=COLORS["blue"], marker="o", linewidth=2, label=f"{MODEL_NAMES_ZH[best_model]} Top 30（净）")
    ax.plot(x, data["benchmark_drawdown"] * 100, color=COLORS["ink"], marker="s", linestyle="--", linewidth=1.6, label="样本等权平均")
    ax.fill_between(x, data["strategy_drawdown"] * 100, 0, color=COLORS["blue"], alpha=0.12)
    ax.set_xticks(x, data["quarter"], rotation=40, ha="right")
    ax.set_ylabel("回撤（%）")
    ax.set_title("图 7 最优模型策略与市场平均组合回撤", pad=28)
    ax.text(0, 1.02, "回撤按各自累计净值相对历史峰值计算", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower left")
    save_figure(fig, "figure_7_drawdown.png")


def plot_feature_importance(importance: pd.DataFrame) -> None:
    data = importance.head(12).sort_values("mean_importance")
    labels = data["feature"].str.replace("x_", "", regex=False)
    fig, ax = plt.subplots(figsize=(7.8, 5.2))
    bars = ax.barh(labels, data["mean_importance"], color=COLORS["olive"], edgecolor=COLORS["ink"], linewidth=0.5)
    ax.bar_label(bars, labels=[f"{value:.3f}" for value in data["mean_importance"]], padding=3, fontsize=8.5)
    ax.set_xlabel("平均不纯度特征重要度")
    ax.set_title("图 8 随机森林前 12 项特征重要度", pad=28)
    ax.text(0, 1.02, "对 8 个扩展窗口模型的重要度取平均；不代表因果效应", transform=ax.transAxes, fontsize=9, color=COLORS["muted"])
    ax.grid(axis="x", color=COLORS["grid"], linewidth=0.7)
    ax.spines[["top", "right", "left"]].set_visible(False)
    save_figure(fig, "figure_8_random_forest_feature_importance.png")


def write_chart_map() -> None:
    rows = [
        ("图 1", "样本与划分", "季度样本覆盖是否稳定", "Trend", "line", "quarter, stock_count", "识别样本覆盖和训练/验证/测试边界", "blue + gold/pink context", "figure_1_sample_coverage.png"),
        ("图 2", "因子", "因子是否高度冗余", "Matrix", "heatmap", "factor ranks", "识别高相关因子组", "diverging blue/orange", "figure_2_factor_correlation.png"),
        ("图 3", "模型", "预测排序逐季度是否稳定", "Trend + benchmark", "multi-line", "quarter, model, rank_ic", "比较季度 Rank IC 及正负方向", "blue + gold + pink", "figure_3_quarterly_rank_ic.png"),
        ("图 4", "策略比较", "哪个模型的季度净超额更高", "Comparison", "horizontal bar", "model, mean net excess", "比较模型经济结果", "model categorical", "figure_4_model_excess_return.png"),
        ("图 5", "回测", "策略累计趋势是否跑赢基准", "Trend", "two-line", "quarter, strategy_nav, benchmark_nav", "比较累计净值", "blue + neutral", "figure_5_cumulative_nav.png"),
        ("图 6", "回测", "策略逐季度如何相对市场表现", "Comparison", "grouped bar", "quarter, returns", "展示逐期差异", "blue + gold", "figure_6_quarterly_returns.png"),
        ("图 7", "风险", "策略回撤与基准有何差异", "Trend", "two-line + fill", "quarter, drawdown", "展示峰值损失", "blue + neutral", "figure_7_drawdown.png"),
        ("图 8", "解释", "随机森林主要依据哪些因子", "Ranking", "horizontal bar", "feature, importance", "展示前 12 项重要度", "olive single-root", "figure_8_random_forest_feature_importance.png"),
    ]
    pd.DataFrame(
        rows,
        columns=["figure", "section", "question", "family", "chart_type", "fields", "takeaway", "palette", "artifact"],
    ).to_csv(OUTPUT_DIR / "chart_map.csv", index=False, encoding="utf-8-sig")


def write_quality_and_summary(
    daily: pd.DataFrame,
    panel: pd.DataFrame,
    train_q: list[int],
    validation_q: list[int],
    test_q: list[int],
    model_metrics: pd.DataFrame,
    backtest_metrics: pd.DataFrame,
) -> None:
    source_metadata = json.loads((RAW_DIR / "source_metadata.json").read_text(encoding="utf-8"))
    quarter_lookup = panel.drop_duplicates("quarter_index").set_index("quarter_index")["quarter"].to_dict()
    quality = {
        "analysis_title": TITLE,
        "source": source_metadata["source"],
        "source_as_of": source_metadata["fetched_at"],
        "raw_daily_rows": int(len(daily)),
        "raw_stock_count": int(daily["ts_code"].nunique()),
        "raw_date_min": str(daily["trade_date"].min().date()),
        "raw_date_max": str(daily["trade_date"].max().date()),
        "raw_duplicate_stock_dates": int(daily.duplicated(["ts_code", "trade_date"]).sum()),
        "raw_missing_core_values": int(daily[["open", "close", "high", "low", "volume", "amount"]].isna().sum().sum()),
        "panel_rows": int(len(panel)),
        "panel_stock_count": int(panel["ts_code"].nunique()),
        "panel_quarters": int(panel["quarter_index"].nunique()),
        "panel_duplicate_keys": int(panel.duplicated(["ts_code", "quarter_index"]).sum()),
        "min_quarter_stock_count": int(panel.groupby("quarter_index").size().min()),
        "max_quarter_stock_count": int(panel.groupby("quarter_index").size().max()),
        "feature_count": len(FEATURE_COLUMNS),
        "train_quarters": [quarter_lookup[q] for q in train_q],
        "validation_quarters": [quarter_lookup[q] for q in validation_q],
        "test_quarters": [quarter_lookup[q] for q in test_q],
        "known_limitations": [
            source_metadata["known_limitation"],
            "Historical ST, suspension and limit-up/limit-down tradeability are not fully modeled.",
            "The primary model uses technical, volatility, liquidity and turnover factors because point-in-time financial announcement data were not available.",
        ],
        "python_version": platform.python_version(),
        "pandas_version": pd.__version__,
        "sklearn_version": sklearn.__version__,
    }
    (OUTPUT_DIR / "data_quality.json").write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    split_rows = []
    for split_name, quarters in (("train", train_q), ("validation", validation_q), ("test", test_q)):
        subset = panel.loc[panel["quarter_index"].isin(quarters)]
        split_rows.append(
            {
                "split": split_name,
                "quarter_start": quarter_lookup[quarters[0]],
                "quarter_end": quarter_lookup[quarters[-1]],
                "quarters": len(quarters),
                "rows": len(subset),
                "stocks": subset["ts_code"].nunique(),
            }
        )
    pd.DataFrame(split_rows).to_csv(OUTPUT_DIR / "split_summary.csv", index=False, encoding="utf-8-sig")

    best_model = model_metrics.sort_values("mean_rank_ic", ascending=False).iloc[0]["model"]
    best_prediction_row = model_metrics.set_index("model").loc[best_model]
    best_backtest_row = backtest_metrics.set_index("model").loc[best_model]
    summary = {
        "best_model_by_test_mean_rank_ic": best_model,
        "best_model_zh": MODEL_NAMES_ZH[best_model],
        "best_mean_rank_ic": float(best_prediction_row["mean_rank_ic"]),
        "best_positive_ic_ratio": float(best_prediction_row["positive_ic_ratio"]),
        "best_strategy_cumulative_net_return": float(best_backtest_row["cumulative_return"]),
        "best_strategy_annualized_net_return": float(best_backtest_row["annualized_return"]),
        "best_strategy_max_drawdown": float(best_backtest_row["max_drawdown"]),
        "benchmark_cumulative_return": float(best_backtest_row["benchmark_cumulative_return"]),
        "benchmark_annualized_return": float(best_backtest_row["benchmark_annualized_return"]),
        "one_way_cost": ONE_WAY_COST,
        "interpretation_boundary": "Historical educational backtest with survivorship and execution limitations; not investment advice.",
    }
    (OUTPUT_DIR / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ensure_directories()
    configure_plot_style()
    daily = load_daily_data()
    panel = build_quarterly_panel(daily)
    processed_features = [f"x_{feature}" for feature in FEATURE_COLUMNS]
    train_q, validation_q, test_q = select_time_splits(panel)
    selected, _ = tune_models(panel, processed_features, train_q, validation_q)
    predictions, importance = expanding_predictions(panel, processed_features, test_q, selected)
    model_metrics, quarterly_ic = evaluate_predictions(predictions)
    quarterly, _, backtest_metrics, _ = backtest(predictions)
    best_model = str(model_metrics.sort_values("mean_rank_ic", ascending=False).iloc[0]["model"])

    plot_sample_coverage(panel, train_q, validation_q, test_q)
    plot_factor_correlation(panel.loc[panel["quarter_index"].isin(train_q + validation_q)])
    plot_quarterly_ic(quarterly_ic)
    plot_model_excess(quarterly)
    plot_cumulative_nav(quarterly, best_model)
    plot_quarterly_returns(quarterly, best_model)
    plot_drawdown(quarterly, best_model)
    plot_feature_importance(importance)
    write_chart_map()
    write_quality_and_summary(daily, panel, train_q, validation_q, test_q, model_metrics, backtest_metrics)

    print("\nModel metrics:")
    print(model_metrics[["model_zh", "mean_rank_ic", "positive_ic_ratio", "mae_rank", "r2_rank"]].to_string(index=False))
    print("\nBacktest metrics (net):")
    print(backtest_metrics[["model_zh", "cumulative_return", "annualized_return", "max_drawdown", "information_ratio"]].to_string(index=False))
    print(f"\nBest model by test mean Rank IC: {MODEL_NAMES_ZH[best_model]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
