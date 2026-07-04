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


def plot_indicators(df: pd.DataFrame, name: str, output: Path) -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
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


def write_report(latest: pd.DataFrame, missing: pd.DataFrame, desc: pd.DataFrame) -> None:
    lines = [
        "# Task2 金融数据技术指标分析",
        "",
        "## 任务思路",
        "1. 读取本地 CSV，统一日期和数值字段。",
        "2. 先做缺失值与描述性统计，确认数据可用。",
        "3. 基于收盘价与 OHLC 数据计算 RSI、MACD、布林带和 ATR。",
        "4. 输出指标 CSV、图表 PNG、Markdown 报告，并由 `build_site.py` 生成网页。",
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

    for path in sorted(DATA_DIR.glob("*.csv")):
        name = stock_name(path)
        data = load_prices(path)
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
    latest.to_csv(OUTPUT_DIR / "latest_indicator_snapshot.csv", index=False, encoding="utf-8-sig")
    missing.to_csv(OUTPUT_DIR / "missing_values.csv", index=False, encoding="utf-8-sig")
    desc.to_csv(OUTPUT_DIR / "diagnostics_summary.csv", index=False, encoding="utf-8-sig")
    write_report(latest, missing, desc)
    return {"latest": latest, "indicator_paths": indicator_paths, "chart_paths": chart_paths}


def main() -> None:
    result = run()
    print(f"Generated {len(result['indicator_paths'])} indicator CSV files.")


if __name__ == "__main__":
    main()
