from __future__ import annotations

import argparse
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from workshop_web_theme import render_page


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
    recent = recent.rename(
        columns={
            "date": "日期",
            "close": "未复权收盘价",
            "qfq_close": "前复权收盘价",
            "pct_chg": "涨跌幅（%）",
            "vol": "成交量",
            "amount": "成交额",
        }
    )
    table_html = recent.to_html(index=False, classes="data-table", border=0, float_format=lambda x: f"{x:,.2f}")
    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>交易日数量</span><strong>{summary["rows"]}</strong></div>
      <div class="metric"><span>数据区间</span><strong>{summary["start"]}<br><small>至 {summary["end"]}</small></strong></div>
      <div class="metric"><span>最新收盘价</span><strong>{summary["latest_close"]:.2f} 元</strong></div>
      <div class="metric"><span>区间前复权收益</span><strong>{summary["qfq_return"]:.2%}</strong></div>
    </div>
    <section><div class="wrap"><h2>数据引擎的三个关键点</h2><div class="grid">
      <article class="card"><h3>行情获取</h3><p>从数据接口获取寒武纪日线行情，并保存可追溯的本地 CSV 快照。</p></article>
      <article class="card"><h3>前复权处理</h3><p>使用复权因子消除除权除息造成的机械跳空，更适合比较连续收益路径。</p></article>
      <article class="card"><h3>标准化输出</h3><p>统一日期、OHLC、成交量和成交额字段，为后续指标与策略回测提供输入。</p></article>
    </div></div></section>
    <section><div class="wrap"><h2>价格走势</h2><p class="section-lede">未复权价格保留历史真实报价，前复权价格保持收益序列连续。点击图表可查看原图。</p>
      <article class="figure"><a href="{chart_name}" target="_blank" rel="noopener"><img src="{chart_name}" alt="寒武纪未复权与前复权收盘价走势"></a></article>
    </div></section>
    <section><div class="wrap"><h2>最近 12 个交易日</h2><div class="table-shell">{table_html}</div>
      <p class="note blue"><strong>阅读提示：</strong>前复权序列用于连续收益分析；研究实际成交价格时仍应保留未复权行情。</p>
    </div></section>
    """
    html = render_page(
        current_task=1,
        document_title="Task1｜量化交易数据引擎",
        hero_title="数据启航：寒武纪<br>行情获取与复权处理",
        hero_subtitle="从行情接口到本地数据快照，完成日期、价格、成交量与前复权序列的标准化整理。",
        body_html=body,
        footer_text="数据：寒武纪 A 股日线本地快照｜处理：Python / pandas｜Task1 可通过 run_all.py 一键复现",
    )
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
