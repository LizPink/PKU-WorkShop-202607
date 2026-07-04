from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
OUTPUT_DIR = TASK_DIR / "outputs"
NUMERIC_COLS = ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
PLOT_COLORS = ["#2563eb", "#f97316", "#0f766e", "#7c3aed"]


def stock_name(path: Path) -> str:
    return path.stem.replace("行情数据", "")


def slug(ts_code: str) -> str:
    return ts_code.replace(".", "_")


def load_prices(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    return df.sort_values("trade_date").reset_index(drop=True)


def wilder_average(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    change = close.diff()
    gain = change.clip(lower=0)
    loss = -change.clip(upper=0)
    rs = wilder_average(gain, period) / wilder_average(loss, period)
    return 100 - 100 / (1 + rs)


def macd(close: pd.Series) -> pd.DataFrame:
    fast = close.ewm(span=12, adjust=False).mean()
    slow = close.ewm(span=26, adjust=False).mean()
    line = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    return pd.DataFrame({"macd": line, "macd_signal": signal, "macd_hist": line - signal})


def bollinger(close: pd.Series, period: int = 20, k: float = 2) -> pd.DataFrame:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    return pd.DataFrame(
        {
            "bb_middle_20": middle,
            "bb_upper_20": middle + k * std,
            "bb_lower_20": middle - k * std,
        }
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift()
    true_range = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return wilder_average(true_range, period)


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.concat([df, pd.DataFrame({"rsi_14": rsi(df["close"])}), macd(df["close"]), bollinger(df["close"])], axis=1)
    out["atr_14"] = atr(out)
    out["atr_pct"] = out["atr_14"] / out["close"] * 100
    return out


def diagnostics(name: str, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = df.isna().sum().rename("missing_count").reset_index().rename(columns={"index": "column"})
    missing.insert(0, "stock_name", name)
    desc = df[NUMERIC_COLS].describe().T.reset_index().rename(columns={"index": "column"})
    desc.insert(0, "stock_name", name)
    return missing, desc


def setup_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def markdown_table(df: pd.DataFrame) -> str:
    text = df.copy()
    for col in text.columns:
        if pd.api.types.is_float_dtype(text[col]):
            text[col] = text[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    rows = [["| " + " | ".join(map(str, text.columns)) + " |"]]
    rows.append(["| " + " | ".join(["---"] * len(text.columns)) + " |"])
    for _, row in text.iterrows():
        rows.append(["| " + " | ".join(map(str, row.tolist())) + " |"])
    return "\n".join(item[0] for item in rows)


def plot_data_description(frames: list[dict[str, object]], missing: pd.DataFrame, output: Path) -> None:
    setup_plot_style()
    names = [item["name"] for item in frames]
    data = [item["data"] for item in frames]
    missing_totals = missing.groupby("stock_name")["missing_count"].sum().reindex(names).fillna(0)

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    axes = axes.ravel()
    bars = axes[0].bar(names, missing_totals, color=PLOT_COLORS[: len(names)], edgecolor="#334155", linewidth=0.8)
    axes[0].set_title("缺失值总数")
    axes[0].set_ylabel("缺失数量")
    axes[0].set_ylim(0, max(1, float(missing_totals.max()) + 1))
    for bar, value in zip(bars, missing_totals):
        axes[0].text(bar.get_x() + bar.get_width() / 2, max(0.04, float(value) + 0.04), f"{int(value)}", ha="center")

    axes[1].boxplot([df["close"].dropna() for df in data], tick_labels=names)
    axes[1].set_title("收盘价分布")
    axes[1].set_ylabel("价格")

    axes[2].boxplot([df["vol"].dropna() / 10000 for df in data], tick_labels=names)
    axes[2].set_title("成交量分布")
    axes[2].set_ylabel("成交量 / 10,000")

    axes[3].boxplot([df["amount"].dropna() / 10000 for df in data], tick_labels=names)
    axes[3].set_title("成交额分布")
    axes[3].set_ylabel("成交额 / 10,000")

    for ax in axes:
        ax.grid(True, axis="y", alpha=0.25)
    fig.suptitle("数据描述性统计图：缺失与主要特征分布", fontsize=15)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_price_volume(frames: list[dict[str, object]], output: Path) -> None:
    setup_plot_style()
    fig, axes = plt.subplots(len(frames), 2, figsize=(13, 3.8 * len(frames)), squeeze=False)
    for row, item in enumerate(frames):
        name = item["name"]
        df = item["data"]
        color = PLOT_COLORS[row % len(PLOT_COLORS)]

        axes[row, 0].plot(df["trade_date"], df["close"], color=color, linewidth=1.8)
        axes[row, 0].set_title(f"{name} 收盘价走势")
        axes[row, 0].set_ylabel("收盘价")

        axes[row, 1].bar(df["trade_date"], df["vol"], color=color, alpha=0.65)
        axes[row, 1].set_title(f"{name} 成交量")
        axes[row, 1].set_ylabel("成交量")

        for ax in axes[row]:
            ax.grid(True, alpha=0.25)

    fig.suptitle("价格与成交量概览", fontsize=15)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_return_distribution(frames: list[dict[str, object]], output: Path) -> None:
    setup_plot_style()
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    returns = []
    names = []
    for idx, item in enumerate(frames):
        name = item["name"]
        pct = item["data"]["pct_chg"].dropna()
        returns.append(pct)
        names.append(name)
        axes[0].hist(pct, bins=28, alpha=0.48, label=name, color=PLOT_COLORS[idx % len(PLOT_COLORS)])

    axes[0].axvline(0, color="#64748b", linewidth=1)
    axes[0].set_title("日收益率直方图")
    axes[0].set_xlabel("日收益率(%)")
    axes[0].set_ylabel("交易日数量")
    axes[0].legend()

    axes[1].boxplot(returns, tick_labels=names)
    axes[1].axhline(0, color="#64748b", linewidth=1)
    axes[1].set_title("日收益率箱线图")
    axes[1].set_ylabel("日收益率(%)")

    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.suptitle("日收益率分布图", fontsize=15)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def plot_indicators(df: pd.DataFrame, name: str, output: Path) -> None:
    setup_plot_style()
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True, gridspec_kw={"height_ratios": [2.2, 1, 1, 1]})

    axes[0].plot(df["trade_date"], df["close"], label="收盘价", linewidth=1.8)
    axes[0].plot(df["trade_date"], df["bb_middle_20"], label="布林带中轨", linewidth=1.2)
    axes[0].fill_between(df["trade_date"], df["bb_lower_20"], df["bb_upper_20"], alpha=0.18, label="布林带区间")
    axes[0].set_title(f"{name} 技术指标")
    axes[0].legend(loc="upper left")

    axes[1].plot(df["trade_date"], df["rsi_14"], color="#7c3aed")
    axes[1].axhline(70, color="#f59e0b", linestyle="--", linewidth=1)
    axes[1].axhline(30, color="#f59e0b", linestyle="--", linewidth=1)
    axes[1].set_ylabel("RSI")

    axes[2].plot(df["trade_date"], df["macd"], label="MACD", color="#0f766e")
    axes[2].plot(df["trade_date"], df["macd_signal"], label="Signal", color="#ea580c")
    axes[2].bar(df["trade_date"], df["macd_hist"], color="#94a3b8", alpha=0.5)
    axes[2].legend(loc="upper left")

    axes[3].plot(df["trade_date"], df["atr_14"], color="#0891b2")
    axes[3].set_ylabel("ATR")
    axes[3].set_xlabel("日期")

    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def write_report(latest: pd.DataFrame, missing: pd.DataFrame, desc: pd.DataFrame, overview_chart_paths: list[Path]) -> None:
    lines = [
        "# Task2 金融数据技术指标分析",
        "",
        "## 任务思路",
        "1. 读取本地 CSV，统一日期和数值字段。",
        "2. 先做缺失值与描述性统计，确认数据可用。",
        "3. 基于收盘价与 OHLC 数据计算 RSI、MACD、布林带和 ATR。",
        "4. 输出指标 CSV、图表 PNG、Markdown 报告，并由 `build_site.py` 生成网页。",
        "",
        "## 数据整体画像",
        "本报告先用三类图表描述数据整体情况，再进入技术指标分析：",
        *[f"- `{path.name}`" for path in overview_chart_paths],
        "",
        "## 最新交易日指标",
        markdown_table(latest),
        "",
        "## 缺失值合计",
        markdown_table(missing.groupby("stock_name", as_index=False)["missing_count"].sum()),
        "",
        "## 描述性统计",
        markdown_table(desc[["stock_name", "column", "mean", "std", "min", "max"]].round(4)),
    ]
    (OUTPUT_DIR / "analysis_report.md").write_text("\n".join(lines), encoding="utf-8")


def run() -> dict[str, object]:
    OUTPUT_DIR.mkdir(exist_ok=True)
    latest_rows, missing_tables, desc_tables, indicator_paths, chart_paths = [], [], [], [], []
    frames: list[dict[str, object]] = []

    for path in sorted(DATA_DIR.glob("*.csv")):
        name = stock_name(path)
        data = load_prices(path)
        frames.append({"name": name, "data": data})
        full = add_indicators(data)
        code = full["ts_code"].iloc[0]

        missing, desc = diagnostics(name, data)
        missing_tables.append(missing)
        desc_tables.append(desc)

        indicator_path = OUTPUT_DIR / f"{slug(code)}_indicators.csv"
        chart_path = OUTPUT_DIR / f"{slug(code)}_technical_indicators.png"
        full.to_csv(indicator_path, index=False, encoding="utf-8-sig")
        plot_indicators(full, name, chart_path)

        latest = full.iloc[-1]
        latest_rows.append(
            {
                "stock_name": name,
                "ts_code": code,
                "trade_date": latest["trade_date"].strftime("%Y-%m-%d"),
                "close": round(latest["close"], 4),
                "rsi_14": round(latest["rsi_14"], 4),
                "macd": round(latest["macd"], 4),
                "macd_signal": round(latest["macd_signal"], 4),
                "bb_upper_20": round(latest["bb_upper_20"], 4),
                "bb_lower_20": round(latest["bb_lower_20"], 4),
                "atr_14": round(latest["atr_14"], 4),
            }
        )
        indicator_paths.append(indicator_path)
        chart_paths.append(chart_path)

    latest = pd.DataFrame(latest_rows)
    missing = pd.concat(missing_tables, ignore_index=True)
    desc = pd.concat(desc_tables, ignore_index=True)
    overview_chart_paths = [
        OUTPUT_DIR / "data_description_overview.png",
        OUTPUT_DIR / "price_volume_overview.png",
        OUTPUT_DIR / "daily_return_distribution.png",
    ]
    plot_data_description(frames, missing, overview_chart_paths[0])
    plot_price_volume(frames, overview_chart_paths[1])
    plot_return_distribution(frames, overview_chart_paths[2])

    latest.to_csv(OUTPUT_DIR / "latest_indicator_snapshot.csv", index=False, encoding="utf-8-sig")
    missing.to_csv(OUTPUT_DIR / "missing_values.csv", index=False, encoding="utf-8-sig")
    desc.to_csv(OUTPUT_DIR / "diagnostics_summary.csv", index=False, encoding="utf-8-sig")
    write_report(latest, missing, desc, overview_chart_paths)
    return {
        "latest": latest,
        "indicator_paths": indicator_paths,
        "chart_paths": chart_paths,
        "overview_chart_paths": overview_chart_paths,
    }


def main() -> None:
    result = run()
    print(f"Generated {len(result['indicator_paths'])} indicator CSV files.")


if __name__ == "__main__":
    main()
