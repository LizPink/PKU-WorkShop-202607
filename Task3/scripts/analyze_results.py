from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd

from config import DEFAULT_LONG_WINDOW, DEFAULT_SHORT_WINDOW, PARAMETER_PAIRS, parameter_label
from strategy_backtest import DATA_DIR, OUTPUT_DIR, setup_plot_style


TASK_DIR = Path(__file__).resolve().parents[1]
PERCENT_COLUMNS = {
    "cumulative_return",
    "annualized_return",
    "annualized_volatility",
    "max_drawdown",
    "benchmark_return",
    "excess_return",
    "holding_ratio",
    "收益中位数",
    "最大回撤中位数",
    "正收益比例",
    "策略累计回报",
    "最大回撤",
    "买入持有回报",
}
DIVERGING_CMAP = LinearSegmentedColormap.from_list(
    "orange_white_blue",
    ["#c2410c", "#fed7aa", "#f8fafc", "#bfdbfe", "#1d4ed8"],
)


def format_percent(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.2%}"


def format_number(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.3f}"


def annotated_heatmap(
    table: pd.DataFrame,
    title: str,
    subtitle: str,
    output: Path,
    percent: bool = False,
) -> None:
    setup_plot_style()
    values = table.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    max_abs = max(abs(float(finite.min())), abs(float(finite.max())), 1e-9)
    norm = TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)
    fig_height = max(5.2, 0.48 * len(table.index) + 2.0)
    fig, axis = plt.subplots(figsize=(10.8, fig_height))
    image = axis.imshow(values, cmap=DIVERGING_CMAP, norm=norm, aspect="auto")
    axis.set_xticks(range(len(table.columns)), table.columns)
    axis.set_yticks(range(len(table.index)), table.index)
    axis.set_xlabel("均线参数")
    axis.set_ylabel("")
    axis.set_title(title, loc="left", fontsize=14, pad=22)
    axis.text(0, 1.015, subtitle, transform=axis.transAxes, fontsize=9.5, color="#475569", va="bottom")
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            value = values[row, col]
            label = "—" if not np.isfinite(value) else (f"{value:.1%}" if percent else f"{value:.2f}")
            color = "white" if np.isfinite(value) and abs(value) > max_abs * 0.56 else "#1f2937"
            axis.text(col, row, label, ha="center", va="center", fontsize=8.5, color=color)
    axis.tick_params(length=0)
    for spine in axis.spines.values():
        spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=axis, fraction=0.028, pad=0.025)
    colorbar.ax.set_ylabel("收益率" if percent else "夏普比率", rotation=90)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_default_returns(summary: pd.DataFrame, output: Path) -> None:
    setup_plot_style()
    default = summary.loc[
        (summary["sample_period"] == "样本外")
        & (summary["short_window"] == DEFAULT_SHORT_WINDOW)
        & (summary["long_window"] == DEFAULT_LONG_WINDOW)
    ].copy()
    default = default.sort_values("cumulative_return")
    labels = default["stock_name"] + "｜" + default["industry"]
    colors = np.where(default["cumulative_return"] >= 0, "#2563eb", "#d97706")
    fig, axis = plt.subplots(figsize=(10.5, 6.3))
    bars = axis.barh(labels, default["cumulative_return"] * 100, color=colors, edgecolor="#334155", linewidth=0.45)
    axis.axvline(0, color="#334155", linewidth=0.9)
    axis.set_title("MA5/MA15 样本外累计回报", loc="left", fontsize=14, pad=22)
    axis.text(0, 1.015, "2024-01-01 至数据截止日；蓝色为正收益，橙色为负收益", transform=axis.transAxes, fontsize=9.5, color="#475569", va="bottom")
    axis.set_xlabel("累计回报（%）")
    axis.set_ylabel("")
    for bar, value in zip(bars, default["cumulative_return"] * 100):
        x = value + (0.7 if value >= 0 else -0.7)
        axis.text(x, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", ha="left" if value >= 0 else "right", fontsize=8.5)
    axis.grid(True, axis="x")
    axis.grid(False, axis="y")
    axis.spines[["top", "right", "left"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.columns:
        if column in PERCENT_COLUMNS:
            display[column] = display[column].map(format_percent)
        elif pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "—" if pd.isna(value) else f"{value:.3f}")
    header = "| " + " | ".join(map(str, display.columns)) + " |"
    separator = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in display.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def build_report(summary: pd.DataFrame, industry_summary: pd.DataFrame, quality: pd.DataFrame) -> Path:
    out_of_sample = summary.loc[summary["sample_period"] == "样本外"].copy()
    global_parameter = (
        out_of_sample.groupby(["parameter", "short_window", "long_window"], as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            median_cumulative_return=("cumulative_return", "median"),
            median_sharpe_ratio=("sharpe_ratio", "median"),
            median_max_drawdown=("max_drawdown", "median"),
            positive_return_share=("cumulative_return", lambda values: float((values > 0).mean())),
            median_buy_count=("buy_count", "median"),
        )
        .sort_values("median_sharpe_ratio", ascending=False)
    )
    best = global_parameter.iloc[0]
    default = out_of_sample.loc[
        (out_of_sample["short_window"] == DEFAULT_SHORT_WINDOW)
        & (out_of_sample["long_window"] == DEFAULT_LONG_WINDOW)
    ].sort_values("sharpe_ratio", ascending=False)
    best_stock = default.iloc[0]
    worst_stock = default.iloc[-1]
    positive_default_count = int((default["cumulative_return"] > 0).sum())
    beat_benchmark_count = int((default["excess_return"] > 0).sum())
    median_default_excess = float(default["excess_return"].median())
    quality_ok = int(quality["is_usable"].astype(str).str.lower().eq("true").sum())
    actual_start = quality["actual_start"].min()
    actual_end = quality["actual_end"].max()

    global_display = global_parameter[
        ["parameter", "stock_count", "median_cumulative_return", "median_sharpe_ratio", "median_max_drawdown", "positive_return_share", "median_buy_count"]
    ].rename(
        columns={
            "parameter": "参数",
            "stock_count": "股票数",
            "median_cumulative_return": "收益中位数",
            "median_sharpe_ratio": "夏普中位数",
            "median_max_drawdown": "最大回撤中位数",
            "positive_return_share": "正收益比例",
            "median_buy_count": "买入次数中位数",
        }
    )
    default_display = default[
        ["stock_name", "industry", "cumulative_return", "sharpe_ratio", "max_drawdown", "benchmark_return", "buy_count"]
    ].rename(
        columns={
            "stock_name": "股票",
            "industry": "行业",
            "cumulative_return": "策略累计回报",
            "sharpe_ratio": "夏普比率",
            "max_drawdown": "最大回撤",
            "benchmark_return": "买入持有回报",
            "buy_count": "买入次数",
        }
    )
    quality_display = quality[
        ["stock_name", "industry", "actual_start", "actual_end", "rows", "duplicate_dates", "missing_required_values", "invalid_ohlc_rows", "source", "is_usable"]
    ].rename(
        columns={
            "stock_name": "股票",
            "industry": "行业",
            "actual_start": "起始日期",
            "actual_end": "截止日期",
            "rows": "交易日数",
            "duplicate_dates": "重复日期",
            "missing_required_values": "关键缺失",
            "invalid_ohlc_rows": "无效OHLC",
            "source": "数据来源",
            "is_usable": "可用于回测",
        }
    )

    lines = [
        "# Task3：双均线策略与跨行业回测",
        "",
        "## 结论摘要",
        "",
        f"- 本次使用 5 个行业、10 只股票的日频前复权行情，数据范围约为 {actual_start} 至 {actual_end}；{quality_ok}/{len(quality)} 只股票通过关键质量检查。",
        f"- 样本外（2024-01-01 起）跨股票夏普比率中位数最高的参数是 **{best['parameter']}**，但这只是本股票池上的历史结果，不代表未来最优。",
        f"- 默认 MA5/MA15 中，样本外夏普最高的是 **{best_stock['stock_name']}**（{format_number(best_stock['sharpe_ratio'])}），最低的是 **{worst_stock['stock_name']}**（{format_number(worst_stock['sharpe_ratio'])}），说明同一规则在不同行业和行情中差异明显。",
        f"- 默认 MA5/MA15 在样本外有 **{positive_default_count}/10** 只股票取得正收益，但只有 **{beat_benchmark_count}/10** 战胜对应的买入持有；超额收益中位数为 {format_percent(median_default_excess)}。正收益不等于择时有效。",
        "- 短周期通常更灵敏、交易次数更多；长周期通常更平滑但反应更慢。判断策略不能只看累计收益，还要同时查看最大回撤、夏普比率、交易成本与买入持有基准。",
        "",
        "## 双均线策略与交易规则",
        "",
        "- **金叉**：短期均线由不高于长期均线转为高于长期均线，产生买入信号。",
        "- **死叉**：短期均线由高于长期均线转为不高于长期均线，产生卖出信号。",
        "- 策略只做多、不做空、不使用杠杆；空仓时资金收益按 0 处理。",
        "- t 日收盘后计算目标仓位，t+1 日才应用，避免把信号日已经发生的收益计入策略。",
        "- 初始资金为 100,000 元，每次在 0% 与 100% 仓位之间切换；单边综合交易成本假设为 0.1%。",
        "- 长均线尚未形成时保持空仓；停牌日不制造价格，交易自然顺延到该股票下一条真实行情。",
        "",
        "## 绩效指标",
        "",
        "- **累计回报**：期末净值 ÷ 期初净值 − 1。",
        "- **最大回撤（MDD）**：每个交易日净值相对历史最高净值的跌幅，其中最小值即最大回撤。",
        "- **夏普比率**：日均策略收益 ÷ 日收益标准差 × √252；本教学案例的无风险利率设为 0。",
        "- **买入持有基准**：从样本期开始一直持有同一只股票，用于判断择时是否真正带来改善。",
        "",
        "## 样本外参数比较",
        "",
        markdown_table(global_display),
        "",
        "## 默认 MA5/MA15 的股票比较",
        "",
        markdown_table(default_display),
        "",
        "## 数据质量检查",
        "",
        markdown_table(quality_display),
        "",
        "## 图表索引",
        "",
        "- `stock_parameter_sharpe_heatmap.png`：10 只股票、5 组参数的样本外夏普比率。",
        "- `industry_parameter_sharpe_heatmap.png`：各行业的样本外夏普比率中位数。",
        "- `default_parameter_returns.png`：MA5/MA15 在不同股票上的样本外累计回报。",
        "- `*_MA5_MA15_strategy.png`：单只股票的价格、均线、交易执行点、净值和回撤。",
        "",
        "## 适用场景与局限",
        "",
        "双均线属于趋势跟随策略，更适合方向持续性较强的行情。在横盘震荡中，短长均线可能反复交叉，导致频繁交易和成本侵蚀。股票池是按当前可见代表性人工挑选，存在幸存者偏差；参数组合也经过多重比较，因此不能把历史最优直接视为未来规则。更严格的研究应使用滚动样本外检验、更多市场阶段以及真实交易费率和成交约束。",
        "",
        "数据源方面，优先使用 TuShare Pro 的 daily 与 adj_factor；由于当前 Token 的 adj_factor 存在严格限频，部分股票使用 TuShare Pro 日线校验交易日期，并从公开前复权接口或 TuShare legacy qfq 补充前复权 OHLC。每只股票的实际来源已记录在质量表和原始 CSV 中。",
    ]
    path = OUTPUT_DIR / "analysis_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_analysis_outputs() -> dict[str, Path]:
    summary = pd.read_csv(OUTPUT_DIR / "parameter_comparison.csv")
    industry_summary = pd.read_csv(OUTPUT_DIR / "industry_parameter_summary.csv")
    quality = pd.read_csv(DATA_DIR / "data_quality_summary.csv")
    out_of_sample = summary.loc[summary["sample_period"] == "样本外"]
    parameter_order = [parameter_label(short, long) for short, long in PARAMETER_PAIRS]

    stock_sharpe = out_of_sample.pivot(index="stock_name", columns="parameter", values="sharpe_ratio").reindex(columns=parameter_order)
    industry_sharpe = (
        industry_summary.loc[industry_summary["sample_period"] == "样本外"]
        .pivot(index="industry", columns="parameter", values="median_sharpe_ratio")
        .reindex(columns=parameter_order)
    )
    stock_heatmap = OUTPUT_DIR / "stock_parameter_sharpe_heatmap.png"
    industry_heatmap = OUTPUT_DIR / "industry_parameter_sharpe_heatmap.png"
    default_returns = OUTPUT_DIR / "default_parameter_returns.png"
    annotated_heatmap(stock_sharpe, "股票与参数的样本外夏普比率", "2024-01-01 至数据截止日；数值越高表示单位波动对应的平均收益越高", stock_heatmap)
    annotated_heatmap(industry_sharpe, "行业与参数的样本外夏普比率中位数", "每个行业包含 2 只股票；用于观察策略在不同市场风格中的稳定性", industry_heatmap)
    plot_default_returns(summary, default_returns)
    report = build_report(summary, industry_summary, quality)

    chart_map = pd.DataFrame(
        [
            {
                "artifact": stock_heatmap.name,
                "question": "不同股票和均线参数的样本外风险调整收益有何差异？",
                "chart_family": "Matrix & Cohort",
                "chart_type": "annotated heatmap",
                "scope": "10 stocks x 5 parameter pairs, out-of-sample",
            },
            {
                "artifact": industry_heatmap.name,
                "question": "双均线策略在不同行业中的稳定性有何差异？",
                "chart_family": "Matrix & Cohort",
                "chart_type": "annotated heatmap",
                "scope": "5 industries x 5 parameter pairs, out-of-sample median",
            },
            {
                "artifact": default_returns.name,
                "question": "默认 MA5/MA15 在各股票上的样本外累计回报如何？",
                "chart_family": "Comparison & Ranking",
                "chart_type": "signed horizontal bar",
                "scope": "10 stocks, out-of-sample",
            },
            {
                "artifact": "*_MA5_MA15_strategy.png",
                "question": "单只股票的价格、交易信号、策略净值和回撤如何演变？",
                "chart_family": "Trend",
                "chart_type": "three-panel line and area chart",
                "scope": "full sample per stock",
            },
        ]
    )
    chart_map.to_csv(OUTPUT_DIR / "chart_map.csv", index=False, encoding="utf-8-sig")
    return {
        "stock_heatmap": stock_heatmap,
        "industry_heatmap": industry_heatmap,
        "default_returns": default_returns,
        "report": report,
    }


if __name__ == "__main__":
    for name, path in build_analysis_outputs().items():
        print(f"{name}: {path}")
