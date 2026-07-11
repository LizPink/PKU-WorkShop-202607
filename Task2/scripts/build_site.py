from __future__ import annotations

from html import escape
from pathlib import Path
import sys

import pandas as pd

from indicator_guide import INDICATOR_GUIDE


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from workshop_web_theme import render_page


TASK_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = TASK_DIR / "outputs"
WEB_DIR = TASK_DIR / "web"


def table_html(df: pd.DataFrame) -> str:
    return df.to_html(index=False, classes="data-table", border=0, float_format=lambda x: f"{x:,.4f}")


def indicator_table_html() -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{escape(item['指标'])}</td>"
        f"<td>{escape(item['名称'])}</td>"
        f"<td>{escape(item['计算方法'])}</td>"
        f"<td>{escape(item['金融应用'])}</td>"
        f"<td>{escape(item['解读提醒'])}</td>"
        "</tr>"
        for item in INDICATOR_GUIDE
    )
    return f"""
<table class="data-table indicator-table">
  <thead><tr><th>指标</th><th>名称</th><th>计算方法</th><th>金融应用</th><th>解读提醒</th></tr></thead>
  <tbody>{rows}</tbody>
</table>
"""


def build_site() -> Path:
    WEB_DIR.mkdir(exist_ok=True)
    latest = pd.read_csv(OUTPUT_DIR / "latest_indicator_snapshot.csv")
    diagnostics = pd.read_csv(OUTPUT_DIR / "diagnostics_summary.csv")
    overview_charts = [
        ("数据描述性统计图：缺失与特征分布", "data_description_overview.png"),
        ("价格与成交量概览", "price_volume_overview.png"),
        ("日收益率分布图", "daily_return_distribution.png"),
    ]
    technical_charts = sorted(OUTPUT_DIR.glob("*_technical_indicators.png"))

    desc = diagnostics[["stock_name", "column", "mean", "std", "min", "max"]].round(4)
    overview_html = "\n".join(
        f'<article class="figure"><h3>{title}</h3><a href="../outputs/{filename}" target="_blank" rel="noopener"><img src="../outputs/{filename}" alt="{title}"></a></article>'
        for title, filename in overview_charts
    )
    technical_html = "\n".join(
        f'<article class="chart-card"><div class="chart-copy"><span class="tag">技术指标</span><h3>{path.stem.replace("_technical_indicators", "")}</h3></div><a href="../outputs/{path.name}" target="_blank" rel="noopener"><img src="../outputs/{path.name}" alt="{path.stem}"></a></article>'
        for path in technical_charts
    )
    latest_date = str(latest["trade_date"].max()) if "trade_date" in latest.columns else "—"
    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>股票数量</span><strong>{len(latest)} 只</strong></div>
      <div class="metric"><span>最新 RSI 均值</span><strong>{latest["rsi_14"].mean():.2f}</strong></div>
      <div class="metric"><span>分析图表</span><strong>{len(overview_charts) + len(technical_charts)} 张</strong></div>
      <div class="metric"><span>最新交易日</span><strong>{escape(latest_date)}</strong></div>
    </div>
    <section><div class="wrap"><h2>从数据画像到交易指标</h2><div class="grid">
      <article class="card"><h3>趋势</h3><p>MACD 与布林带帮助观察方向、动量和价格相对区间。</p></article>
      <article class="card"><h3>超买超卖</h3><p>RSI 将近期涨跌强弱压缩到 0–100，便于识别极端状态。</p></article>
      <article class="card"><h3>波动风险</h3><p>ATR 使用真实波幅衡量正常波动，为止损和风险定仓提供尺度。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>数据整体画像</h2><p class="section-lede">先确认缺失、分布、价格、成交量和日收益率，再解读技术指标。</p><div class="figure-grid">{overview_html}</div></div></section>
    <section><div class="wrap"><h2>技术指标说明</h2><div class="table-shell">{indicator_table_html()}</div></div></section>
    <section><div class="wrap"><h2>最新交易日指标</h2><div class="table-shell">{table_html(latest)}</div></div></section>
    <section><div class="wrap"><h2>逐股技术指标图</h2><div class="chart-list">{technical_html}</div></div></section>
    <section><div class="wrap"><h2>描述性统计</h2><div class="table-shell">{table_html(desc)}</div>
      <p class="note"><strong>解读提醒：</strong>任何单一指标都不能独立构成交易结论，应结合趋势、波动、价格位置和数据质量共同判断。</p>
    </div></section>
    """
    html = render_page(
        current_task=2,
        document_title="Task2｜数据诊断与技术指标",
        hero_title="指标进阶：从数据诊断<br>到趋势与波动",
        hero_subtitle="先检查数据质量和分布，再构建 RSI、MACD、布林带与 ATR，为策略研究建立可靠指标层。",
        body_html=body,
        footer_text="数据：本地行情快照｜指标：RSI / MACD / Bollinger Bands / ATR｜Task2 可通过 run_all.py 一键复现",
    )
    output = WEB_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


def main() -> None:
    print(build_site())


if __name__ == "__main__":
    main()
