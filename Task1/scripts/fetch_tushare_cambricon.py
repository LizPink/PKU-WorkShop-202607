from __future__ import annotations

import argparse
import json
import math
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
TUSHARE_URL = "https://api.tushare.pro"
TS_CODE = "688256.SH"
STOCK_LABEL = "寒武纪"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    default_end = date.today()
    default_start = default_end - timedelta(days=365)
    parser = argparse.ArgumentParser(
        description="Fetch Cambricon A-share daily data from TuShare and build a static HTML dashboard."
    )
    parser.add_argument("--start-date", default=default_start.strftime("%Y%m%d"), help="YYYYMMDD")
    parser.add_argument("--end-date", default=default_end.strftime("%Y%m%d"), help="YYYYMMDD")
    parser.add_argument("--token", default=None, help="TuShare token. Prefer TUSHARE_TOKEN or .env instead.")
    return parser.parse_args()


def tushare_call(token: str, api_name: str, params: dict[str, Any], fields: str) -> pd.DataFrame:
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params,
        "fields": fields,
    }
    response = requests.post(TUSHARE_URL, json=payload, timeout=30)
    response.raise_for_status()
    body = response.json()
    if body.get("code") != 0:
        raise RuntimeError(f"TuShare {api_name} failed: {body.get('msg') or body}")
    data = body.get("data") or {}
    columns = data.get("fields") or []
    rows = data.get("items") or []
    return pd.DataFrame(rows, columns=columns)


def normalize_trade_dates(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["trade_date"] = pd.to_datetime(result["trade_date"], format="%Y%m%d")
    result = result.sort_values("trade_date").reset_index(drop=True)
    result["date"] = result["trade_date"].dt.strftime("%Y-%m-%d")
    return result


def numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def fetch_stock_meta(token: str) -> dict[str, Any]:
    meta = tushare_call(
        token,
        "stock_basic",
        {"exchange": "", "list_status": "L"},
        "ts_code,symbol,name,area,industry,market,list_date",
    )
    if meta.empty:
        return {"ts_code": TS_CODE, "name": STOCK_LABEL}
    exact = meta[meta["ts_code"].eq(TS_CODE)]
    if not exact.empty:
        return exact.iloc[0].to_dict()
    fuzzy = meta[meta["name"].astype(str).str.contains("寒武纪", na=False)]
    if not fuzzy.empty:
        return fuzzy.iloc[0].to_dict()
    return {"ts_code": TS_CODE, "name": STOCK_LABEL}


def fetch_daily_data(token: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = tushare_call(
        token,
        "daily",
        {"ts_code": TS_CODE, "start_date": start_date, "end_date": end_date},
        "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount",
    )
    adj = tushare_call(
        token,
        "adj_factor",
        {"ts_code": TS_CODE, "start_date": start_date, "end_date": end_date},
        "ts_code,trade_date,adj_factor",
    )
    if daily.empty:
        raise RuntimeError(f"No daily rows returned for {TS_CODE} from {start_date} to {end_date}.")
    if adj.empty:
        raise RuntimeError(f"No adj_factor rows returned for {TS_CODE} from {start_date} to {end_date}.")
    return normalize_trade_dates(daily), normalize_trade_dates(adj)


def build_adjusted_frames(daily: pd.DataFrame, adj: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_cols = ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    daily = numeric_columns(daily, price_cols)
    adj = numeric_columns(adj, ["adj_factor"])

    merged = daily.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
    missing_factor = merged["adj_factor"].isna().sum()
    if missing_factor:
        raise RuntimeError(f"Missing adjustment factors for {missing_factor} trading rows.")

    latest_factor = float(merged["adj_factor"].iloc[-1])
    qfq = merged[["ts_code", "trade_date", "date", "adj_factor", "vol", "amount"]].copy()
    for column in ["open", "high", "low", "close"]:
        qfq[f"qfq_{column}"] = merged[column] * merged["adj_factor"] / latest_factor

    qfq["qfq_pre_close"] = qfq["qfq_close"].shift(1)
    qfq["qfq_change"] = qfq["qfq_close"] - qfq["qfq_pre_close"]
    qfq["qfq_pct_chg"] = qfq["qfq_change"] / qfq["qfq_pre_close"] * 100

    unadjusted = merged[
        [
            "ts_code",
            "trade_date",
            "date",
            "open",
            "high",
            "low",
            "close",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
            "adj_factor",
        ]
    ].copy()

    combined = unadjusted.merge(
        qfq[
            [
                "trade_date",
                "qfq_open",
                "qfq_high",
                "qfq_low",
                "qfq_close",
                "qfq_pre_close",
                "qfq_change",
                "qfq_pct_chg",
            ]
        ],
        on="trade_date",
        how="left",
    )
    return unadjusted, qfq, combined


def fmt_number(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def fmt_percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):+.2f}%"


def finite_or_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    return value


def rows_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    safe = df.copy()
    safe["trade_date"] = safe["trade_date"].dt.strftime("%Y-%m-%d")
    records = safe.to_dict(orient="records")
    return [{key: finite_or_none(value) for key, value in row.items()} for row in records]


def build_summary(combined: pd.DataFrame, meta: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
    first = combined.iloc[0]
    latest = combined.iloc[-1]
    raw_return = (latest["close"] / first["close"] - 1) * 100
    qfq_return = (latest["qfq_close"] / first["qfq_close"] - 1) * 100
    return {
        "name": meta.get("name") or STOCK_LABEL,
        "ts_code": meta.get("ts_code") or TS_CODE,
        "requested_start": start_date,
        "requested_end": end_date,
        "first_trade_date": first["date"],
        "latest_trade_date": latest["date"],
        "row_count": int(len(combined)),
        "latest_close": float(latest["close"]),
        "latest_qfq_close": float(latest["qfq_close"]),
        "latest_pct_chg": float(latest["pct_chg"]),
        "raw_return": float(raw_return),
        "qfq_return": float(qfq_return),
        "min_close": float(combined["close"].min()),
        "max_close": float(combined["close"].max()),
        "min_qfq_close": float(combined["qfq_close"].min()),
        "max_qfq_close": float(combined["qfq_close"].max()),
        "latest_adj_factor": float(latest["adj_factor"]),
    }


def render_html(combined: pd.DataFrame, summary: dict[str, Any], outputs: dict[str, str], output_path: Path) -> None:
    data_json = json.dumps(rows_for_json(combined), ensure_ascii=False, separators=(",", ":"))
    summary_json = json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
    outputs_json = json.dumps(outputs, ensure_ascii=False, separators=(",", ":"))
    generated_at = date.today().isoformat()

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>寒武纪每日收盘价</title>
  <style>
    :root {{
      --bg: #f7f8f3;
      --panel: #ffffff;
      --ink: #202426;
      --muted: #687076;
      --line: #d8ded7;
      --blue: #2868a8;
      --gold: #b17912;
      --teal: #287c78;
      --rose: #b85b66;
      --soft-blue: #e8f1f8;
      --soft-gold: #f8efd9;
      --shadow: 0 10px 30px rgba(32, 36, 38, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      letter-spacing: 0;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 42px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
      padding: 8px 0 22px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(28px, 4vw, 48px);
      line-height: 1.08;
      font-weight: 760;
    }}
    .subtitle {{
      margin: 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.6;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .link-button {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 38px;
      padding: 0 12px;
      color: var(--ink);
      text-decoration: none;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      font-size: 13px;
      box-shadow: 0 2px 10px rgba(32, 36, 38, 0.04);
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin: 22px 0;
    }}
    .metric {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: var(--shadow);
      min-width: 0;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }}
    .metric strong {{
      display: block;
      font-size: 24px;
      line-height: 1.15;
      font-weight: 720;
      white-space: nowrap;
    }}
    .metric small {{
      display: block;
      color: var(--muted);
      margin-top: 8px;
      line-height: 1.4;
    }}
    section {{
      margin-top: 22px;
    }}
    .section-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 12px;
    }}
    h2 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.25;
    }}
    .segmented {{
      display: inline-grid;
      grid-template-columns: repeat(3, minmax(82px, 1fr));
      gap: 4px;
      padding: 4px;
      background: #eef1ea;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .segmented button {{
      border: 0;
      border-radius: 6px;
      min-height: 32px;
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      white-space: nowrap;
    }}
    .segmented button.active {{
      background: var(--panel);
      color: var(--ink);
      box-shadow: 0 2px 8px rgba(32, 36, 38, 0.08);
    }}
    .chart-panel, .table-panel, .method-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .chart-panel {{
      position: relative;
      min-height: 470px;
      padding: 16px;
    }}
    #priceChart {{
      width: 100%;
      height: 430px;
      display: block;
    }}
    .legend {{
      display: flex;
      gap: 18px;
      align-items: center;
      flex-wrap: wrap;
      color: var(--muted);
      font-size: 13px;
      margin: 0 0 10px;
    }}
    .legend span {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
    }}
    .swatch {{
      width: 26px;
      height: 3px;
      border-radius: 999px;
      display: inline-block;
    }}
    .swatch.raw {{ background: var(--blue); }}
    .swatch.qfq {{ background: var(--gold); }}
    .tooltip {{
      position: absolute;
      pointer-events: none;
      z-index: 5;
      min-width: 190px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
      box-shadow: var(--shadow);
      border-radius: 8px;
      font-size: 12px;
      line-height: 1.55;
      color: var(--ink);
      transform: translate(12px, 12px);
      display: none;
    }}
    .table-wrap {{
      overflow: auto;
      max-height: 520px;
      border-radius: 8px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 900px;
      font-size: 13px;
    }}
    thead th {{
      position: sticky;
      top: 0;
      background: #f4f6f1;
      color: var(--muted);
      text-align: right;
      font-weight: 650;
      border-bottom: 1px solid var(--line);
      padding: 10px 12px;
      white-space: nowrap;
    }}
    thead th:first-child, tbody td:first-child {{ text-align: left; }}
    tbody td {{
      text-align: right;
      padding: 10px 12px;
      border-bottom: 1px solid #edf0eb;
      white-space: nowrap;
    }}
    tbody tr:hover {{ background: #faf8f0; }}
    .method-panel {{
      padding: 18px;
      color: var(--muted);
      line-height: 1.7;
      font-size: 14px;
    }}
    .method-panel strong {{ color: var(--ink); }}
    .footnote {{
      margin: 20px 0 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }}
    @media (max-width: 860px) {{
      main {{ padding: 20px 14px 32px; }}
      header {{
        grid-template-columns: 1fr;
        align-items: start;
      }}
      .actions {{ justify-content: flex-start; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .section-head {{
        flex-direction: column;
        align-items: stretch;
      }}
      .segmented {{ width: 100%; }}
      .chart-panel {{ min-height: 390px; padding: 12px; }}
      #priceChart {{ height: 340px; }}
    }}
    @media (max-width: 520px) {{
      .metric-grid {{ grid-template-columns: 1fr; }}
      .metric strong {{ font-size: 21px; }}
      .actions {{ display: grid; grid-template-columns: 1fr; }}
      .link-button {{ justify-content: center; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>寒武纪每日收盘价</h1>
        <p class="subtitle">股票代码 <strong>{summary["ts_code"]}</strong>；请求区间 {summary["requested_start"]} 至 {summary["requested_end"]}；实际覆盖 {summary["first_trade_date"]} 至 {summary["latest_trade_date"]}，共 {summary["row_count"]} 个交易日。</p>
      </div>
      <nav class="actions" aria-label="下载数据">
        <a class="link-button" href="../{outputs["unadjusted"]}" download>↓ 未复权 CSV</a>
        <a class="link-button" href="../{outputs["qfq"]}" download>↓ 前复权 CSV</a>
        <a class="link-button" href="../{outputs["combined"]}" download>↓ 合并 CSV</a>
      </nav>
    </header>

    <div class="metric-grid" aria-label="关键指标">
      <article class="metric">
        <span>最新未复权收盘价</span>
        <strong>{fmt_number(summary["latest_close"])} 元</strong>
        <small>最新交易日 {summary["latest_trade_date"]}</small>
      </article>
      <article class="metric">
        <span>最新日涨跌幅</span>
        <strong>{fmt_percent(summary["latest_pct_chg"])}</strong>
        <small>TuShare daily 原始口径</small>
      </article>
      <article class="metric">
        <span>区间未复权收益</span>
        <strong>{fmt_percent(summary["raw_return"])}</strong>
        <small>仅反映原始收盘价变化</small>
      </article>
      <article class="metric">
        <span>区间前复权收益</span>
        <strong>{fmt_percent(summary["qfq_return"])}</strong>
        <small>更适合观察连续收益走势</small>
      </article>
    </div>

    <section>
      <div class="section-head">
        <div>
          <h2>收盘价曲线</h2>
          <p class="subtitle">可切换未复权、前复权或双线对比。前复权使最新价格与真实交易价格保持一致。</p>
        </div>
        <div class="segmented" role="group" aria-label="价格口径">
          <button type="button" data-mode="both" class="active">双线</button>
          <button type="button" data-mode="raw">未复权</button>
          <button type="button" data-mode="qfq">前复权</button>
        </div>
      </div>
      <div class="chart-panel">
        <p class="legend">
          <span><i class="swatch raw"></i>未复权 close</span>
          <span><i class="swatch qfq"></i>前复权 qfq_close</span>
        </p>
        <svg id="priceChart" role="img" aria-label="寒武纪每日收盘价曲线"></svg>
        <div id="tooltip" class="tooltip"></div>
      </div>
    </section>

    <section>
      <div class="section-head">
        <div>
          <h2>交易日明细</h2>
          <p class="subtitle">表格按时间倒序展示，价格单位为元；成交量单位为手，成交额单位为千元。</p>
        </div>
      </div>
      <div class="table-panel">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>未复权收盘</th>
                <th>前复权收盘</th>
                <th>涨跌幅</th>
                <th>成交量</th>
                <th>成交额</th>
                <th>复权因子</th>
              </tr>
            </thead>
            <tbody id="dataRows"></tbody>
          </table>
        </div>
      </div>
    </section>

    <section>
      <div class="method-panel">
        <strong>数据与方法：</strong> 数据来自 TuShare `daily` 与 `adj_factor` 接口。未复权数据保留 TuShare 原始日线；前复权价格按 <code>未复权价格 × 当日复权因子 ÷ 区间最新复权因子</code> 计算。本页面为静态 HTML，数据已内嵌，下载链接指向同目录项目中的 CSV 文件。
      </div>
    </section>
    <p class="footnote">Generated on {generated_at}. This dashboard is for data display and does not constitute investment advice.</p>
  </main>
  <script>
    const rows = {data_json};
    const summary = {summary_json};
    const outputs = {outputs_json};
    let mode = "both";

    const fmt = new Intl.NumberFormat("zh-CN", {{ maximumFractionDigits: 2, minimumFractionDigits: 2 }});
    const fmt0 = new Intl.NumberFormat("zh-CN", {{ maximumFractionDigits: 0 }});
    const pct = value => value == null ? "-" : `${{value >= 0 ? "+" : ""}}${{value.toFixed(2)}}%`;

    function renderTable() {{
      const body = document.getElementById("dataRows");
      body.innerHTML = rows.slice().reverse().map(row => `
        <tr>
          <td>${{row.date}}</td>
          <td>${{fmt.format(row.close)}}</td>
          <td>${{fmt.format(row.qfq_close)}}</td>
          <td>${{pct(row.pct_chg)}}</td>
          <td>${{fmt0.format(row.vol)}}</td>
          <td>${{fmt0.format(row.amount)}}</td>
          <td>${{fmt.format(row.adj_factor)}}</td>
        </tr>
      `).join("");
    }}

    function linePath(points, xScale, yScale, key) {{
      return points.map((row, index) => `${{index === 0 ? "M" : "L"}} ${{xScale(index).toFixed(2)}} ${{yScale(row[key]).toFixed(2)}}`).join(" ");
    }}

    function renderChart() {{
      const svg = document.getElementById("priceChart");
      const tooltip = document.getElementById("tooltip");
      const width = Math.max(320, svg.clientWidth);
      const height = Math.max(300, svg.clientHeight);
      svg.setAttribute("viewBox", `0 0 ${{width}} ${{height}}`);
      svg.innerHTML = "";

      const margin = {{ top: 18, right: 30, bottom: 44, left: 58 }};
      const innerW = width - margin.left - margin.right;
      const innerH = height - margin.top - margin.bottom;
      const keys = mode === "raw" ? ["close"] : mode === "qfq" ? ["qfq_close"] : ["close", "qfq_close"];
      const values = rows.flatMap(row => keys.map(key => row[key])).filter(value => Number.isFinite(value));
      const minValue = Math.min(...values);
      const maxValue = Math.max(...values);
      const pad = Math.max((maxValue - minValue) * 0.08, 1);
      const yMin = minValue - pad;
      const yMax = maxValue + pad;
      const xScale = index => margin.left + (rows.length <= 1 ? 0 : (index / (rows.length - 1)) * innerW);
      const yScale = value => margin.top + ((yMax - value) / (yMax - yMin)) * innerH;

      const add = (name, attrs = {{}}, text = null) => {{
        const el = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
        if (text != null) el.textContent = text;
        svg.appendChild(el);
        return el;
      }};

      const gridCount = 5;
      for (let i = 0; i <= gridCount; i++) {{
        const y = margin.top + (i / gridCount) * innerH;
        const value = yMax - (i / gridCount) * (yMax - yMin);
        add("line", {{ x1: margin.left, y1: y, x2: width - margin.right, y2: y, stroke: "#e4e8e1", "stroke-width": "1" }});
        add("text", {{ x: margin.left - 10, y: y + 4, "text-anchor": "end", fill: "#687076", "font-size": "12" }}, fmt.format(value));
      }}

      const tickCount = Math.min(6, rows.length);
      for (let i = 0; i < tickCount; i++) {{
        const index = Math.round((i / Math.max(tickCount - 1, 1)) * (rows.length - 1));
        const x = xScale(index);
        add("line", {{ x1: x, y1: margin.top + innerH, x2: x, y2: margin.top + innerH + 5, stroke: "#9aa39b" }});
        add("text", {{ x, y: margin.top + innerH + 24, "text-anchor": "middle", fill: "#687076", "font-size": "12" }}, rows[index].date.slice(5));
      }}

      add("line", {{ x1: margin.left, y1: margin.top, x2: margin.left, y2: margin.top + innerH, stroke: "#9aa39b" }});
      add("line", {{ x1: margin.left, y1: margin.top + innerH, x2: width - margin.right, y2: margin.top + innerH, stroke: "#9aa39b" }});

      const series = [
        {{ key: "close", color: "#2868a8", label: "未复权" }},
        {{ key: "qfq_close", color: "#b17912", label: "前复权" }}
      ].filter(item => keys.includes(item.key));

      series.forEach(item => {{
        add("path", {{
          d: linePath(rows, xScale, yScale, item.key),
          fill: "none",
          stroke: item.color,
          "stroke-width": "2.4",
          "stroke-linejoin": "round",
          "stroke-linecap": "round"
        }});
        const last = rows[rows.length - 1];
        add("circle", {{ cx: xScale(rows.length - 1), cy: yScale(last[item.key]), r: "4", fill: item.color, stroke: "#fff", "stroke-width": "2" }});
        add("text", {{
          x: Math.min(width - margin.right, xScale(rows.length - 1) + 8),
          y: yScale(last[item.key]) - 8,
          fill: item.color,
          "font-size": "12",
          "font-weight": "700",
          "text-anchor": "end"
        }}, `${{item.label}} ${{fmt.format(last[item.key])}}`);
      }});

      const hoverLine = add("line", {{ x1: 0, y1: margin.top, x2: 0, y2: margin.top + innerH, stroke: "#687076", "stroke-dasharray": "3 4", opacity: "0" }});
      const hit = add("rect", {{ x: margin.left, y: margin.top, width: innerW, height: innerH, fill: "transparent" }});
      hit.addEventListener("mousemove", event => {{
        const point = svg.createSVGPoint();
        point.x = event.clientX;
        point.y = event.clientY;
        const cursor = point.matrixTransform(svg.getScreenCTM().inverse());
        const idx = Math.max(0, Math.min(rows.length - 1, Math.round(((cursor.x - margin.left) / innerW) * (rows.length - 1))));
        const row = rows[idx];
        const x = xScale(idx);
        hoverLine.setAttribute("x1", x);
        hoverLine.setAttribute("x2", x);
        hoverLine.setAttribute("opacity", "1");
        tooltip.style.display = "block";
        tooltip.style.left = `${{Math.min(width - 230, Math.max(8, cursor.x))}}px`;
        tooltip.style.top = `${{Math.max(8, cursor.y)}}px`;
        tooltip.innerHTML = `
          <strong>${{row.date}}</strong><br>
          未复权收盘：${{fmt.format(row.close)}} 元<br>
          前复权收盘：${{fmt.format(row.qfq_close)}} 元<br>
          日涨跌幅：${{pct(row.pct_chg)}}<br>
          成交量：${{fmt0.format(row.vol)}} 手
        `;
      }});
      hit.addEventListener("mouseleave", () => {{
        hoverLine.setAttribute("opacity", "0");
        tooltip.style.display = "none";
      }});
    }}

    document.querySelectorAll(".segmented button").forEach(button => {{
      button.addEventListener("click", () => {{
        mode = button.dataset.mode;
        document.querySelectorAll(".segmented button").forEach(item => item.classList.remove("active"));
        button.classList.add("active");
        renderChart();
      }});
    }});

    renderTable();
    renderChart();
    window.addEventListener("resize", renderChart);
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")


def main() -> None:
    args = parse_args()
    load_env_file(ROOT / ".env")
    token = args.token or os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise SystemExit("Missing TuShare token. Set TUSHARE_TOKEN, create Task1/.env, or pass --token.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

    meta = fetch_stock_meta(token)
    daily, adj = fetch_daily_data(token, args.start_date, args.end_date)
    unadjusted, qfq, combined = build_adjusted_frames(daily, adj)
    summary = build_summary(combined, meta, args.start_date, args.end_date)

    suffix = f"{args.start_date}_{args.end_date}"
    unadjusted_path = DATA_DIR / f"cambricon_688256_SH_daily_unadjusted_{suffix}.csv"
    qfq_path = DATA_DIR / f"cambricon_688256_SH_daily_qfq_{suffix}.csv"
    combined_path = DATA_DIR / f"cambricon_688256_SH_daily_combined_{suffix}.csv"
    html_path = WEB_DIR / "index.html"

    unadjusted.to_csv(unadjusted_path, index=False, encoding="utf-8-sig")
    qfq.to_csv(qfq_path, index=False, encoding="utf-8-sig")
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")

    outputs = {
        "unadjusted": str(unadjusted_path.relative_to(ROOT)).replace("\\", "/"),
        "qfq": str(qfq_path.relative_to(ROOT)).replace("\\", "/"),
        "combined": str(combined_path.relative_to(ROOT)).replace("\\", "/"),
    }
    render_html(combined, summary, outputs, html_path)

    print(json.dumps({"summary": summary, "outputs": outputs, "html": str(html_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

