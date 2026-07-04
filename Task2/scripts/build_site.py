from __future__ import annotations

from html import escape
from pathlib import Path

import pandas as pd

from indicator_guide import INDICATOR_GUIDE


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
        f'<section><h2>{title}</h2><img src="../outputs/{filename}" alt="{title}"></section>'
        for title, filename in overview_charts
    )
    technical_html = "\n".join(
        f'<section><h2>{path.stem.replace("_technical_indicators", "")}</h2><img src="../outputs/{path.name}" alt="{path.stem}"></section>'
        for path in technical_charts
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Task2 技术指标分析</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #182230; background: #f6f7f9; }}
    header {{ background: #fff; border-bottom: 1px solid #d8dee9; padding: 24px 0; }}
    main, .wrap {{ width: min(1120px, calc(100vw - 32px)); margin: 0 auto; }}
    h1 {{ margin: 0; font-size: 30px; }}
    .sub {{ color: #5f6b7a; margin-top: 6px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric, section {{ background: #fff; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; }}
    .label {{ color: #5f6b7a; font-size: 12px; }}
    .value {{ display: block; font-size: 22px; font-weight: 700; margin-top: 6px; }}
    section {{ margin-bottom: 24px; overflow: auto; }}
    img {{ max-width: 100%; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 760px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6ebf2; text-align: right; }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ background: #f1f5f9; }}
    .indicator-table th, .indicator-table td {{ text-align: left; vertical-align: top; line-height: 1.55; }}
    @media (max-width: 820px) {{ .metrics {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>Task2 技术指标分析</h1><div class="sub">先看数据整体画像，再进入 RSI、MACD、布林带与 ATR</div></div></header>
  <main>
    <div class="metrics">
      <div class="metric"><span class="label">股票数量</span><span class="value">{len(latest)}</span></div>
      <div class="metric"><span class="label">最新 RSI 均值</span><span class="value">{latest["rsi_14"].mean():.2f}</span></div>
      <div class="metric"><span class="label">图表数量</span><span class="value">{len(overview_charts) + len(technical_charts)}</span></div>
    </div>
    {overview_html}
    <section><h2>技术指标说明</h2>{indicator_table_html()}</section>
    <section><h2>最新交易日指标</h2>{table_html(latest)}</section>
    {technical_html}
    <section><h2>描述性统计</h2>{table_html(desc)}</section>
  </main>
</body>
</html>
"""
    output = WEB_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


def main() -> None:
    print(build_site())


if __name__ == "__main__":
    main()
