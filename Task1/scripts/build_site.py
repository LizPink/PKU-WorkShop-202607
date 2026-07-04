from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
WEB_DIR = TASK_DIR / "web"
STOCK_NAME = "寒武纪"


def latest_combined_csv() -> Path:
    files = sorted(DATA_DIR.glob("cambricon_688256_SH_daily_combined_*.csv"))
    if not files:
        raise FileNotFoundError("No combined CSV found. Run fetch_data.py first.")
    return files[-1]


def load_combined(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["trade_date"])
    return df.sort_values("trade_date").reset_index(drop=True)


def summarize(df: pd.DataFrame) -> dict[str, object]:
    first, latest = df.iloc[0], df.iloc[-1]
    return {
        "rows": len(df),
        "start": first["date"],
        "end": latest["date"],
        "latest_close": latest["close"],
        "latest_qfq_close": latest["qfq_close"],
        "raw_return": latest["close"] / first["close"] - 1,
        "qfq_return": latest["qfq_close"] / first["qfq_close"] - 1,
    }


def plot_price(df: pd.DataFrame, output: Path) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(df["trade_date"], df["close"], label="未复权收盘价", linewidth=2)
    ax.plot(df["trade_date"], df["qfq_close"], label="前复权收盘价", linewidth=2)
    ax.set_title(f"{STOCK_NAME}收盘价走势")
    ax.set_xlabel("日期")
    ax.set_ylabel("价格")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def write_html(df: pd.DataFrame, summary: dict[str, object], chart_name: str, output: Path) -> None:
    recent = df[["date", "close", "qfq_close", "pct_chg", "vol", "amount"]].tail(12)
    table_html = recent.to_html(index=False, classes="data-table", border=0, float_format=lambda x: f"{x:,.2f}")
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Task1 寒武纪行情展示</title>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #182230; background: #f6f7f9; }}
    header {{ background: #fff; border-bottom: 1px solid #d8dee9; padding: 24px 0; }}
    main, .wrap {{ width: min(1100px, calc(100vw - 32px)); margin: 0 auto; }}
    h1 {{ margin: 0; font-size: 30px; }}
    .sub {{ color: #5f6b7a; margin-top: 6px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }}
    .metric, section {{ background: #fff; border: 1px solid #d8dee9; border-radius: 8px; padding: 16px; }}
    .label {{ color: #5f6b7a; font-size: 12px; }}
    .value {{ display: block; font-size: 22px; font-weight: 700; margin-top: 6px; }}
    section {{ margin-bottom: 24px; overflow: auto; }}
    img {{ max-width: 100%; display: block; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; min-width: 720px; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #e6ebf2; text-align: right; }}
    th:first-child, td:first-child {{ text-align: left; }}
    th {{ background: #f1f5f9; }}
    @media (max-width: 820px) {{ .metrics {{ grid-template-columns: 1fr 1fr; }} }}
  </style>
</head>
<body>
  <header><div class="wrap"><h1>Task1 寒武纪 A 股行情展示</h1><div class="sub">未复权与前复权收盘价对比</div></div></header>
  <main>
    <div class="metrics">
      <div class="metric"><span class="label">交易日数量</span><span class="value">{summary["rows"]}</span></div>
      <div class="metric"><span class="label">数据区间</span><span class="value">{summary["start"]} 至 {summary["end"]}</span></div>
      <div class="metric"><span class="label">最新收盘价</span><span class="value">{summary["latest_close"]:.2f}</span></div>
      <div class="metric"><span class="label">区间前复权收益</span><span class="value">{summary["qfq_return"]:.2%}</span></div>
    </div>
    <section><h2>价格走势</h2><img src="{chart_name}" alt="寒武纪收盘价走势"></section>
    <section><h2>最近 12 个交易日</h2>{table_html}</section>
  </main>
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")


def build_site(input_csv: Path | None = None) -> Path:
    WEB_DIR.mkdir(exist_ok=True)
    csv_path = input_csv or latest_combined_csv()
    df = load_combined(csv_path)
    chart_path = WEB_DIR / "cambricon_price.png"
    plot_price(df, chart_path)
    write_html(df, summarize(df), chart_path.name, WEB_DIR / "index.html")
    return WEB_DIR / "index.html"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Task1 static website from the combined CSV.")
    parser.add_argument("--input-csv", type=Path, default=None)
    args = parser.parse_args()
    print(build_site(args.input_csv))


if __name__ == "__main__":
    main()
