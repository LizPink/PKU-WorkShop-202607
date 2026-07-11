from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from config import CROSS_TOLERANCE, DEFAULT_TRANSACTION_COST, PARAMETER_PAIRS, UNIVERSE, code_slug
from strategy_backtest import DATA_DIR, OUTPUT_DIR


TASK_DIR = Path(__file__).resolve().parents[1]
WEB_DIR = TASK_DIR / "web"


def parse_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().map({"true": True, "false": False})


def validate_results() -> Path:
    issues: list[tuple[str, str]] = []
    checks: list[str] = []

    quality = pd.read_csv(DATA_DIR / "data_quality_summary.csv")
    usable = parse_bool(quality["is_usable"])
    if usable.isna().any() or not usable.all():
        issues.append(("High", "至少一只股票未通过数据质量检查。"))
    else:
        checks.append(f"数据质量：{len(quality)}/{len(quality)} 只股票通过重复日期、关键缺失和 OHLC 合法性检查。")

    summary = pd.read_csv(OUTPUT_DIR / "parameter_comparison.csv")
    expected_rows = len(UNIVERSE) * len(PARAMETER_PAIRS) * 3
    if len(summary) != expected_rows:
        issues.append(("High", f"参数汇总应有 {expected_rows} 行，实际为 {len(summary)} 行。"))
    else:
        checks.append(f"参数网格：10 只股票 × 5 组参数 × 3 个样本区间 = {expected_rows} 行。")

    if summary[["cumulative_return", "max_drawdown", "sharpe_ratio"]].isna().any().any():
        issues.append(("Medium", "参数汇总的核心绩效指标存在缺失。"))

    for spec in UNIVERSE:
        path = OUTPUT_DIR / f"{code_slug(spec.ts_code)}_MA5_MA15_backtest.csv"
        if not path.exists():
            issues.append(("High", f"缺少 {spec.ts_code} 默认参数回测文件。"))
            continue
        result = pd.read_csv(path, parse_dates=["trade_date"])
        expected_target = (
            (result["short_ma"] > result["long_ma"] + CROSS_TOLERANCE) & result["long_ma"].notna()
        ).astype(int)
        expected_position = expected_target.shift(1).fillna(0).astype(int)
        if not result["target_position"].astype(int).equals(expected_target):
            issues.append(("High", f"{spec.ts_code} 目标仓位与均线规则不一致。"))
        if not result["position"].astype(int).equals(expected_position):
            issues.append(("High", f"{spec.ts_code} 仓位没有严格错后一日。"))

        expected_cost = result["position"].diff().fillna(result["position"]).abs() * DEFAULT_TRANSACTION_COST
        if not (expected_cost.round(12) == result["transaction_cost"].round(12)).all():
            issues.append(("High", f"{spec.ts_code} 交易成本与换手不一致。"))

        independent_equity = (1 + result["strategy_return"]).cumprod()
        independent_cumulative = independent_equity.iloc[-1] - 1
        independent_drawdown = (independent_equity / independent_equity.cummax() - 1).min()
        full_row = summary.loc[
            (summary["ts_code"] == spec.ts_code)
            & (summary["parameter"] == "MA5/MA15")
            & (summary["sample_period"] == "全样本")
        ].iloc[0]
        if not math.isclose(independent_cumulative, full_row["cumulative_return"], rel_tol=0, abs_tol=1e-10):
            issues.append(("High", f"{spec.ts_code} 累计回报独立复算不一致。"))
        if not math.isclose(independent_drawdown, full_row["max_drawdown"], rel_tol=0, abs_tol=1e-10):
            issues.append(("High", f"{spec.ts_code} 最大回撤独立复算不一致。"))

        chart = OUTPUT_DIR / f"{code_slug(spec.ts_code)}_MA5_MA15_strategy.png"
        if not chart.exists() or chart.stat().st_size < 20_000:
            issues.append(("Medium", f"{spec.ts_code} 回测图缺失或文件异常小。"))

    checks.append("交易逻辑：逐股核对目标仓位、信号错后一日和交易成本。")
    checks.append("核心计算：逐股独立复算 MA5/MA15 全样本累计回报与最大回撤。")

    required_outputs = [
        OUTPUT_DIR / "stock_parameter_sharpe_heatmap.png",
        OUTPUT_DIR / "industry_parameter_sharpe_heatmap.png",
        OUTPUT_DIR / "default_parameter_returns.png",
        OUTPUT_DIR / "analysis_report.md",
        OUTPUT_DIR / "chart_map.csv",
        WEB_DIR / "index.html",
        TASK_DIR / "Task3_process_walkthrough.ipynb",
    ]
    for path in required_outputs:
        if not path.exists() or path.stat().st_size == 0:
            issues.append(("High", f"缺少最终交付物：{path.name}"))

    html = (WEB_DIR / "index.html").read_text(encoding="utf-8") if (WEB_DIR / "index.html").exists() else ""
    missing_names = [spec.stock_name for spec in UNIVERSE if spec.stock_name not in html]
    if missing_names:
        issues.append(("Medium", f"网页未覆盖全部股票：{missing_names}"))
    else:
        checks.append("网页内容：10 只股票均有对应图表入口。")

    assessment = "Ready to share" if not issues else ("Share with caveats" if all(level != "High" for level, _ in issues) else "Needs revision")
    lines = [
        "# Task3 Validation Report",
        "",
        f"## Overall Assessment: {assessment}",
        "",
        "## Methodology Review",
        "",
        "回测问题、股票池、时间范围、交易规则、交易成本、绩效指标和样本内/样本外划分均已在代码与报告中显式记录。策略信号采用错后一日仓位，避免直接使用当日信号赚取当日收益。",
        "",
        "## Calculation Spot-Checks",
        "",
        *[f"- {item}" for item in checks],
        "",
        "## Issues Found",
        "",
        *([f"1. [{level}] {message}" for level, message in issues] if issues else ["- 未发现阻止分享的计算或交付问题。"]),
        "",
        "## Required Caveats for Stakeholders",
        "",
        "- 股票池按当前代表性人工选择，存在幸存者偏差。",
        "- 参数组合经过多重比较，历史最佳不等于未来最佳。",
        "- 回测使用简化交易成本，未模拟涨跌停、成交量约束、滑点差异和整手交易。",
        "- 结果用于教学和研究演示，不构成投资建议。",
    ]
    path = OUTPUT_DIR / "validation_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    if assessment == "Needs revision":
        raise RuntimeError("Task3 validation failed; see validation_report.md")
    return path


if __name__ == "__main__":
    print(validate_results())
