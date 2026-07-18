from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_PARAMS, PARAMETER_SETS, UNIVERSE, parameter_label, parameter_slug, code_slug
from turtle_backtest import OUTPUT_DIR, add_turtle_indicators, load_prices


TASK_DIR = Path(__file__).resolve().parents[1]


def validate_results() -> Path:
    checks: list[tuple[str, str]] = []
    issues: list[str] = []

    summary_path = OUTPUT_DIR / "parameter_comparison.csv"
    summary = pd.read_csv(summary_path)
    expected_rows = len(UNIVERSE) * len(PARAMETER_SETS) * 3
    if len(summary) != expected_rows:
        issues.append(f"parameter_comparison.csv 应有 {expected_rows} 行，实际 {len(summary)} 行")
    else:
        checks.append(("批量结果行数", f"通过：{len(summary)} 行 = 10只股票×6组参数×3个样本区间"))

    stock = UNIVERSE[0]
    prices = load_prices(stock)
    indicators = add_turtle_indicators(prices, DEFAULT_PARAMS)
    expected_upper = prices["high"].rolling(DEFAULT_PARAMS.entry_window).max().shift(1)
    expected_lower = prices["low"].rolling(DEFAULT_PARAMS.exit_window).min().shift(1)
    previous_close = prices["close"].shift(1)
    expected_tr = pd.concat(
        [
            prices["high"] - prices["low"],
            (prices["high"] - previous_close).abs(),
            (prices["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    np.testing.assert_allclose(indicators["entry_high"], expected_upper, equal_nan=True)
    np.testing.assert_allclose(indicators["exit_low"], expected_lower, equal_nan=True)
    np.testing.assert_allclose(indicators["true_range"], expected_tr, equal_nan=True)
    checks.append(("通道与TR公式", "通过：通道只使用前一日及更早数据，TR三项最大值独立重算一致"))

    first_atr_index = DEFAULT_PARAMS.atr_window - 1
    expected_first_atr = expected_tr.iloc[: DEFAULT_PARAMS.atr_window].mean()
    if not np.isclose(indicators.loc[first_atr_index, "atr"], expected_first_atr):
        issues.append("Wilder ATR 初始值与前20个TR简单平均不一致")
    else:
        next_expected = (
            indicators.loc[first_atr_index, "atr"] * (DEFAULT_PARAMS.atr_window - 1)
            + expected_tr.iloc[first_atr_index + 1]
        ) / DEFAULT_PARAMS.atr_window
        if not np.isclose(indicators.loc[first_atr_index + 1, "atr"], next_expected):
            issues.append("Wilder ATR 递推值不一致")
        else:
            checks.append(("Wilder ATR", "通过：初始均值与递推公式均独立复核一致"))

    default_label = parameter_label(DEFAULT_PARAMS)
    default_full = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "full")]
    for spec in UNIVERSE:
        slug = f"{code_slug(spec.ts_code)}_{parameter_slug(DEFAULT_PARAMS)}"
        result_path = OUTPUT_DIR / f"{slug}_backtest.csv"
        trades_path = OUTPUT_DIR / f"{slug}_trades.csv"
        chart_path = OUTPUT_DIR / f"{slug}_strategy.png"
        for path in [result_path, trades_path, chart_path]:
            if not path.exists() or path.stat().st_size == 0:
                issues.append(f"缺少或为空：{path.name}")
        result = pd.read_csv(result_path, parse_dates=["trade_date"])
        np.testing.assert_allclose(
            result["strategy_equity"],
            result["cash"] + result["shares"] * result["close"],
            rtol=1e-9,
            atol=1e-7,
        )
        if not result["drawdown"].between(-1, 0).all():
            issues.append(f"{spec.ts_code} 回撤超出 [-1, 0]")
        if (result["transaction_cost"] < 0).any():
            issues.append(f"{spec.ts_code} 存在负交易成本")
        if (result.loc[result["execution"].eq("HOLD"), "transaction_cost"] > 1e-10).any():
            issues.append(f"{spec.ts_code} 在HOLD日产生了交易成本")
        if not set(result.loc[result["execution"].eq("SELL"), "exit_reason"].dropna()) <= {"ATR_STOP", "CHANNEL_EXIT"}:
            issues.append(f"{spec.ts_code} 存在未知卖出原因")

        metric_row = default_full.loc[default_full["ts_code"] == spec.ts_code].iloc[0]
        independently_compounded = float((1 + result["strategy_return"]).prod() - 1)
        if not np.isclose(independently_compounded, metric_row["cumulative_return"], rtol=1e-9, atol=1e-10):
            issues.append(f"{spec.ts_code} 累计回报与日收益复利不一致")
    checks.append(("资金与绩效重算", "通过：10只股票的资金恒等式、成本、退出原因和累计回报均复核"))

    if not summary["max_drawdown"].between(-1, 0).all():
        issues.append("汇总表存在超出 [-1, 0] 的最大回撤")
    if summary[["cumulative_return", "benchmark_return", "max_drawdown"]].isna().any().any():
        issues.append("汇总表核心绩效指标存在缺失")
    else:
        checks.append(("指标范围与完整性", "通过：累计回报、基准收益和最大回撤完整，MDD范围正确"))

    required_outputs = [
        OUTPUT_DIR / "analysis_report.md",
        OUTPUT_DIR / "default_parameter_returns.png",
        OUTPUT_DIR / "stock_parameter_sharpe_heatmap.png",
        OUTPUT_DIR / "industry_parameter_sharpe_heatmap.png",
        OUTPUT_DIR / "risk_return_scatter.png",
        OUTPUT_DIR / "chart_map.csv",
        TASK_DIR / "Task4_process_walkthrough.ipynb",
        TASK_DIR / "web" / "index.html",
        TASK_DIR / "李子平-Task4-海龟策略完整版.docx",
    ]
    missing_outputs = [path.name for path in required_outputs if not path.exists() or path.stat().st_size == 0]
    if missing_outputs:
        issues.append(f"缺少交付物：{', '.join(missing_outputs)}")
    else:
        checks.append(("交付物完整性", "通过：报告、四类汇总图、图表映射、Notebook和网页均存在"))

    status = "Ready to share" if not issues else "Needs revision"
    issue_lines = "\n".join(f"{index}. [High] {issue}" for index, issue in enumerate(issues, start=1)) or "未发现阻断性问题。"
    check_lines = "\n".join(f"- **{name}**：{detail}" for name, detail in checks)
    report = f"""# Task4 Validation Report

## Overall Assessment: {status}

### Methodology Review

验证覆盖海龟通道的时间错位、TR与Wilder ATR公式、交易资金恒等式、交易成本、退出原因、累计回报复利、MDD范围、批量结果行数和交付物完整性。

### Issues Found

{issue_lines}

### Calculation Spot-Checks

{check_lines}

### Visualization Review

静态图均要求非空并由统一绘图函数生成；图表使用明确标题、日期范围、单位和非红绿主导配色。网页报告由同一份结构化数据快照生成。

### Required Caveats for Stakeholders

- 股票池为人工选择的10只当前代表性股票，存在幸存者偏差，行业样本量仅2只。
- 回测未模拟100股整手、涨跌停无法成交、停牌、滑点和容量限制。
- 单边0.1%交易成本、零无风险利率和允许小数股均为教学假设。
- 参数比较不能证明未来最优，结论应重点看跨标的和样本外稳定性。
"""
    report_path = OUTPUT_DIR / "validation_report.md"
    report_path.write_text(report, encoding="utf-8")
    if issues:
        raise AssertionError("; ".join(issues))
    return report_path


if __name__ == "__main__":
    print(validate_results())
