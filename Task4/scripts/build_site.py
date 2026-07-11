from __future__ import annotations

from html import escape
from pathlib import Path
import sys

import pandas as pd

from config import DEFAULT_PARAMS, UNIVERSE, code_slug, parameter_label, parameter_slug


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from workshop_web_theme import render_page


TASK_DIR = Path(__file__).resolve().parents[1]
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
    default_label = parameter_label(DEFAULT_PARAMS)
    out_of_sample = summary.loc[summary["sample_period"] == "out_of_sample"].copy()
    default = out_of_sample.loc[out_of_sample["parameter"] == default_label].sort_values("sharpe_ratio", ascending=False)
    parameter_summary = (
        out_of_sample.groupby("parameter", as_index=False)
        .agg(
            收益中位数=("cumulative_return", "median"),
            夏普中位数=("sharpe_ratio", "median"),
            回撤中位数=("max_drawdown", "median"),
            正收益比例=("cumulative_return", lambda values: float((values > 0).mean())),
            完成交易中位数=("completed_trades", "median"),
        )
        .sort_values("夏普中位数", ascending=False)
    )
    best_parameter = parameter_summary.iloc[0]
    best_stock = default.iloc[0]
    positive_count = int((default["cumulative_return"] > 0).sum())

    parameter_display = parameter_summary.copy()
    for column in ["收益中位数", "回撤中位数", "正收益比例"]:
        parameter_display[column] = parameter_display[column].map(pct)
    parameter_display["夏普中位数"] = parameter_display["夏普中位数"].map(num)
    parameter_display["完成交易中位数"] = parameter_display["完成交易中位数"].map(lambda value: f"{value:.1f}")

    default_display = default[
        [
            "stock_name",
            "industry",
            "cumulative_return",
            "benchmark_return",
            "max_drawdown",
            "sharpe_ratio",
            "completed_trades",
            "win_rate",
            "average_exposure",
        ]
    ].rename(
        columns={
            "stock_name": "股票",
            "industry": "行业",
            "cumulative_return": "策略回报",
            "benchmark_return": "买入持有",
            "max_drawdown": "最大回撤",
            "sharpe_ratio": "夏普",
            "completed_trades": "完成交易",
            "win_rate": "胜率",
            "average_exposure": "平均资金暴露",
        }
    )
    for column in ["策略回报", "买入持有", "最大回撤", "胜率", "平均资金暴露"]:
        default_display[column] = default_display[column].map(pct)
    default_display["夏普"] = default_display["夏普"].map(num)

    stock_cards = []
    slug = parameter_slug(DEFAULT_PARAMS)
    for spec in UNIVERSE:
        chart = f"../outputs/{code_slug(spec.ts_code)}_{slug}_strategy.png"
        stock_cards.append(
            f"""
            <article class="chart-card">
              <div class="chart-copy"><span class="tag">{escape(spec.industry)}</span><h3>{escape(spec.stock_name)} <small>{escape(spec.ts_code)}</small></h3></div>
              <a href="{chart}" target="_blank" rel="noopener"><img src="{chart}" alt="{escape(spec.stock_name)} 海龟策略回测图"></a>
            </article>
            """.strip()
        )

    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>股票池</span><strong>{len(UNIVERSE)} 只</strong></div>
      <div class="metric"><span>行业覆盖</span><strong>{len({spec.industry for spec in UNIVERSE})} 个</strong></div>
      <div class="metric"><span>默认参数样本外正收益</span><strong>{positive_count}/10</strong></div>
      <div class="metric"><span>样本外夏普最佳参数</span><strong>{escape(str(best_parameter['parameter']))}</strong></div>
    </div>
    <section><div class="wrap"><h2>海龟策略的三个核心组件</h2><div class="grid">
      <article class="card"><h3>高低点通道</h3><p>突破前20日最高通道入场，跌破前10日最低通道退出，用价格行为确认趋势。</p></article>
      <article class="card"><h3>Wilder ATR</h3><p>真实波幅同时考虑日内波动和跳空，为止损距离和仓位规模提供统一风险尺度。</p></article>
      <article class="card"><h3>风险定仓</h3><p>每笔计划风险为账户权益的1%，高波动股票自动减少股数，避免固定满仓。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>可执行的交易规则</h2><div class="rules">
      <article class="card rule"><h3>什么时候买？</h3><p>收盘价首次突破截至前一日的20日最高通道；下一交易日开盘按ATR风险预算买入。</p></article>
      <article class="card rule sell"><h3>什么时候卖？</h3><p>收盘价跌破10日最低通道，或持仓日触及入场价下方2ATR止损线；跳空时按开盘价处理。</p></article>
    </div><p class="note"><strong>回测假设：</strong>只做多、不加杠杆、不加仓；允许教学用小数股；单边成本0.1%；普通通道信号次日执行。</p></div></section>
    <section><div class="wrap"><h2>三项核心指标</h2><div class="grid">
      <article class="card"><h3>累计回报</h3><p>日策略收益复利后的期末总回报，展示最终收益规模。</p></article>
      <article class="card"><h3>最大回撤 MDD</h3><p>净值相对历史最高点的最大跌幅，衡量策略最难承受的损失阶段。</p></article>
      <article class="card"><h3>夏普比率</h3><p>日均收益相对波动率的比例并按252日年化，衡量风险调整后表现。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>跨股票、参数与行业结果</h2><div class="figure-grid">
      <article class="figure wide"><a href="../outputs/stock_parameter_sharpe_heatmap.png" target="_blank" rel="noopener"><img src="../outputs/stock_parameter_sharpe_heatmap.png" alt="股票参数样本外夏普热力图"></a></article>
      <article class="figure"><a href="../outputs/industry_parameter_sharpe_heatmap.png" target="_blank" rel="noopener"><img src="../outputs/industry_parameter_sharpe_heatmap.png" alt="行业参数样本外夏普热力图"></a></article>
      <article class="figure"><a href="../outputs/default_parameter_returns.png" target="_blank" rel="noopener"><img src="../outputs/default_parameter_returns.png" alt="默认参数样本外累计回报"></a></article>
      <article class="figure wide"><a href="../outputs/risk_return_scatter.png" target="_blank" rel="noopener"><img src="../outputs/risk_return_scatter.png" alt="默认参数样本外风险收益分布"></a></article>
    </div></div></section>
    <section><div class="wrap"><h2>参数比较表</h2><div class="table-shell">{styled_table(parameter_display)}</div>
      <p class="note blue"><strong>参数结论：</strong>{escape(str(best_parameter['parameter']))} 的跨股票中位夏普最高，但与其他组合差距有限，不应据此认定未来最优。</p>
    </div></section>
    <section><div class="wrap"><h2>默认 {escape(default_label)} 样本外表现</h2><div class="table-shell">{styled_table(default_display)}</div>
      <p class="note"><strong>阅读重点：</strong>{escape(str(best_stock['stock_name']))} 的默认参数样本外夏普最高；股票间结果分化说明海龟策略更适合多标的分散，而不是单股确定性预测。</p>
    </div></section>
    <section><div class="wrap"><h2>逐股回测图</h2><div class="chart-list">{''.join(stock_cards)}</div></div></section>
    <section><div class="wrap"><h2>适应场景与限制</h2><div class="grid two">
      <article class="card"><h3>更适合</h3><p>趋势持续、流动性较好、可以跨股票分散，并能严格执行风险预算和止损的场景。</p></article>
      <article class="card"><h3>需要谨慎</h3><p>窄幅震荡、频繁跳空、涨跌停或成交受限的个股；股票池也存在幸存者偏差。</p></article>
    </div><p class="note">本页使用前复权日线、固定成本和小数股教学假设，结果用于策略研究演示，不构成投资建议。</p></div></section>
    """
    html = render_page(
        current_task=4,
        document_title="Task4｜海龟交易策略回测",
        hero_title="复刻传奇：海龟法则<br>突破、波动与风险控制",
        hero_subtitle="用高低点通道识别趋势，以Wilder ATR确定止损和仓位，并通过样本外回测观察参数与股票差异。",
        body_html=body,
        footer_text="数据：10只A股前复权日线本地快照｜策略：Turtle Channel / Wilder ATR｜Task4 可通过 run_all.py 一键复现",
    )
    output = WEB_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_site())
