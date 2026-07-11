from __future__ import annotations

from html import escape
from pathlib import Path
import sys

import pandas as pd

from config import DEFAULT_LONG_WINDOW, DEFAULT_SHORT_WINDOW, UNIVERSE, code_slug


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from workshop_web_theme import render_page


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
OUTPUT_DIR = TASK_DIR / "outputs"
WEB_DIR = TASK_DIR / "web"


def pct(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "—" if pd.isna(value) else f"{value:.3f}"


def styled_table(frame: pd.DataFrame) -> str:
    return frame.to_html(index=False, border=0, classes="data-table", escape=True)


def build_site() -> Path:
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    summary = pd.read_csv(OUTPUT_DIR / "parameter_comparison.csv")
    quality = pd.read_csv(DATA_DIR / "data_quality_summary.csv")
    out_of_sample = summary.loc[summary["sample_period"] == "样本外"].copy()
    parameter_summary = (
        out_of_sample.groupby("parameter", as_index=False)
        .agg(
            收益中位数=("cumulative_return", "median"),
            夏普中位数=("sharpe_ratio", "median"),
            回撤中位数=("max_drawdown", "median"),
            正收益比例=("cumulative_return", lambda values: float((values > 0).mean())),
        )
        .sort_values("夏普中位数", ascending=False)
    )
    best_parameter = parameter_summary.iloc[0]
    default = out_of_sample.loc[
        (out_of_sample["short_window"] == DEFAULT_SHORT_WINDOW)
        & (out_of_sample["long_window"] == DEFAULT_LONG_WINDOW)
    ].sort_values("sharpe_ratio", ascending=False)
    best_stock = default.iloc[0]
    beat_benchmark_count = int((default["excess_return"] > 0).sum())

    parameter_display = parameter_summary.copy()
    for column in ["收益中位数", "回撤中位数", "正收益比例"]:
        parameter_display[column] = parameter_display[column].map(pct)
    parameter_display["夏普中位数"] = parameter_display["夏普中位数"].map(num)

    default_display = default[
        ["stock_name", "industry", "cumulative_return", "sharpe_ratio", "max_drawdown", "benchmark_return", "buy_count"]
    ].rename(
        columns={
            "stock_name": "股票",
            "industry": "行业",
            "cumulative_return": "策略回报",
            "sharpe_ratio": "夏普",
            "max_drawdown": "最大回撤",
            "benchmark_return": "买入持有",
            "buy_count": "买入次数",
        }
    )
    for column in ["策略回报", "最大回撤", "买入持有"]:
        default_display[column] = default_display[column].map(pct)
    default_display["夏普"] = default_display["夏普"].map(num)

    quality_display = quality[
        ["stock_name", "industry", "actual_start", "actual_end", "rows", "duplicate_dates", "missing_required_values", "source", "is_usable"]
    ].rename(
        columns={
            "stock_name": "股票",
            "industry": "行业",
            "actual_start": "起始日期",
            "actual_end": "截止日期",
            "rows": "交易日数",
            "duplicate_dates": "重复日期",
            "missing_required_values": "关键缺失",
            "source": "数据来源",
            "is_usable": "通过检查",
        }
    )

    stock_cards = []
    for spec in UNIVERSE:
        chart = f"../outputs/{code_slug(spec.ts_code)}_MA5_MA15_strategy.png"
        stock_cards.append(
            f"""
            <article class="chart-card">
              <div class="chart-copy"><span class="tag">{escape(spec.industry)}</span><h3>{escape(spec.stock_name)} <small>{escape(spec.ts_code)}</small></h3></div>
              <a href="{chart}" target="_blank" rel="noopener"><img src="{chart}" alt="{escape(spec.stock_name)} 双均线回测图"></a>
            </article>
            """.strip()
        )

    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>股票池</span><strong>10 只</strong></div>
      <div class="metric"><span>行业覆盖</span><strong>5 个</strong></div>
      <div class="metric"><span>样本外夏普最佳参数</span><strong>{escape(str(best_parameter['parameter']))}</strong></div>
      <div class="metric"><span>MA5/15 战胜买入持有</span><strong>{beat_benchmark_count}/10</strong></div>
    </div>
    <section><div class="wrap"><h2>核心概念</h2><div class="grid">
      <article class="card"><h3>金叉</h3><p>短期均线从不高于长期均线变为高于长期均线，表示近期价格趋势转强，产生买入信号。</p></article>
      <article class="card"><h3>死叉</h3><p>短期均线从高于长期均线变为不高于长期均线，表示近期趋势转弱，产生卖出信号。</p></article>
      <article class="card"><h3>趋势跟随</h3><p>均线不预测未来，而是确认已经出现的方向；趋势行情更友好，震荡行情容易反复触发。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>可执行的交易规则</h2><div class="rules">
      <article class="card rule"><h3>什么时候买？</h3><p>MA5 首次上穿 MA15、此前为空仓且两条均线均已形成时记录金叉；信号下一交易期应用。</p></article>
      <article class="card rule sell"><h3>什么时候卖？</h3><p>MA5 从高于 MA15 变为不高于 MA15、此前持仓时记录死叉；下一交易期仓位归零。</p></article>
    </div><p class="note"><strong>回测假设：</strong>初始资金100,000元，只做多、不加杠杆；单边成本0.1%；无风险利率为0；信号错后一日。</p></div></section>
    <section><div class="wrap"><h2>三项核心指标</h2><div class="grid">
      <article class="card"><h3>累计回报</h3><p>期末净值 ÷ 期初净值 − 1，回答策略最终赚了多少。</p></article>
      <article class="card"><h3>最大回撤 MDD</h3><p>净值相对历史最高点的最大跌幅，回答策略最难熬时损失多大。</p></article>
      <article class="card"><h3>夏普比率</h3><p>年化平均收益相对于年化波动的比例，回答风险调整后收益如何。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>跨股票与跨行业结果</h2><div class="figure-grid">
      <article class="figure wide"><a href="../outputs/stock_parameter_sharpe_heatmap.png" target="_blank" rel="noopener"><img src="../outputs/stock_parameter_sharpe_heatmap.png" alt="股票参数夏普热力图"></a></article>
      <article class="figure"><a href="../outputs/industry_parameter_sharpe_heatmap.png" target="_blank" rel="noopener"><img src="../outputs/industry_parameter_sharpe_heatmap.png" alt="行业参数夏普热力图"></a></article>
      <article class="figure"><a href="../outputs/default_parameter_returns.png" target="_blank" rel="noopener"><img src="../outputs/default_parameter_returns.png" alt="默认参数累计回报"></a></article>
    </div></div></section>
    <section><div class="wrap"><h2>参数比较表</h2><div class="table-shell">{styled_table(parameter_display)}</div></div></section>
    <section><div class="wrap"><h2>默认 MA5/MA15 样本外表现</h2><div class="table-shell">{styled_table(default_display)}</div><p class="note"><strong>阅读重点：</strong>正收益不等于择时有效。MA5/MA15 样本外表现最好的股票是 {escape(str(best_stock['stock_name']))}，但只有 {beat_benchmark_count}/10 战胜买入持有。</p></div></section>
    <section><div class="wrap"><h2>逐股回测图</h2><div class="chart-list">{''.join(stock_cards)}</div></div></section>
    <section><div class="wrap"><h2>数据质量</h2><div class="table-shell">{styled_table(quality_display)}</div><p class="note">股票池按当前代表性人工选择，存在幸存者偏差；历史最优参数也可能过拟合。本页用于教学与研究演示，不构成投资建议。</p></div></section>
    """
    html = render_page(
        current_task=3,
        document_title="Task3｜双均线策略与跨行业回测",
        hero_title="策略首秀：双均线<br>捕捉趋势与波动",
        hero_subtitle="用明确的金叉、死叉规则完成跨行业股票回测，并从累计回报、最大回撤和夏普比率评价策略。",
        body_html=body,
        footer_text="数据：TuShare日线校验与前复权本地快照｜回测：Python / pandas｜Task3 可通过 run_all.py 一键复现",
    )
    output = WEB_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_site())
