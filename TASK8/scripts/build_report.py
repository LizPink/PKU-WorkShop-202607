from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor, Twips

plt = None
FancyBboxPatch = None
FancyArrowPatch = None


ROOT = Path(__file__).resolve().parents[2]
TASK8_DIR = ROOT / "TASK8"
OUTPUT_DIR = TASK8_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
REPORT_DIR = TASK8_DIR / "report"
TOC_PAGES_PATH = OUTPUT_DIR / "toc_pages.json"

AUTHOR = "李子平"
REPORT_DATE = "2026 年 7 月 22 日"
TITLE = "从规则策略到机器学习选股"
SUBTITLE = "量化交易实践总结与多策略系统设计"
SUBMISSION_STEM = f"{AUTHOR}TASK8"

FONT_BODY = "SimSun"
FONT_HEADING = "SimHei"
FONT_CHART = "Microsoft YaHei"
BODY_SIZE = 10.5
TABLE_SIZE = 8.8
CONTENT_WIDTH_DXA = 9025

INK = "25313A"
BLUE = "2F6B8A"
BLUE_DARK = "244C61"
BLUE_LIGHT = "E8F1F5"
GOLD = "C6912B"
ORANGE = "D77A3D"
PINK = "B45B7C"
OLIVE = "738154"
MUTED = "6B747C"
LIGHT_GRAY = "F4F6F7"
GRID = "B7C1C8"
WHITE = "FFFFFF"

PALETTE = {
    "blue": "#2F6B8A",
    "blue_dark": "#244C61",
    "blue_light": "#B9D4DF",
    "gold": "#C6912B",
    "orange": "#D77A3D",
    "pink": "#B45B7C",
    "olive": "#738154",
    "gray": "#7B858D",
    "light_gray": "#DCE2E5",
    "ink": "#25313A",
}


TOC_ENTRIES = [
    (1, "摘要"),
    (1, "1 量化交易核心概念与研究框架"),
    (2, "1.1 从数据到决策的完整链条"),
    (2, "1.2 核心价值、评价原则与研究边界"),
    (2, "1.3 六项任务形成的递进式学习路线"),
    (1, "2 量化交易策略综合分析"),
    (2, "2.1 技术指标是信息压缩工具而非独立答案"),
    (2, "2.2 双均线策略具有趋势捕捉能力但超额收益不足"),
    (2, "2.3 海龟策略以风险预算换取更平稳的损失路径"),
    (2, "2.4 不同策略的适用场景、关联性与互补性"),
    (2, "2.5 多策略量化交易系统的构建思路"),
    (1, "3 机器学习在量化交易中的应用总结"),
    (2, "3.1 从通用分类实验到金融预测问题"),
    (2, "3.2 数据预处理、特征工程与防止信息泄漏"),
    (2, "3.3 模型选择、训练与评价"),
    (2, "3.4 机器学习选股取得正收益但未形成稳定超额"),
    (2, "3.5 机器学习的优势、局限与发展趋势"),
    (1, "4 结论与展望"),
    (2, "4.1 主要结论"),
    (2, "4.2 学习收获与能力提升"),
    (2, "4.3 后续研究计划"),
    (1, "参考文献"),
    (1, "附录 改进建议"),
]


def ensure_dirs() -> None:
    for path in (OUTPUT_DIR, FIGURE_DIR, REPORT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def read_inputs() -> dict[str, object]:
    task1 = pd.read_csv(ROOT / "Task1/data/cambricon_688256_SH_daily_combined_20250704_20260704.csv")
    task2_diag = pd.read_csv(ROOT / "Task2/outputs/diagnostics_summary.csv")
    task2_latest = pd.read_csv(ROOT / "Task2/outputs/latest_indicator_snapshot.csv")
    task3 = pd.read_csv(ROOT / "Task3/outputs/parameter_comparison.csv")
    task4 = pd.read_csv(ROOT / "Task4/outputs/parameter_comparison.csv")
    task5_metrics = pd.read_csv(ROOT / "TASK5/outputs/metrics.csv")
    task5_quality = json.loads((ROOT / "TASK5/outputs/data_quality.json").read_text(encoding="utf-8"))
    task6_quality = json.loads((ROOT / "TASK6/outputs/data_quality.json").read_text(encoding="utf-8"))
    task6_summary = json.loads((ROOT / "TASK6/outputs/analysis_summary.json").read_text(encoding="utf-8"))
    task6_model = pd.read_csv(ROOT / "TASK6/outputs/model_metrics.csv")
    task6_backtest = pd.read_csv(ROOT / "TASK6/outputs/backtest_metrics.csv")
    task6_ic = pd.read_csv(ROOT / "TASK6/outputs/quarterly_ic.csv")
    task6_returns = pd.read_csv(ROOT / "TASK6/outputs/quarterly_returns.csv")
    task6_cost = pd.read_csv(ROOT / "TASK6/outputs/cost_sensitivity.csv")

    task3_oos = task3.loc[task3["sample_period"] == "样本外"].copy()
    task3_default = task3_oos.loc[task3_oos["parameter"] == "MA5/MA15"].copy()
    task3_param = (
        task3_oos.groupby("parameter", as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            median_return=("cumulative_return", "median"),
            median_sharpe=("sharpe_ratio", "median"),
            median_drawdown=("max_drawdown", "median"),
            positive_share=("cumulative_return", lambda x: float((x > 0).mean())),
            median_trades=("buy_count", "median"),
        )
        .sort_values("median_sharpe", ascending=False)
    )
    task3_default["beat_benchmark"] = task3_default["cumulative_return"] > task3_default["benchmark_return"]

    task4_oos = task4.loc[task4["sample_period"] == "out_of_sample"].copy()
    task4_default = task4_oos.loc[task4_oos["parameter"] == "E20/X10/ATR20/S2"].copy()
    task4_param = (
        task4_oos.groupby("parameter", as_index=False)
        .agg(
            stock_count=("ts_code", "nunique"),
            median_return=("cumulative_return", "median"),
            median_sharpe=("sharpe_ratio", "median"),
            median_drawdown=("max_drawdown", "median"),
            positive_share=("cumulative_return", lambda x: float((x > 0).mean())),
            median_trades=("completed_trades", "median"),
            median_exposure=("average_exposure", "median"),
        )
        .sort_values("median_sharpe", ascending=False)
    )

    return {
        "task1": task1,
        "task2_diag": task2_diag,
        "task2_latest": task2_latest,
        "task3": task3,
        "task3_oos": task3_oos,
        "task3_default": task3_default,
        "task3_param": task3_param,
        "task4": task4,
        "task4_oos": task4_oos,
        "task4_default": task4_default,
        "task4_param": task4_param,
        "task5_metrics": task5_metrics,
        "task5_quality": task5_quality,
        "task6_quality": task6_quality,
        "task6_summary": task6_summary,
        "task6_model": task6_model,
        "task6_backtest": task6_backtest,
        "task6_ic": task6_ic,
        "task6_returns": task6_returns,
        "task6_cost": task6_cost,
    }


def configure_matplotlib() -> None:
    global plt, FancyBboxPatch, FancyArrowPatch
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    from matplotlib.patches import FancyArrowPatch as _FancyArrowPatch
    from matplotlib.patches import FancyBboxPatch as _FancyBboxPatch

    plt = _plt
    FancyBboxPatch = _FancyBboxPatch
    FancyArrowPatch = _FancyArrowPatch
    plt.rcParams.update(
        {
            "font.sans-serif": [FONT_CHART, "SimHei", "Arial Unicode MS"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": PALETTE["ink"],
            "axes.labelcolor": PALETTE["ink"],
            "text.color": PALETTE["ink"],
            "xtick.color": PALETTE["gray"],
            "ytick.color": PALETTE["gray"],
            "axes.titleweight": "bold",
            "axes.titlesize": 14,
            "axes.labelsize": 10,
            "xtick.labelsize": 8.5,
            "ytick.labelsize": 8.5,
            "legend.fontsize": 8.5,
        }
    )


def polish_axis(ax, *, grid_axis: str = "y") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis=grid_axis, color="#E4E8EA", linewidth=0.7)
    ax.set_axisbelow(True)


def save_figure(fig, filename: str) -> None:
    fig.savefig(FIGURE_DIR / filename, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def quarter_label_zh(value: str) -> str:
    year, quarter = str(value).split("Q")
    names = {"1": "一季", "2": "二季", "3": "三季", "4": "四季"}
    return f"{year[-2:]}年{names[quarter]}"


def fig_learning_path() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 3.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")
    stages = [
        ("数据基础", "行情获取\n复权与校验"),
        ("指标构造", "动量、趋势\n波动与流动性"),
        ("规则策略", "双均线\n海龟突破"),
        ("机器学习", "模型训练\n样本外评价"),
        ("组合决策", "选股、择时\n风控与监控"),
    ]
    colors = [PALETTE["blue_light"], "#D9E4C6", "#F2D7C6", "#E7D5DE", "#E8E1C3"]
    xs = np.linspace(1, 9, len(stages))
    for i, ((title, detail), x, color) in enumerate(zip(stages, xs, colors)):
        box = FancyBboxPatch(
            (x - 0.75, 1.1),
            1.5,
            1.8,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            linewidth=1.2,
            edgecolor=PALETTE["blue_dark"],
            facecolor=color,
        )
        ax.add_patch(box)
        ax.text(x, 2.32, title, ha="center", va="center", fontsize=12, fontweight="bold")
        ax.text(x, 1.65, detail, ha="center", va="center", fontsize=9.5, linespacing=1.5)
        if i < len(stages) - 1:
            arrow = FancyArrowPatch(
                (x + 0.78, 2.0),
                (xs[i + 1] - 0.78, 2.0),
                arrowstyle="-|>",
                mutation_scale=14,
                linewidth=1.4,
                color=PALETTE["gray"],
            )
            ax.add_patch(arrow)
    ax.set_title("六项任务形成的量化研究闭环", pad=12)
    ax.text(5, 0.45, "每一环节都必须保留时间顺序、基准和风险约束", ha="center", fontsize=10, color=PALETTE["gray"])
    save_figure(fig, "figure_1_learning_path.png")


def fig_task3_return_vs_benchmark(data: dict[str, object]) -> None:
    df = data["task3_default"].sort_values("cumulative_return")
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(8.4, 5.7))
    height = 0.34
    ax.barh(y - height / 2, df["cumulative_return"] * 100, height=height, color=PALETTE["blue"], label="双均线策略")
    ax.barh(y + height / 2, df["benchmark_return"] * 100, height=height, color=PALETTE["light_gray"], edgecolor=PALETTE["gray"], label="买入持有基准")
    ax.axvline(0, color=PALETTE["ink"], linewidth=0.8)
    ax.set_yticks(y, df["stock_name"])
    ax.set_xlabel("样本外累计收益率（%）")
    ax.set_title("5日/15日双均线策略与买入持有基准", pad=34)
    ax.text(0, 1.01, "2024年1月至2026年7月，10只股票；策略仅1只跑赢对应基准", transform=ax.transAxes, fontsize=9, color=PALETTE["gray"])
    ax.legend(loc="lower right", frameon=False)
    polish_axis(ax, grid_axis="x")
    save_figure(fig, "figure_2_ma_returns.png")


def fig_task3_heatmap(data: dict[str, object]) -> None:
    df = data["task3_oos"].copy()
    labels = {"MA5/MA10": "5日/10日", "MA5/MA15": "5日/15日", "MA10/MA20": "10日/20日", "MA10/MA30": "10日/30日", "MA20/MA60": "20日/60日"}
    pivot = df.pivot(index="stock_name", columns="parameter", values="sharpe_ratio")
    order = ["MA5/MA10", "MA5/MA15", "MA10/MA20", "MA10/MA30", "MA20/MA60"]
    pivot = pivot[order]
    values = pivot.to_numpy()
    limit = max(1.5, float(np.nanmax(np.abs(values))))
    fig, ax = plt.subplots(figsize=(8.3, 5.3))
    image = ax.imshow(values, cmap="RdBu_r", vmin=-limit, vmax=limit, aspect="auto")
    ax.set_xticks(np.arange(len(order)), [labels[x] for x in order])
    ax.set_yticks(np.arange(len(pivot.index)), pivot.index)
    ax.set_xlabel("短期/长期均线窗口")
    ax.set_title("双均线参数的样本外夏普比率", pad=34)
    ax.text(0, 1.02, "同一参数在不同股票上的表现差异明显", transform=ax.transAxes, fontsize=9, color=PALETTE["gray"])
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            color = "white" if abs(value) > limit * 0.55 else PALETTE["ink"]
            ax.text(j, i, f"{value:.2f}", ha="center", va="center", fontsize=7.5, color=color)
    cbar = fig.colorbar(image, ax=ax, fraction=0.028, pad=0.02)
    cbar.set_label("夏普比率")
    save_figure(fig, "figure_3_ma_heatmap.png")


def fig_strategy_sharpe_compare(data: dict[str, object]) -> None:
    ma = data["task3_default"].set_index("stock_name")["sharpe_ratio"]
    turtle = data["task4_default"].set_index("stock_name")["sharpe_ratio"]
    frame = pd.concat([ma.rename("双均线"), turtle.rename("海龟策略")], axis=1).dropna()
    frame = frame.sort_values("双均线")
    y = np.arange(len(frame))
    fig, ax = plt.subplots(figsize=(8.4, 5.4))
    for i, (_, row) in enumerate(frame.iterrows()):
        ax.plot([row["双均线"], row["海龟策略"]], [i, i], color=PALETTE["light_gray"], linewidth=2.2, zorder=1)
    ax.scatter(frame["双均线"], y, color=PALETTE["blue"], s=45, label="双均线策略", zorder=3)
    ax.scatter(frame["海龟策略"], y, facecolor="white", edgecolor=PALETTE["orange"], linewidth=1.8, s=55, label="海龟策略", zorder=3)
    ax.axvline(0, color=PALETTE["ink"], linewidth=0.8)
    ax.set_yticks(y, frame.index)
    ax.set_xlabel("样本外夏普比率")
    ax.set_title("相同股票上的规则策略风险调整收益", pad=34)
    ax.text(0, 1.01, "双均线接近全仓切换；海龟策略采用1%风险预算，比较重点是稳定性而非绝对收益", transform=ax.transAxes, fontsize=8.7, color=PALETTE["gray"])
    ax.legend(frameon=False, loc="lower right")
    polish_axis(ax, grid_axis="x")
    save_figure(fig, "figure_4_strategy_sharpe.png")


def fig_task5_metrics(data: dict[str, object]) -> None:
    df = data["task5_metrics"].copy()
    metrics = [("accuracy", "准确率"), ("recall", "召回率"), ("roc_auc", "曲线下面积")]
    x = np.arange(len(df))
    width = 0.23
    colors = [PALETTE["blue"], PALETTE["gold"], PALETTE["pink"]]
    fig, ax = plt.subplots(figsize=(8.0, 4.4))
    for idx, ((column, label), color) in enumerate(zip(metrics, colors)):
        ax.bar(x + (idx - 1) * width, df[column] * 100, width, label=label, color=color, edgecolor="white")
    ax.set_xticks(x, df["model_zh"])
    ax.set_ylim(80, 101)
    ax.set_ylabel("测试集指标（%）")
    ax.set_title("通用分类实验中的模型评价", pad=34)
    ax.text(0, 1.01, "569条医学示例数据、30项特征；仅用于验证机器学习流程", transform=ax.transAxes, fontsize=9, color=PALETTE["gray"])
    ax.legend(frameon=False, ncol=3, loc="lower left")
    polish_axis(ax, grid_axis="y")
    save_figure(fig, "figure_5_ml_classification.png")


def fig_task6_ic(data: dict[str, object]) -> None:
    df = data["task6_ic"].copy()
    model_order = ["ridge", "decision_tree", "random_forest"]
    colors = [PALETTE["blue"], PALETTE["gold"], PALETTE["pink"]]
    markers = ["o", "s", "^"]
    fig, ax = plt.subplots(figsize=(8.3, 4.6))
    for model, color, marker in zip(model_order, colors, markers):
        subset = df.loc[df["model"] == model].sort_values("quarter_index")
        quarter_labels = subset["quarter"].map(quarter_label_zh)
        ax.plot(quarter_labels, subset["rank_ic"], color=color, marker=marker, linewidth=1.8, markersize=4.5, label=subset["model_zh"].iloc[0])
    ax.axhline(0, color=PALETTE["ink"], linewidth=0.8)
    ax.set_ylabel("斯皮尔曼秩相关系数")
    ax.set_title("三种模型的测试期季度排序相关性", pad=34)
    ax.text(0, 1.01, "2024年第二季度至2026年第一季度；正值表示预测排序与未来收益排序方向一致", transform=ax.transAxes, fontsize=8.7, color=PALETTE["gray"])
    ax.legend(frameon=False, ncol=3, loc="lower left")
    polish_axis(ax, grid_axis="y")
    save_figure(fig, "figure_6_ml_rank_ic.png")


def task6_nav_frame(data: dict[str, object]) -> pd.DataFrame:
    returns = data["task6_returns"]
    best = returns.loc[returns["model"] == "decision_tree"].sort_values("quarter_index").copy()
    nav = pd.DataFrame(
        {
            "季度": ["期初"] + best["quarter"].map(quarter_label_zh).tolist(),
            "策略净值": [1.0] + (1 + best["net_return"]).cumprod().tolist(),
            "基准净值": [1.0] + (1 + best["benchmark_return"]).cumprod().tolist(),
        }
    )
    return nav


def fig_task6_nav(data: dict[str, object]) -> None:
    nav = task6_nav_frame(data)
    fig, ax = plt.subplots(figsize=(8.3, 4.6))
    ax.plot(nav["季度"], nav["策略净值"], color=PALETTE["blue"], marker="o", linewidth=2.2, label="决策树前30名组合")
    ax.plot(nav["季度"], nav["基准净值"], color=PALETTE["gray"], marker="s", linewidth=1.8, linestyle="--", label="研究样本等权基准")
    ax.set_ylabel("累计净值")
    ax.set_title("机器学习选股组合与基准的累计净值", pad=34)
    ax.text(0, 1.01, "按季度调仓并扣除单边0.2%综合成本", transform=ax.transAxes, fontsize=9, color=PALETTE["gray"])
    ax.legend(frameon=False, loc="upper left")
    polish_axis(ax, grid_axis="y")
    save_figure(fig, "figure_7_ml_nav.png")


def fig_task6_drawdown(data: dict[str, object]) -> None:
    nav = task6_nav_frame(data)
    for column in ("策略净值", "基准净值"):
        nav[f"{column}回撤"] = nav[column] / nav[column].cummax() - 1
    fig, ax = plt.subplots(figsize=(8.3, 4.4))
    ax.plot(nav["季度"], nav["策略净值回撤"] * 100, color=PALETTE["blue"], linewidth=2.1, label="决策树前30名组合")
    ax.plot(nav["季度"], nav["基准净值回撤"] * 100, color=PALETTE["gray"], linewidth=1.8, linestyle="--", label="研究样本等权基准")
    ax.fill_between(np.arange(len(nav)), nav["策略净值回撤"] * 100, 0, color=PALETTE["blue_light"], alpha=0.35)
    ax.set_xticks(np.arange(len(nav)), nav["季度"])
    ax.set_ylabel("回撤（%）")
    ax.set_title("机器学习选股组合与基准的回撤路径", pad=34)
    ax.text(0, 1.01, "回撤按各自历史净值峰值计算", transform=ax.transAxes, fontsize=9, color=PALETTE["gray"])
    ax.legend(frameon=False, loc="lower left")
    polish_axis(ax, grid_axis="y")
    save_figure(fig, "figure_8_ml_drawdown.png")


def fig_multi_strategy_system() -> None:
    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    ax.axis("off")
    boxes = [
        (1.4, 3.5, "股票池与数据层", "历史可交易股票池\n复权、停牌与成本校验", PALETTE["blue_light"]),
        (5.0, 3.5, "机器学习选股层", "多因子横截面排序\n形成候选股票清单", "#E7D5DE"),
        (8.6, 3.5, "趋势确认层", "均线方向与通道突破\n过滤逆势入场", "#F2D7C6"),
        (3.2, 1.25, "风险与执行层", "波动率定仓、止损\n换手与成交约束", "#D9E4C6"),
        (6.8, 1.25, "组合监控层", "收益、回撤与相关性\n漂移和失效预警", "#E8E1C3"),
    ]
    for x, y, title, detail, color in boxes:
        box = FancyBboxPatch((x - 1.25, y - 0.65), 2.5, 1.3, boxstyle="round,pad=0.04,rounding_size=0.12", linewidth=1.2, edgecolor=PALETTE["blue_dark"], facecolor=color)
        ax.add_patch(box)
        ax.text(x, y + 0.23, title, ha="center", va="center", fontsize=11, fontweight="bold")
        ax.text(x, y - 0.24, detail, ha="center", va="center", fontsize=8.8, linespacing=1.35)
    arrows = [((2.7, 3.5), (3.7, 3.5)), ((6.3, 3.5), (7.3, 3.5)), ((8.6, 2.8), (7.4, 1.75)), ((5.55, 1.25), (4.45, 1.25)), ((3.2, 1.9), (4.1, 2.9)), ((6.8, 1.9), (7.7, 2.9))]
    for start, end in arrows:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=13, linewidth=1.3, color=PALETTE["gray"]))
    ax.set_title("多策略量化交易系统的建议架构", pad=10)
    ax.text(5, 0.22, "该架构是基于前六项任务提出的改进方案，尚需统一口径的组合级回测验证", ha="center", fontsize=9, color=PALETTE["gray"])
    save_figure(fig, "figure_9_multi_strategy.png")


def make_figures(data: dict[str, object]) -> None:
    configure_matplotlib()
    fig_learning_path()
    fig_task3_return_vs_benchmark(data)
    fig_task3_heatmap(data)
    fig_strategy_sharpe_compare(data)
    fig_task5_metrics(data)
    fig_task6_ic(data)
    fig_task6_nav(data)
    fig_task6_drawdown(data)
    fig_multi_strategy_system()


def set_run_font(run, *, size: float = BODY_SIZE, bold: bool | None = None, color: str = INK, font: str = FONT_BODY, italic: bool | None = None) -> None:
    run.font.name = font
    rpr = run._element.get_or_add_rPr()
    rpr.rFonts.set(qn("w:ascii"), font)
    rpr.rFonts.set(qn("w:hAnsi"), font)
    rpr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_paragraph_format(paragraph, *, alignment=WD_ALIGN_PARAGRAPH.JUSTIFY, line_spacing: float = 1.5, keep_with_next: bool = False, first_line_chars: float | None = 2, space_before: float = 0, space_after: float = 0, page_break_before: bool = False) -> None:
    fmt = paragraph.paragraph_format
    fmt.alignment = alignment
    fmt.space_before = Pt(space_before)
    fmt.space_after = Pt(space_after)
    fmt.line_spacing = line_spacing
    fmt.keep_with_next = keep_with_next
    fmt.widow_control = True
    fmt.page_break_before = page_break_before
    if first_line_chars is not None:
        fmt.first_line_indent = Pt(BODY_SIZE * first_line_chars)


def add_body(doc: Document, text: str, *, bold_lead: str | None = None) -> object:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph)
    if bold_lead and text.startswith(bold_lead):
        set_run_font(paragraph.add_run(bold_lead), bold=True)
        set_run_font(paragraph.add_run(text[len(bold_lead) :]))
    else:
        set_run_font(paragraph.add_run(text))
    return paragraph


def add_heading(
    doc: Document,
    text: str,
    level: int = 1,
    *,
    page_break_before: bool = False,
    compact: bool = False,
) -> object:
    paragraph = doc.add_paragraph(style=f"Heading {level}")
    if compact:
        space_before = 3 if level == 1 else 2
        space_after = 2 if level == 1 else 1
    else:
        space_before = 10 if level == 1 else 6
        space_after = 4
    set_paragraph_format(
        paragraph,
        alignment=WD_ALIGN_PARAGRAPH.LEFT,
        keep_with_next=True,
        first_line_chars=None,
        space_before=space_before,
        space_after=space_after,
        page_break_before=page_break_before,
    )
    set_run_font(paragraph.add_run(text), size=15 if level == 1 else 12 if level == 2 else 10.5, bold=True, color=BLUE if level == 1 else INK, font=FONT_HEADING)
    return paragraph


def add_bullet(doc: Document, text: str) -> object:
    paragraph = doc.add_paragraph(style="List Bullet")
    set_paragraph_format(paragraph, first_line_chars=None)
    paragraph.paragraph_format.left_indent = Cm(0.74)
    paragraph.paragraph_format.first_line_indent = Cm(-0.37)
    set_run_font(paragraph.add_run(text))
    return paragraph


def shade_paragraph(paragraph, fill: str) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.append(shd)
    shd.set(qn("w:fill"), fill)


def add_callout(doc: Document, label: str, text: str, *, fill: str = BLUE_LIGHT) -> object:
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.LEFT, first_line_chars=None, space_before=4, space_after=4)
    shade_paragraph(paragraph, fill)
    set_run_font(paragraph.add_run(f"{label}："), bold=True, color=BLUE)
    set_run_font(paragraph.add_run(text))
    return paragraph


def ensure_child(parent, tag: str):
    child = parent.find(qn(tag))
    if child is None:
        child = OxmlElement(tag)
        parent.append(child)
    return child


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 80, start: int = 120, bottom: int = 80, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = ensure_child(tc_pr, "w:tcMar")
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        margin = ensure_child(tc_mar, f"w:{side}")
        margin.set(qn("w:w"), str(value))
        margin.set(qn("w:type"), "dxa")


def set_row_cant_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    tr_pr.append(header)


def set_table_geometry(table, widths_dxa: list[int], *, indent_dxa: int = 120) -> None:
    if sum(widths_dxa) != CONTENT_WIDTH_DXA:
        raise ValueError(f"Table widths must sum to {CONTENT_WIDTH_DXA}, got {sum(widths_dxa)}")
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = ensure_child(tbl_pr, "w:tblW")
    tbl_w.set(qn("w:w"), str(CONTENT_WIDTH_DXA))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = ensure_child(tbl_pr, "w:tblInd")
    tbl_ind.set(qn("w:w"), str(indent_dxa))
    tbl_ind.set(qn("w:type"), "dxa")
    layout = ensure_child(tbl_pr, "w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths_dxa:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        row.height = None
        set_row_cant_split(row)
        for col_index, cell in enumerate(row.cells):
            width = widths_dxa[col_index]
            cell.width = Twips(width)
            tc_pr = cell._tc.get_or_add_tcPr()
            tc_w = ensure_child(tc_pr, "w:tcW")
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)


def add_table_caption(doc: Document, text: str) -> object:
    paragraph = doc.add_paragraph(style="Caption")
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None, space_before=4, space_after=4)
    set_run_font(paragraph.add_run(text), size=9.5, bold=True)
    return paragraph


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths_dxa: list[int], *, alignments: list[object] | None = None, font_size: float = TABLE_SIZE) -> object:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    repeat_table_header(table.rows[0])
    alignments = alignments or [WD_ALIGN_PARAGRAPH.LEFT] + [WD_ALIGN_PARAGRAPH.CENTER] * (len(headers) - 1)
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        set_cell_shading(cell, BLUE_LIGHT)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, line_spacing=1.0, keep_with_next=True)
        set_run_font(paragraph.add_run(header), size=font_size, bold=True)
    for row_index, row_data in enumerate(rows):
        row = table.add_row()
        for index, value in enumerate(row_data):
            cell = row.cells[index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            set_paragraph_format(paragraph, alignment=alignments[index], first_line_chars=None, line_spacing=1.0, keep_with_next=row_index < len(rows) - 1)
            set_run_font(paragraph.add_run(str(value)), size=font_size)
    set_table_geometry(table, widths_dxa)
    spacer = doc.add_paragraph()
    set_paragraph_format(spacer, first_line_chars=None, line_spacing=1.0, space_after=2)
    return table


def add_figure(doc: Document, filename: str, caption: str, interpretation: str, *, width_cm: float = 15.2) -> None:
    image_path = FIGURE_DIR / filename
    paragraph = doc.add_paragraph()
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None, space_before=4)
    inline_shape = paragraph.add_run().add_picture(str(image_path), width=Cm(width_cm))
    inline_shape._inline.docPr.set("descr", caption)
    inline_shape._inline.docPr.set("title", caption)
    caption_paragraph = doc.add_paragraph(style="Caption")
    set_paragraph_format(caption_paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, keep_with_next=True, first_line_chars=None, space_after=2)
    set_run_font(caption_paragraph.add_run(caption), size=9.5, bold=True)
    add_body(doc, interpretation)


def add_page_number(paragraph) -> None:
    set_paragraph_format(paragraph, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, line_spacing=1.0)
    set_run_font(paragraph.add_run("第 "), size=9, color=MUTED)
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])
    set_run_font(run, size=9, color=MUTED)
    set_run_font(paragraph.add_run(" 页"), size=9, color=MUTED)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)
    section.header_distance = Cm(1.25)
    section.footer_distance = Cm(1.25)
    section.different_first_page_header_footer = True

    normal = doc.styles["Normal"]
    normal.font.name = FONT_BODY
    normal._element.rPr.rFonts.set(qn("w:ascii"), FONT_BODY)
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_BODY)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_BODY)
    normal.font.size = Pt(BODY_SIZE)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    heading_tokens = {"Heading 1": (15, BLUE, 10, 4), "Heading 2": (12, INK, 6, 3), "Heading 3": (10.5, BLUE, 4, 2)}
    for style_name, (size, color, before, after) in heading_tokens.items():
        style = doc.styles[style_name]
        style.font.name = FONT_HEADING
        style._element.rPr.rFonts.set(qn("w:ascii"), FONT_HEADING)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_HEADING)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_HEADING)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.5
        style.paragraph_format.keep_with_next = True

    for style_name in ("List Bullet", "List Number"):
        style = doc.styles[style_name]
        style.font.name = FONT_BODY
        style._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_BODY)
        style.font.size = Pt(BODY_SIZE)
        style.paragraph_format.space_before = Pt(0)
        style.paragraph_format.space_after = Pt(0)
        style.paragraph_format.line_spacing = 1.5

    caption = doc.styles["Caption"]
    caption.font.name = FONT_BODY
    caption._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_BODY)
    caption.font.size = Pt(9.5)
    caption.font.color.rgb = RGBColor.from_string(INK)
    caption.paragraph_format.space_before = Pt(0)
    caption.paragraph_format.space_after = Pt(0)

    header = section.header
    hp = header.paragraphs[0]
    set_paragraph_format(hp, alignment=WD_ALIGN_PARAGRAPH.RIGHT, first_line_chars=None, line_spacing=1.0)
    set_run_font(hp.add_run("TASK8 · 量化交易学习成果报告"), size=9, color=MUTED)
    add_page_number(section.footer.paragraphs[0])


def add_cover(doc: Document) -> None:
    for _ in range(4):
        p = doc.add_paragraph()
        set_paragraph_format(p, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, line_spacing=1.0, space_after=12)
    kicker = doc.add_paragraph()
    set_paragraph_format(kicker, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, space_after=16)
    set_run_font(kicker.add_run("北京大学工作坊个人作业 · TASK8 成果展示"), size=11, bold=True, color=GOLD, font=FONT_HEADING)
    title = doc.add_paragraph()
    set_paragraph_format(title, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, space_after=8)
    set_run_font(title.add_run(TITLE), size=24, bold=True, color=BLUE, font=FONT_HEADING)
    subtitle = doc.add_paragraph()
    set_paragraph_format(subtitle, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, space_after=54)
    set_run_font(subtitle.add_run(SUBTITLE), size=15, bold=True, color=INK, font=FONT_HEADING)
    meta = doc.add_paragraph()
    set_paragraph_format(meta, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, line_spacing=1.8)
    set_run_font(meta.add_run(f"作者：{AUTHOR}\n完成日期：{REPORT_DATE}\n研究范围：TASK1-TASK6"), size=11, color=MUTED)
    note = doc.add_paragraph()
    set_paragraph_format(note, alignment=WD_ALIGN_PARAGRAPH.CENTER, first_line_chars=None, space_before=42)
    set_run_font(note.add_run("本报告仅用于课程学习与研究，不构成投资建议。"), size=9.5, italic=True, color=MUTED)
    doc.add_page_break()


def load_toc_pages() -> dict[str, int | str]:
    if TOC_PAGES_PATH.exists():
        return json.loads(TOC_PAGES_PATH.read_text(encoding="utf-8"))
    return {}


def add_static_toc(doc: Document, pages: dict[str, int | str]) -> None:
    add_heading(doc, "目录", 1)
    table = doc.add_table(rows=0, cols=2)
    table.autofit = False
    for level, title in TOC_ENTRIES:
        row = table.add_row()
        set_row_cant_split(row)
        left, right = row.cells
        left.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p_left = left.paragraphs[0]
        set_paragraph_format(p_left, alignment=WD_ALIGN_PARAGRAPH.LEFT, first_line_chars=None, line_spacing=1.2, space_after=1)
        p_left.paragraph_format.left_indent = Cm(0 if level == 1 else 0.65)
        set_run_font(p_left.add_run(title), size=10.0 if level == 1 else 9.5, bold=level == 1)
        p_right = right.paragraphs[0]
        set_paragraph_format(p_right, alignment=WD_ALIGN_PARAGRAPH.RIGHT, first_line_chars=None, line_spacing=1.2, space_after=1)
        page = pages.get(title, "—")
        set_run_font(p_right.add_run(str(page)), size=10.0 if level == 1 else 9.5, bold=level == 1)
    # Quiet two-column TOC without visible grid.
    table.style = "Table Grid"
    set_table_geometry(table, [8150, 875], indent_dxa=0)
    tbl_borders = ensure_child(table._tbl.tblPr, "w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = ensure_child(tbl_borders, f"w:{edge}")
        node.set(qn("w:val"), "nil")
    doc.add_page_break()


def pct(value: float, digits: int = 1, signed: bool = False) -> str:
    sign = "+" if signed else ""
    return f"{value:{sign}.{digits}%}"


def num(value: float, digits: int = 2) -> str:
    return "—" if pd.isna(value) else f"{value:.{digits}f}"


def build_document(data: dict[str, object]) -> Path:
    task1 = data["task1"]
    task2_diag = data["task2_diag"]
    task3_default = data["task3_default"]
    task3_param = data["task3_param"]
    task4_default = data["task4_default"]
    task4_param = data["task4_param"]
    task5_metrics = data["task5_metrics"]
    task5_quality = data["task5_quality"]
    task6_quality = data["task6_quality"]
    task6_summary = data["task6_summary"]
    task6_model = data["task6_model"].set_index("model")
    task6_backtest = data["task6_backtest"].set_index("model")

    doc = Document()
    configure_document(doc)
    doc.core_properties.title = f"{TITLE}：{SUBTITLE}"
    doc.core_properties.subject = "TASK8 成果展示：专业报告撰写与策略路演"
    doc.core_properties.author = AUTHOR
    doc.core_properties.keywords = "量化交易, 双均线, 海龟策略, 机器学习, 多策略系统, 样本外回测"

    add_cover(doc)

    add_heading(doc, "摘要", 1)
    abstract = (
        "本文综合前六项课程任务，围绕数据获取、技术指标、规则策略、机器学习建模与组合回测，构建可复现的量化研究路径。研究比较双均线和海龟策略在十只跨行业股票上的样本外表现，并将通用机器学习流程迁移至中证300样本的季度收益排序。结果显示，5日/15日双均线在六成股票上取得正收益，但仅一只跑赢买入持有；海龟策略可降低回撤，却存在明显的标的和参数敏感性。决策树选股组合累计净收益为30.04%，低于48.42%的样本等权基准，平均排序相关亦为负。报告据此认为，策略复杂度不能替代数据时点、样本外检验、基准比较和风险约束，并提出由机器学习选股、趋势确认、波动率定仓与组合监控组成的多策略框架。"
    )
    add_body(doc, abstract)
    add_callout(doc, "关键词", "量化交易；趋势跟踪；双均线；海龟策略；机器学习选股；样本外回测；风险管理")
    add_static_toc(doc, load_toc_pages())

    add_heading(doc, "1 量化交易核心概念与研究框架", 1)
    add_heading(doc, "1.1 从数据到决策的完整链条", 2)
    add_body(doc, "量化交易是把投资假设转化为可计算、可执行和可检验规则的研究与交易方法。完整过程并不止于生成买卖信号，而是从数据获取和清洗开始，经由特征或指标构造、信号生成、仓位配置、成本建模、回测评价，再进入模拟执行和持续监控。任何一个环节出现时间错位、数据遗漏或口径不一致，都可能让表面优秀的结果失去可信度。")
    add_body(doc, f"TASK1以寒武纪日线为例，保存了未复权与前复权价格，共{len(task1)}个交易日，覆盖2025年7月4日至2026年7月3日。复权处理使跨分红送转时期的收益计算保持连续。TASK2进一步对平安集团和三一重工的本地行情进行缺失值检查和描述性统计，共形成{len(task2_diag)}条字段级统计记录，并计算相对强弱、指数平滑异同移动平均、布林带和平均真实波幅等指标。两项任务共同说明，量化策略首先是一项数据工程工作。")
    add_figure(doc, "figure_1_learning_path.png", "图1 六项任务形成的量化研究闭环", "图1将学习成果重新组织为数据、指标、规则策略、机器学习和组合决策五个阶段。TASK1与TASK2构成数据和特征基础，TASK3与TASK4验证规则策略，TASK5建立机器学习评价流程，TASK6完成金融场景中的模型选股与组合回测。")

    add_heading(doc, "1.2 核心价值、评价原则与研究边界", 2)
    add_body(doc, "量化交易的核心价值主要体现在四个方面：第一，用明确规则减少临场情绪对交易决策的影响；第二，使假设可以在历史样本中重复检验；第三，在多资产和多指标环境中保持一致执行；第四，把收益目标与仓位、回撤和成本约束放在同一框架内。其价值不是保证盈利，而是提高决策的可解释性、纪律性和可审计性。")
    add_body(doc, "评价策略时，本报告遵循“收益、风险、基准、稳定性”四维框架。收益使用累计收益和年化收益描述；风险使用波动率、最大回撤和夏普比率刻画；基准用于回答策略是否比被动持有更有效；稳定性则通过样本外区间、跨股票表现、参数敏感性和交易成本情景进行检查。对于机器学习模型，还必须区分预测指标与投资指标：预测排序正确不必然产生可交易的超额收益。")
    add_callout(doc, "研究边界", "TASK3与TASK4使用相同的十只股票和相近样本区间，但仓位机制不同；TASK6使用不同股票池和季度频率。因此本报告比较的是方法机制与样本外证据，不把三类策略的累计收益直接做横向排名。")

    add_heading(doc, "1.3 六项任务形成的递进式学习路线", 2)
    task_rows = [
        ["TASK1", "行情获取与复权", "理解数据来源、复权和可复现保存"],
        ["TASK2", "技术指标与质量检查", "把价格和成交信息转化为可解释指标"],
        ["TASK3", "双均线趋势策略", "掌握信号延迟、成本和样本外比较"],
        ["TASK4", "海龟突破与风险定仓", "把波动率、止损和风险预算纳入策略"],
        ["TASK5", "通用机器学习分类", "建立预处理、训练、评价与过拟合检查流程"],
        ["TASK6", "机器学习季度选股", "完成金融特征、时间划分、组合回测与成本敏感性"],
    ]
    add_table_caption(doc, "表1 TASK1-TASK6的学习成果与报告角色")
    add_table(doc, ["任务", "主要内容", "形成的能力"], task_rows, [1050, 2600, 5375])
    add_body(doc, "表1体现了从单项工具到完整研究系统的递进关系。前两项任务解决“数据能否使用”，中间两项解决“规则能否执行”，后两项解决“模型能否泛化并转化为组合收益”。这种组织方式也构成后文的直线型行文逻辑。")

    add_heading(doc, "2 量化交易策略综合分析", 1, page_break_before=True)
    add_heading(doc, "2.1 技术指标是信息压缩工具而非独立答案", 2)
    add_body(doc, "TASK2中的相对强弱指标反映上涨与下跌动能的相对强度，指数平滑异同移动平均用于观察趋势动量，布林带描述价格相对均值和波动区间的位置，平均真实波幅则衡量价格波动而不判断方向。这些指标把长序列压缩为易解释的状态变量，但都存在滞后、参数依赖或市场状态敏感性，因此不应把单一阈值机械理解为确定买卖指令。")
    add_body(doc, "从后续任务看，技术指标有三种更合理的使用方式：作为规则策略的组成部分、作为风险管理尺度、作为机器学习特征。双均线将移动平均转化为趋势方向信号；海龟策略用平均真实波幅确定仓位和止损距离；TASK6则将动量、趋势、风险和流动性变量共同输入模型。由此，指标的价值来自其在完整决策链中的功能，而不是指标名称本身。")

    add_heading(doc, "2.2 双均线策略具有趋势捕捉能力但超额收益不足", 2)
    ma_median_return = float(task3_default["cumulative_return"].median())
    ma_median_sharpe = float(task3_default["sharpe_ratio"].median())
    ma_median_drawdown = float(task3_default["max_drawdown"].median())
    ma_positive = float((task3_default["cumulative_return"] > 0).mean())
    ma_beat = float(task3_default["beat_benchmark"].mean())
    add_body(doc, f"TASK3在五个行业、十只股票上实施双均线策略。信号在收盘后生成，下一交易日才应用仓位，并计入单边0.1%的综合交易成本，从而避免把信号当日已经发生的收益错误计入策略。默认5日/15日参数在样本外的累计收益中位数为{ma_median_return:.1%}，夏普比率中位数为{ma_median_sharpe:.2f}，最大回撤中位数为{ma_median_drawdown:.1%}；{ma_positive:.0%}的股票取得正收益，但只有{ma_beat:.0%}跑赢对应的买入持有基准。")
    add_figure(doc, "figure_2_ma_returns.png", "图2 5日/15日双均线策略与买入持有基准", "图2直接展示策略和基准的样本外累计收益。长电科技、宁德时代等标的上的策略收益为正，但多数情况下仍落后于买入持有；贵州茅台和五粮液等标的则出现负收益。该结果说明“避免部分下跌”和“创造稳定超额收益”是两个不同问题。")
    ma_rows = []
    label_map = {"MA5/MA10": "5日/10日", "MA5/MA15": "5日/15日", "MA10/MA20": "10日/20日", "MA10/MA30": "10日/30日", "MA20/MA60": "20日/60日"}
    for _, row in task3_param.iterrows():
        ma_rows.append([label_map[row["parameter"]], pct(row["median_return"]), num(row["median_sharpe"]), pct(row["median_drawdown"]), pct(row["positive_share"], 0), num(row["median_trades"], 1)])
    add_table_caption(doc, "表2 双均线参数的样本外跨股票中位表现")
    add_table(doc, ["均线窗口", "累计收益", "夏普比率", "最大回撤", "正收益占比", "买入次数"], ma_rows, [1500, 1500, 1350, 1500, 1550, 1625])
    add_body(doc, "表2显示，5日/15日参数在当前股票池上的夏普比率中位数最高，但不同参数的排序并不构成未来最优证明。短周期信号更灵敏、交易次数更多，也更容易受到震荡噪声和交易成本影响；长周期信号较平滑，但会延迟进入和退出。")
    add_figure(doc, "figure_3_ma_heatmap.png", "图3 双均线参数的样本外夏普比率", "图3进一步揭示股票与参数之间的交互。同一个均线窗口在半导体、新能源、银行和食品饮料股票上的结果可能方向相反，因此从单只股票挑选历史最优参数容易产生数据挖掘偏差。参数选择应优先关注跨标的和滚动样本外稳定性。")

    add_heading(doc, "2.3 海龟策略以风险预算换取更平稳的损失路径", 2)
    turtle_median_return = float(task4_default["cumulative_return"].median())
    turtle_median_sharpe = float(task4_default["sharpe_ratio"].median())
    turtle_median_drawdown = float(task4_default["max_drawdown"].median())
    turtle_positive = float((task4_default["cumulative_return"] > 0).mean())
    turtle_exposure = float(task4_default["average_exposure"].median())
    add_body(doc, f"TASK4使用20日突破入场、10日通道退出、20日平均真实波幅和2倍波动止损。每笔交易的计划风险控制为账户权益的1%，因而仓位会随波动率上升而下降。默认参数在样本外有{turtle_positive:.0%}的股票取得正收益，累计收益中位数为{turtle_median_return:.1%}，夏普比率中位数为{turtle_median_sharpe:.2f}，最大回撤中位数为{turtle_median_drawdown:.1%}，平均风险敞口中位数仅为{turtle_exposure:.1%}。较低回撤既来自止损，也来自较低资金暴露。")
    turtle_rows = []
    turtle_label = {
        "E10/X5/ATR14/S1.5": "10日入场/5日退出/1.5倍止损",
        "E20/X10/ATR20/S1.5": "20日入场/10日退出/1.5倍止损",
        "E20/X10/ATR20/S2": "20日入场/10日退出/2倍止损",
        "E20/X10/ATR20/S3": "20日入场/10日退出/3倍止损",
        "E40/X20/ATR20/S2": "40日入场/20日退出/2倍止损",
        "E55/X20/ATR20/S2": "55日入场/20日退出/2倍止损",
    }
    for _, row in task4_param.iterrows():
        turtle_rows.append([turtle_label[row["parameter"]], pct(row["median_return"]), num(row["median_sharpe"]), pct(row["median_drawdown"]), pct(row["positive_share"], 0), pct(row["median_exposure"], 1)])
    add_table_caption(doc, "表3 海龟策略参数的样本外跨股票中位表现")
    add_table(doc, ["参数组合", "累计收益", "夏普比率", "最大回撤", "正收益占比", "平均敞口"], turtle_rows, [2875, 1250, 1250, 1250, 1200, 1200], font_size=8.3)
    add_body(doc, "表3中，40日入场、20日退出、2倍波动止损的夏普比率中位数相对较高，但它并非对所有股票占优。更长通道可以过滤部分噪声，却可能错过趋势前段；更窄止损容易被正常波动触发，更宽止损则降低仓位并扩大单笔容忍区间。参数必须与资产波动和组合分散程度共同评价。")

    add_heading(doc, "2.4 不同策略的适用场景、关联性与互补性", 2)
    add_figure(doc, "figure_4_strategy_sharpe.png", "图4 相同股票上的规则策略样本外夏普比率", "图4使用相同股票的样本外夏普比率比较双均线和海龟策略。双均线收益分化更大，海龟策略在多数标的上的数值更接近零。由于两者资金暴露不同，该图主要用于观察稳定性和适用差异，不能视为严格的组合归因实验。")
    strategy_rows = [
        ["双均线", "短长期均线交叉", "持续趋势、交易成本较低", "规则简单、方向清晰", "震荡期反复交易、接近全仓", "中期方向过滤"],
        ["海龟策略", "价格通道突破", "趋势扩张、可跨资产分散", "ATR定仓与止损完整", "低胜率、跳空和成交限制", "入场确认与风险控制"],
        ["机器学习选股", "多因子横截面排序", "股票数量较多、因子关系稳定", "可处理非线性和交互", "过拟合、漂移和弱可解释性", "候选股票筛选"],
    ]
    add_table_caption(doc, "表4 三类策略的优缺点、适用场景与互补角色")
    add_table(doc, ["策略", "信号来源", "适用场景", "主要优点", "主要局限", "系统角色"], strategy_rows, [1250, 1500, 1650, 1550, 1700, 1375], font_size=8.2)
    add_body(doc, "三类方法的互补性来自决策维度不同，而不是简单平均收益。机器学习回答“优先持有哪些股票”，双均线回答“中期方向是否允许持有”，海龟突破和平均真实波幅回答“何时确认入场以及承担多大风险”。但这种互补关系目前只是结构性假设，必须在统一股票池、交易频率和成本口径下重新回测。")

    add_heading(doc, "2.5 多策略量化交易系统的构建思路", 2)
    add_figure(doc, "figure_9_multi_strategy.png", "图5 多策略量化交易系统的建议架构", "图5提出五层系统：先使用历史可交易股票池和点时数据建立研究底座，再用机器学习完成横截面筛选，以均线和突破规则过滤逆势信号，用平均真实波幅确定仓位和止损，最后在组合层监控收益、回撤、换手、相关性和模型漂移。具体实施顺序见附录建议A5。")
    system_rows = [
        ["数据层", "股票池、行情、公司行为、成交状态", "保证每个信号时点只使用当时可得数据"],
        ["选股层", "多因子排序模型", "输出候选股票及预测分数"],
        ["择时层", "均线方向、通道突破", "减少逆势持仓并定义执行时点"],
        ["风险层", "波动率定仓、止损、行业约束", "控制单股和组合损失集中度"],
        ["执行层", "换手、费用、涨跌停和容量", "把理论信号转化为可成交订单"],
        ["监控层", "净值、回撤、相关性、漂移", "识别策略失效并触发降权或复核"],
    ]
    add_table_caption(doc, "表5 多策略系统的模块与职责")
    add_table(doc, ["模块", "核心输入或工具", "主要职责"], system_rows, [1200, 3050, 4775])

    add_heading(doc, "3 机器学习在量化交易中的应用总结", 1, page_break_before=True)
    add_heading(doc, "3.1 从通用分类实验到金融预测问题", 2)
    add_body(doc, f"TASK5使用{task5_quality['samples']}条医学示例数据和{task5_quality['features']}项数值特征，按分层随机方式划分训练集与测试集，比较逻辑回归、决策树和随机森林。该任务的意义在于建立标准机器学习流程，包括缺失检查、标准化、模型训练、混淆矩阵、准确率、召回率和曲线下面积评价。由于数据不是金融数据，实验结果只能证明流程能够正确运行，不能用来支持交易策略有效性。")
    add_figure(doc, "figure_5_ml_classification.png", "图6 通用分类实验中的模型评价", "图6显示逻辑回归和随机森林在该示例数据上的测试集表现较高，单棵决策树相对较弱。这个结果同时提示：模型优劣依赖数据结构和评价目标。进入金融场景后，类别准确率不再是唯一目标，模型还必须接受时间顺序、收益排序和交易成本的检验。")
    task5_rows = []
    for _, row in task5_metrics.iterrows():
        task5_rows.append([row["model_zh"], pct(row["accuracy"]), pct(row["precision"]), pct(row["recall"]), pct(row["f1"]), pct(row["roc_auc"]), pct(row["accuracy_gap_train_minus_test"])])
    add_table_caption(doc, "表6 TASK5通用分类实验的测试集指标")
    add_table(doc, ["模型", "准确率", "精确率", "召回率", "调和平均", "曲线下面积", "训练测试差"], task5_rows, [1350, 1200, 1200, 1200, 1300, 1500, 1275])

    add_heading(doc, "3.2 数据预处理、特征工程与防止信息泄漏", 2)
    add_body(doc, f"TASK6将机器学习流程迁移到股票横截面收益排序。研究从抓取时点的中证300当前成分列表中等距抽取{task6_quality['raw_stock_count']}只股票，取得2015年1月至2026年7月的{task6_quality['raw_daily_rows']:,}条后复权日线，形成{task6_quality['panel_rows']:,}条股票-季度记录和{task6_quality['feature_count']}项动量、趋势、风险及流动性因子。训练期为2016年第一季度至2023年第一季度，验证期为随后四个季度，测试期为2024年第二季度至2026年第一季度。")
    add_body(doc, "防止信息泄漏的关键是让数据可得时间早于信号，信号早于建仓，建仓早于收益标签结束。TASK6在每个季度末形成特征，在下一季度初建仓，并用再下一季度初的价格计算持有期收益；测试期逐季使用扩展窗口重新训练。横截面缩尾、缺失填补和百分位转换也仅使用当期股票，避免把未来分布带回历史。该设计比随机打乱金融样本更符合真实决策过程。")
    add_callout(doc, "数据局限", "TASK6使用当前成分股回溯历史，而不是逐季度历史成分股，存在幸存者与样本选择偏差；历史ST、停牌、涨跌停和冲击成本也未完整模拟。相关改进见附录建议A3与A4。", fill=LIGHT_GRAY)

    add_heading(doc, "3.3 模型选择、训练与评价", 2)
    add_body(doc, "岭回归提供线性和正则化基准，决策树能够学习非线性阈值，随机森林通过多棵树的抽样平均降低单树方差。模型在验证期选择参数，再在测试期逐季度重训。预测层使用平均绝对误差、均方根误差、决定系数和季度排序相关系数；策略层使用累计收益、年化收益、波动率、夏普比率、最大回撤、换手率、跟踪误差和信息比率。")
    add_body(doc, "金融预测通常具有低信噪比。决定系数为负说明模型在点预测层面可能不如简单均值，但排序相关性仍可能对选股有价值；反过来，平均排序相关性略高也不保证前30名组合能跑赢基准，因为组合只使用分布上端，容易受到极端个股、行业集中和换手成本影响。因此模型选择必须同时检查统计指标和经济结果。")
    add_figure(doc, "figure_6_ml_rank_ic.png", "图7 三种模型的测试期季度排序相关性", "图7显示三种模型的季度排序相关性波动明显。决策树的测试期平均值为-0.080，仍是三种模型中相对最高者，且仅一半季度为正。该证据不支持“模型已经形成稳定预测优势”，更合理的解释是模型信号较弱并存在市场状态依赖。")

    add_heading(doc, "3.4 机器学习选股取得正收益但未形成稳定超额", 2)
    model_rows = []
    for model in ("ridge", "decision_tree", "random_forest"):
        pred = task6_model.loc[model]
        bt = task6_backtest.loc[model]
        model_rows.append([pred["model_zh"], num(pred["mean_rank_ic"], 3), pct(pred["positive_ic_ratio"], 0), pct(bt["cumulative_return"]), pct(bt["annualized_return"]), num(bt["sharpe_rf0"]), pct(bt["max_drawdown"]), pct(bt["annualized_excess_return"])])
    add_table_caption(doc, "表7 TASK6模型预测与前30名组合回测结果")
    add_table(doc, ["模型", "平均秩相关", "正相关季度", "累计净收益", "年化收益", "夏普比率", "最大回撤", "年化超额"], model_rows, [1200, 1250, 1250, 1250, 1200, 1100, 1100, 675], font_size=8.0)
    add_body(doc, f"表7显示，决策树前30名组合在单边0.2%综合成本下累计净收益为{task6_summary['best_strategy_cumulative_net_return']:.2%}、年化收益为{task6_summary['best_strategy_annualized_net_return']:.2%}、最大回撤为{task6_summary['best_strategy_max_drawdown']:.2%}。同期研究样本等权基准累计收益为{task6_summary['benchmark_cumulative_return']:.2%}，说明组合虽然获得正绝对收益，却没有形成正超额收益。")
    add_figure(doc, "figure_7_ml_nav.png", "图8 机器学习选股组合与基准的累计净值", "图8给出决策树组合和研究样本等权基准的复利路径。策略在部分季度控制了下跌，但整体净值终点低于基准。仅观察30.04%的正收益容易产生乐观判断，加入基准后才能识别策略的机会成本。")
    add_figure(doc, "figure_8_ml_drawdown.png", "图9 机器学习选股组合与基准的回撤路径", "图9说明策略评价还需要考虑路径风险。决策树组合最大回撤约为8.29%，低于其累计收益规模，但较小回撤不能抵消长期落后基准的问题。组合若要进入实盘模拟，必须同时满足超额收益、回撤和稳定性要求。")

    add_heading(doc, "3.5 机器学习的优势、局限与发展趋势", 2)
    add_body(doc, "机器学习的优势是能够在大量特征中拟合非线性关系和交互作用，并通过统一评分完成横截面排序；它还可以与滚动训练、特征重要性和模型集成结合，适应不断更新的数据。其局限则包括过拟合、标签噪声、数据泄漏、模型漂移、可解释性不足和交易成本放大。金融市场中的数据分布会随制度、参与者和风险偏好变化，模型历史成功并不意味着结构长期稳定。")
    add_body(doc, "未来更值得探索的方向不是继续增加模型复杂度，而是提高证据质量：使用逐季度真实股票池和公告日对齐的财务数据，扩大样本外区间，进行行业和风格中性化，比较滚动与扩展窗口，加入特征稳定性筛选，并用组合级风险预算约束模型输出。模型还应设置漂移阈值和停用规则，使“何时不相信模型”成为系统的一部分。")

    add_heading(doc, "4 结论与展望", 1, page_break_before=True)
    add_heading(doc, "4.1 主要结论", 2)
    add_body(doc, "第一，量化交易的专业性首先体现在研究流程，而非策略名称。复权、时间顺序、基准、成本和风险口径决定了结果是否可信。第二，双均线和海龟策略都能在部分趋势阶段工作，但跨股票差异和参数敏感性显著，单一规则难以适应所有市场。第三，机器学习能够形成系统化选股流程，却没有在当前样本中产生稳定的排序能力和超额收益。第四，多策略系统的价值应来自选股、择时和风险控制的职责分工，并需要组合级样本外验证。")
    add_callout(doc, "核心判断", "策略有效性的最低标准不是“回测赚钱”，而是在真实可得数据、合理成本和样本外检验下，相对明确基准取得与风险相匹配的稳定增量。")

    add_heading(doc, "4.2 学习收获与能力提升", 2)
    add_body(doc, "通过六项任务，我完成了从调用数据接口、处理复权价格和检查数据质量，到计算技术指标、编写交易规则、设计无前视回测、评价策略风险，再到训练机器学习模型和构建季度组合的完整实践。相比只关注模型输出，学习过程中更重要的提升是能够追踪每个数字的来源，识别看似优秀结果背后的口径差异，并主动报告负面证据和研究限制。")
    add_body(doc, "在专业表达方面，本报告将分散任务重新组织为一条因果清晰的研究路线，并通过统一图表说明结果。报告没有回避双均线多数情况下未跑赢持有基准、海龟策略绝对收益有限以及机器学习平均排序相关为负等事实。这种对结果边界的说明，是从完成程序走向完成研究的重要一步。")

    add_heading(doc, "4.3 后续研究计划", 2)
    add_body(doc, "后续工作将按“先修正数据，再统一回测，最后增加复杂度”的顺序推进。第一阶段建立历史可交易股票池和真实成本模型；第二阶段在同一股票池、同一调仓日和同一风险预算下复测双均线、海龟与机器学习组合；第三阶段开展多策略权重和市场状态识别；第四阶段建立模拟交易监控，记录信号、订单、成交、偏差和策略漂移。附录建议A1-A6给出了相应的实施要点。")

    add_heading(doc, "参考文献", 1)
    references = [
        "[1] Breiman, L. (2001). Random Forests. Machine Learning, 45, 5-32.",
        "[2] Fama, E. F., & French, K. R. (1993). Common risk factors in the returns on stocks and bonds. Journal of Financial Economics, 33(1), 3-56.",
        "[3] Gu, S., Kelly, B., & Xiu, D. (2020). Empirical Asset Pricing via Machine Learning. Review of Financial Studies, 33(5), 2223-2273.",
        "[4] TuShare与AkShare公开接口文档；本报告使用的数据抓取日期和实际来源记录见各任务的数据元文件。",
    ]
    for ref in references:
        add_body(doc, ref)

    add_heading(doc, "附录 改进建议", 1, page_break_before=True, compact=True)
    add_heading(doc, "建议A1 统一策略比较口径", 2, compact=True)
    add_body(doc, "对应问题：TASK3采用接近全仓的仓位切换，TASK4采用1%风险预算，TASK6则按季度等权选股，累计收益无法直接比较。改进措施：选定共同股票池、共同样本外区间、共同成本和共同目标波动率，对各策略输出进行波动率缩放后再比较收益、回撤、换手和相关性。预期效果：区分信号质量与资金暴露差异。优先级：高。正文引用：第1.2节、第2.4节。")
    add_heading(doc, "建议A2 建立滚动样本外与参数稳定性检验", 2, compact=True)
    add_body(doc, "对应问题：当前参数比较仍可能受到特定样本区间影响。改进措施：使用滚动训练窗口和固定长度测试窗口，记录每期最优参数、次优参数以及参数邻域表现；只有在多个窗口和多个标的上均不过度失真的参数才进入候选集。预期效果：降低数据挖掘和参数过拟合。优先级：高。正文引用：第2.2节、第2.3节。")
    add_heading(doc, "建议A3 使用点时股票池与公告日数据", 2, compact=True)
    add_body(doc, "对应问题：TASK6使用当前中证300成分股回溯历史，可能遗漏已被剔除或退市股票。改进措施：按每个季度恢复当时的指数成分、上市状态和风险警示状态；财务和估值特征严格按公告日加入，避免使用事后修订数据。预期效果：降低幸存者偏差和信息泄漏。优先级：最高。正文引用：第3.2节。")
    add_heading(doc, "建议A4 完善交易可达性与成本模型", 2, compact=True)
    add_body(doc, "对应问题：现有回测未完整模拟停牌、涨跌停、整手、滑点、印花税变化和市场冲击。改进措施：建立订单级执行规则，以信号后可成交价格为基准，按成交额比例估计冲击成本，并对不同资金规模进行容量情景分析。预期效果：缩小理论收益与模拟实盘收益的差距。优先级：高。正文引用：第3.2节、第3.4节。")
    add_heading(doc, "建议A5 验证机器学习选股与趋势风控的组合", 2, compact=True)
    add_body(doc, "对应问题：本报告提出的多策略架构尚未进行统一实证。改进措施：先由模型选出前30名股票，再分别测试无择时、均线过滤和通道突破三种入场规则；所有方案使用相同的平均真实波幅风险预算和行业上限，并比较净超额、最大回撤、换手和回撤恢复时间。预期效果：验证互补性是否真实存在。优先级：中高。正文引用：第2.5节。")
    add_heading(doc, "建议A6 建立策略监控和停用机制", 2, compact=True)
    add_body(doc, "对应问题：回测不能自动识别上线后的结构变化。改进措施：持续监控滚动排序相关、超额收益、回撤、换手、特征分布和策略间相关性；当指标连续越过预设阈值时，自动降权、停止新增仓位并触发研究复核。预期效果：把模型失效风险转化为可执行流程。优先级：中高。正文引用：第2.5节、第3.5节。")

    path = REPORT_DIR / f"{SUBMISSION_STEM}.docx"
    doc.save(path)
    return path


def write_supporting_files(data: dict[str, object]) -> None:
    chart_map = pd.DataFrame(
        [
            ["图1", "研究框架", "学习任务如何形成完整研究链", "流程图", "五阶段闭环", "六项任务由数据走向组合决策", "figure_1_learning_path.png"],
            ["图2", "双均线", "策略是否跑赢买入持有", "比较", "分组水平条形图", "正收益不等于有效超额", "figure_2_ma_returns.png"],
            ["图3", "双均线", "参数是否跨股票稳定", "矩阵", "带数值热力图", "参数与股票存在明显交互", "figure_3_ma_heatmap.png"],
            ["图4", "规则策略", "两类策略的风险调整收益如何", "比较", "连接点图", "仓位机制影响稳定性", "figure_4_strategy_sharpe.png"],
            ["图6", "通用机器学习", "分类模型在示例数据上的表现", "比较", "分组柱形图", "高指标只证明流程可运行", "figure_5_ml_classification.png"],
            ["图7", "机器学习预测", "季度排序能力是否稳定", "趋势与基准", "多折线", "排序能力弱且时变", "figure_6_ml_rank_ic.png"],
            ["图8", "机器学习回测", "选股组合是否跑赢基准", "趋势", "双折线", "策略正收益但落后基准", "figure_7_ml_nav.png"],
            ["图9", "机器学习风险", "组合回撤路径如何", "趋势", "双折线与填充", "较小回撤不等于有效超额", "figure_8_ml_drawdown.png"],
            ["图5", "多策略系统", "六项任务如何组合为系统", "流程图", "五层架构", "选股、择时、风控与监控分工", "figure_9_multi_strategy.png"],
        ],
        columns=["图号", "章节", "分析问题", "图形家族", "具体形式", "支持结论", "文件"],
    )
    chart_map.to_csv(OUTPUT_DIR / "chart_map.csv", index=False, encoding="utf-8-sig")
    notes = [
        "# TASK8报告来源与设计说明",
        "",
        "- 范围：仅使用TASK1-TASK6，不使用TASK7。",
        "- 导师反馈：用户确认没有可用的导师反馈或评语，因此报告不虚构相关内容。",
        "- 核心证据：TASK3与TASK4样本外参数结果、TASK5模型指标、TASK6模型与组合回测结果。",
        "- 比较边界：规则策略与机器学习策略的股票池、频率和仓位不同，不进行累计收益硬排名。",
        "- 图表设计：统一中文标题与变量名，蓝色为主色，金色/粉色用于模型或对比，灰色用于基准。",
        "- 文档设计：narrative_proposal预设，按作业要求改为A4、宋体五号、1.5倍行距、0磅段间距、两端对齐；封面采用克制的editorial_cover模式。",
        "- 提交文件：李子平TASK8.pdf；同时保留可编辑DOCX。",
    ]
    (OUTPUT_DIR / "report_source_notes.md").write_text("\n".join(notes), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--figures-only", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    data = read_inputs()
    if not args.skip_figures:
        make_figures(data)
    write_supporting_files(data)
    if args.figures_only:
        print(f"Created figures in {FIGURE_DIR}")
        return 0
    path = build_document(data)
    print(f"Created {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
