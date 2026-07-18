from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

from config import DEFAULT_PARAMS, parameter_label
from turtle_backtest import OUTPUT_DIR, setup_plot_style


CHART_MAP_PATH = OUTPUT_DIR / "chart_map.csv"
INDUSTRY_COLORS = {
    "银行": "#2563eb",
    "食品饮料": "#d97706",
    "新能源汽车": "#7a8b22",
    "半导体": "#db2777",
    "工程机械": "#b38b00",
}


def fmt_percent(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.1%}"


def fmt_number(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.2f}"


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "（无可用数据）"
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def plot_default_returns(default_oos: pd.DataFrame, output: Path) -> None:
    setup_plot_style()
    data = default_oos.sort_values("cumulative_return", ascending=True).copy()
    y = np.arange(len(data))
    fig, axis = plt.subplots(figsize=(11.5, 6.8))
    colors = np.where(data["cumulative_return"] >= 0, "#2563eb", "#d97706")
    bars = axis.barh(y, data["cumulative_return"] * 100, height=0.56, color=colors, edgecolor="#ffffff", linewidth=0.6)
    axis.set_yticks(y, data["stock_name"])
    axis.axvline(0, color="#334155", linewidth=0.9)
    axis.set_xlabel("累计回报（%）")
    for bar, value in zip(bars, data["cumulative_return"] * 100):
        offset = 0.25 if value >= 0 else -0.25
        alignment = "left" if value >= 0 else "right"
        axis.text(value + offset, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", ha=alignment, va="center", fontsize=9)
    fig.suptitle("默认参数下各股票样本外累计回报", x=0.085, y=0.985, ha="left", fontsize=14)
    fig.text(0.085, 0.948, "2024-01至2026-07，E20/X10/ATR20/S2；蓝色为正收益，橙色为负收益", color="#475569", fontsize=10)
    axis.grid(axis="x")
    axis.grid(axis="y", visible=False)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_heatmap(frame: pd.DataFrame, row_field: str, title: str, subtitle: str, output: Path) -> None:
    setup_plot_style()
    pivot = frame.pivot(index=row_field, columns="parameter", values="sharpe_ratio")
    ordered_columns = list(dict.fromkeys(frame["parameter"].tolist()))
    pivot = pivot.reindex(columns=[column for column in ordered_columns if column in pivot.columns])
    values = pivot.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    max_abs = max(abs(finite.min()), abs(finite.max()), 0.5) if finite.size else 1.0
    cmap = LinearSegmentedColormap.from_list("turtle_diverging", ["#d97706", "#fff7ed", "#2563eb"])
    fig_width = 12 if len(pivot.columns) > 4 else 9
    fig_height = max(4.6, 0.52 * len(pivot.index) + 2.2)
    fig, axis = plt.subplots(figsize=(fig_width, fig_height))
    image = axis.imshow(values, aspect="auto", cmap=cmap, vmin=-max_abs, vmax=max_abs)
    axis.set_xticks(np.arange(len(pivot.columns)), pivot.columns, rotation=25, ha="right")
    axis.set_yticks(np.arange(len(pivot.index)), pivot.index)
    for row in range(values.shape[0]):
        for column in range(values.shape[1]):
            value = values[row, column]
            label = "—" if not np.isfinite(value) else f"{value:.2f}"
            axis.text(column, row, label, ha="center", va="center", fontsize=8.5, color="#0f172a")
    fig.suptitle(title, x=0.105, y=0.99, ha="left", fontsize=14)
    fig.text(0.105, 0.91, subtitle, color="#475569", fontsize=10)
    axis.set_xlabel("参数组合")
    axis.set_ylabel("")
    colorbar = fig.colorbar(image, ax=axis, fraction=0.025, pad=0.025)
    colorbar.set_label("夏普比率")
    axis.spines[:].set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_risk_return(default_oos: pd.DataFrame, output: Path) -> None:
    setup_plot_style()
    fig, axis = plt.subplots(figsize=(10.8, 6.6))
    for industry, group in default_oos.groupby("industry"):
        axis.scatter(
            -group["max_drawdown"] * 100,
            group["cumulative_return"] * 100,
            s=70,
            color=INDUSTRY_COLORS.get(industry, "#2563eb"),
            label=industry,
            edgecolor="white",
            linewidth=0.8,
        )
        for row in group.itertuples():
            axis.annotate(row.stock_name, (-row.max_drawdown * 100, row.cumulative_return * 100), xytext=(5, 5), textcoords="offset points", fontsize=8)
    axis.axhline(0, color="#334155", linewidth=0.9)
    axis.set_xlabel("最大回撤幅度（%）")
    axis.set_ylabel("累计回报（%）")
    fig.suptitle("默认参数样本外风险—收益分布", x=0.085, y=0.99, ha="left", fontsize=14)
    fig.text(0.085, 0.91, "2024-01至2026-07；越靠左上表示回撤较小且收益较高", color="#475569", fontsize=10)
    axis.legend(title="行业", loc="best", ncol=2, fontsize=9)
    axis.grid(True)
    axis.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_analysis_report(summary: pd.DataFrame, industry_summary: pd.DataFrame) -> Path:
    default_label = parameter_label(DEFAULT_PARAMS)
    default_full = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "full")].copy()
    default_oos = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "out_of_sample")].copy()
    oos = summary.loc[summary["sample_period"] == "out_of_sample"].copy()
    parameter_oos = (
        oos.groupby("parameter", as_index=False)
        .agg(
            median_return=("cumulative_return", "median"),
            median_sharpe=("sharpe_ratio", "median"),
            median_mdd=("max_drawdown", "median"),
            positive_share=("cumulative_return", lambda values: float((values > 0).mean())),
            median_trades=("completed_trades", "median"),
        )
        .sort_values(["median_sharpe", "median_return"], ascending=False)
    )

    best_stock = default_oos.sort_values("sharpe_ratio", ascending=False).iloc[0]
    worst_stock = default_oos.sort_values("sharpe_ratio", ascending=True).iloc[0]
    best_parameter = parameter_oos.iloc[0]
    positive_count = int((default_oos["cumulative_return"] > 0).sum())

    top_table = default_oos.sort_values("sharpe_ratio", ascending=False).loc[
        :, ["stock_name", "industry", "cumulative_return", "max_drawdown", "sharpe_ratio", "completed_trades", "win_rate"]
    ].copy()
    top_table.columns = ["股票", "行业", "累计回报", "最大回撤", "夏普比率", "完成交易", "胜率"]
    top_table["累计回报"] = top_table["累计回报"].map(fmt_percent)
    top_table["最大回撤"] = top_table["最大回撤"].map(fmt_percent)
    top_table["夏普比率"] = top_table["夏普比率"].map(fmt_number)
    top_table["胜率"] = top_table["胜率"].map(fmt_percent)

    parameter_table = parameter_oos.copy()
    parameter_table.columns = ["参数", "中位累计回报", "中位夏普", "中位最大回撤", "正收益占比", "中位交易数"]
    parameter_table["中位累计回报"] = parameter_table["中位累计回报"].map(fmt_percent)
    parameter_table["中位最大回撤"] = parameter_table["中位最大回撤"].map(fmt_percent)
    parameter_table["正收益占比"] = parameter_table["正收益占比"].map(fmt_percent)
    parameter_table["中位夏普"] = parameter_table["中位夏普"].map(fmt_number)
    parameter_table["中位交易数"] = parameter_table["中位交易数"].map(lambda value: f"{value:.1f}")

    report = f"""# Task4 海龟交易策略：回测与参数研究

## 技术摘要

- 默认参数 `{default_label}` 在样本外10只股票中有 **{positive_count}/10** 取得正累计回报；跨股票中位累计回报为 **{fmt_percent(default_oos['cumulative_return'].median())}**，中位夏普比率为 **{fmt_number(default_oos['sharpe_ratio'].median())}**，中位最大回撤为 **{fmt_percent(default_oos['max_drawdown'].median())}**。
- 默认参数样本外表现最好的是 **{best_stock['stock_name']}**：累计回报 {fmt_percent(best_stock['cumulative_return'])}、最大回撤 {fmt_percent(best_stock['max_drawdown'])}、夏普比率 {fmt_number(best_stock['sharpe_ratio'])}；表现最弱的是 **{worst_stock['stock_name']}**，说明单一趋势策略对标的和行情阶段高度敏感。
- 按10只股票样本外中位夏普排序，表现最好的参数组合是 **{best_parameter['parameter']}**，中位夏普 {fmt_number(best_parameter['median_sharpe'])}、中位累计回报 {fmt_percent(best_parameter['median_return'])}。该结果仅用于稳健性比较，不应被视为未来最优参数。

## 海龟策略的核心思想与优势

海龟交易法则属于规则化趋势跟踪策略：当价格向上突破过去一段时间的最高价时入场，让盈利头寸跟随趋势；当价格跌破较短周期低点或触发波动率止损时离场。ATR把不同股票的波动尺度转换成可比较的风险单位，并用于确定止损距离和仓位规模。

主要优势包括：规则客观、容易复现；能够保留少数大趋势带来的收益；ATR风险定仓使高波动股票自动降低仓位；通道、仓位和止损均可清晰审计。其代价是震荡行情中容易连续出现小额亏损，胜率通常不高，且真实交易会受跳空、滑点、涨跌停和成交量约束影响。

## 数据、定义与回测口径

- 数据：Task3保存的10只A股前复权日线，覆盖2019-01至2026-07；关键字段为交易日、开盘价、最高价、最低价和收盘价。
- 入场：收盘价首次突破“截至前一交易日”的N日最高价；信号下一交易日开盘执行。
- 离场：上一日收盘价跌破M日最低通道，则下一交易日开盘卖出；若持仓日最低价触及预先设置的初始止损，则按止损价成交，跳空低开时按开盘价成交。
- ATR：真实波幅取 `max(最高-最低, |最高-昨收|, |最低-昨收|)`，再使用Wilder递推平均。
- 仓位：每笔交易计划风险为账户权益的1%，股数为“风险预算 /（止损倍数×ATR）”，资金使用不超过100%。允许教学用小数股，不模拟整手约束。
- 成本：买卖单边综合交易成本均按0.1%估计；不做空、不加杠杆、不加仓。
- 样本：2019-2023为样本内，2024-01至2026-07为样本外。夏普比率使用日收益、零无风险利率和252个交易日年化。

## 默认参数的样本外结果

{markdown_table(top_table)}

图表 `default_parameter_returns.png` 比较了默认参数的样本外累计回报；买入持有基准保留在上表和网页报告中，避免极端上涨基准压缩策略柱形。`risk_return_scatter.png` 将样本外累计回报与最大回撤并列展示。单只股票的策略图同时给出股价、通道、买卖执行点、ATR、止损线、净值和回撤。

## 参数敏感性

{markdown_table(parameter_table)}

`stock_parameter_sharpe_heatmap.png` 显示同一参数在不同股票上可能产生相反结果；`industry_parameter_sharpe_heatmap.png` 进一步按行业中位数汇总。比起挑选最高收益参数，更重要的是寻找在多只股票、多个行业和样本外区间都不过度失真的参数区域。

## 适应场景与使用心得

海龟法则更适合趋势持续、流动性较好、能够分散持有多个标的的场景。单只股票长期横盘、频繁跳空或受事件驱动时，通道突破可能很快失败。实践中应同时观察累计回报、夏普比率、最大回撤、交易次数、胜率、持仓比例与基准收益，不能只看最高收益。

本次结果表明：通道周期决定策略对趋势的敏感度，短通道交易更频繁且更容易受噪声影响，长通道通常减少交易但可能错过趋势前段；ATR倍数过小容易被正常波动触发，过大则扩大单股止损距离并降低风险定仓数量。参数选择应优先依据跨标的和样本外稳定性，而不是全样本最优值。

## 局限、稳健性与下一步

- 本回测是教学模型，未模拟A股100股整手、涨跌停无法成交、停牌、滑点、容量和税费结构变化。
- 股票池为人工挑选的当前代表性股票，存在幸存者偏差；行业样本每组仅2只股票，不能代表完整行业。
- 前复权价格适合收益路径比较，但实际成交价格和现金分红处理仍是简化假设。
- 下一步可加入滚动样本外检验、更多股票、组合级风险预算、真实交易日历和成交限制，并比较海龟策略与双均线及买入持有基准。
"""
    output = OUTPUT_DIR / "analysis_report.md"
    output.write_text(report, encoding="utf-8")
    return output


def build_analysis_outputs() -> dict[str, Path]:
    summary = pd.read_csv(OUTPUT_DIR / "parameter_comparison.csv")
    industry_summary = pd.read_csv(OUTPUT_DIR / "industry_parameter_summary.csv")
    default_label = parameter_label(DEFAULT_PARAMS)
    default_oos = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "out_of_sample")]
    oos = summary.loc[summary["sample_period"] == "out_of_sample"]
    industry_oos = industry_summary.loc[industry_summary["sample_period"] == "out_of_sample"].rename(columns={"median_sharpe_ratio": "sharpe_ratio"})

    outputs = {
        "default_returns": OUTPUT_DIR / "default_parameter_returns.png",
        "stock_heatmap": OUTPUT_DIR / "stock_parameter_sharpe_heatmap.png",
        "industry_heatmap": OUTPUT_DIR / "industry_parameter_sharpe_heatmap.png",
        "risk_return": OUTPUT_DIR / "risk_return_scatter.png",
    }
    plot_default_returns(default_oos, outputs["default_returns"])
    plot_heatmap(oos, "stock_name", "股票—参数夏普比率", "样本外：2024-01至2026-07；蓝色较高、橙色较低", outputs["stock_heatmap"])
    plot_heatmap(industry_oos, "industry", "行业—参数中位夏普比率", "每个行业含2只代表性股票；样本外：2024-01至2026-07", outputs["industry_heatmap"])
    plot_risk_return(default_oos, outputs["risk_return"])

    chart_map = pd.DataFrame(
        [
            {"section": "默认参数", "question": "默认策略的样本外累计回报如何", "family": "comparison", "chart_type": "horizontal bar", "fields": "stock_name,cumulative_return", "takeaway": "比较策略的跨股票差异", "palette": "blue + orange signed", "artifact": outputs["default_returns"].name},
            {"section": "参数敏感性", "question": "参数表现是否跨股票稳定", "family": "matrix", "chart_type": "heatmap", "fields": "stock_name,parameter,sharpe_ratio", "takeaway": "识别参数与股票的交互差异", "palette": "blue + orange diverging", "artifact": outputs["stock_heatmap"].name},
            {"section": "行业适应性", "question": "行业层面的参数中位表现如何", "family": "matrix", "chart_type": "heatmap", "fields": "industry,parameter,median_sharpe_ratio", "takeaway": "观察行业间稳健性", "palette": "blue + orange diverging", "artifact": outputs["industry_heatmap"].name},
            {"section": "风险收益", "question": "默认参数的收益与回撤如何权衡", "family": "relationship", "chart_type": "scatter", "fields": "stock_name,industry,cumulative_return,max_drawdown", "takeaway": "左上方股票风险收益更优", "palette": "five-category", "artifact": outputs["risk_return"].name},
        ]
    )
    chart_map.to_csv(CHART_MAP_PATH, index=False, encoding="utf-8-sig")
    outputs["chart_map"] = CHART_MAP_PATH
    outputs["analysis_report"] = build_analysis_report(summary, industry_summary)
    return outputs


if __name__ == "__main__":
    for name, path in build_analysis_outputs().items():
        print(f"{name}: {path}")
