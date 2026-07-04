from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import tushare as ts


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
TS_CODE = "688256.SH"
STOCK_NAME = "寒武纪"


def load_env(path: Path = TASK_DIR / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d")
    out = out.sort_values("trade_date").reset_index(drop=True)
    out["date"] = out["trade_date"].dt.strftime("%Y-%m-%d")
    return out


def fetch_raw_data(token: str, start_date: str, end_date: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pro = ts.pro_api(token)
    daily = pro.daily(ts_code=TS_CODE, start_date=start_date, end_date=end_date)
    adj = pro.adj_factor(ts_code=TS_CODE, start_date=start_date, end_date=end_date)
    if daily.empty or adj.empty:
        raise RuntimeError("TuShare returned empty daily or adj_factor data.")
    return normalize(daily), normalize(adj)


def add_forward_adjusted_prices(daily: pd.DataFrame, adj: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_cols = ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    daily = daily.copy()
    adj = adj.copy()
    daily[price_cols] = daily[price_cols].apply(pd.to_numeric, errors="coerce")
    adj["adj_factor"] = pd.to_numeric(adj["adj_factor"], errors="coerce")

    combined = daily.merge(adj[["trade_date", "adj_factor"]], on="trade_date", how="left")
    if combined["adj_factor"].isna().any():
        raise RuntimeError("Some trading days are missing adjustment factors.")

    latest_factor = combined["adj_factor"].iloc[-1]
    qfq = combined[["ts_code", "trade_date", "date", "adj_factor", "vol", "amount"]].copy()
    for col in ["open", "high", "low", "close"]:
        qfq[f"qfq_{col}"] = combined[col] * combined["adj_factor"] / latest_factor

    qfq["qfq_pre_close"] = qfq["qfq_close"].shift(1)
    qfq["qfq_change"] = qfq["qfq_close"].diff()
    qfq["qfq_pct_chg"] = qfq["qfq_change"] / qfq["qfq_pre_close"] * 100

    unadjusted = combined[
        ["ts_code", "trade_date", "date", *price_cols, "adj_factor"]
    ].copy()
    combined = unadjusted.merge(
        qfq[["trade_date", "qfq_open", "qfq_high", "qfq_low", "qfq_close", "qfq_pre_close", "qfq_change", "qfq_pct_chg"]],
        on="trade_date",
        how="left",
    )
    return unadjusted, qfq, combined


def save_outputs(unadjusted: pd.DataFrame, qfq: pd.DataFrame, combined: pd.DataFrame, start_date: str, end_date: str) -> dict[str, Path]:
    DATA_DIR.mkdir(exist_ok=True)
    suffix = f"{start_date}_{end_date}"
    paths = {
        "unadjusted": DATA_DIR / f"cambricon_688256_SH_daily_unadjusted_{suffix}.csv",
        "qfq": DATA_DIR / f"cambricon_688256_SH_daily_qfq_{suffix}.csv",
        "combined": DATA_DIR / f"cambricon_688256_SH_daily_combined_{suffix}.csv",
    }
    unadjusted.to_csv(paths["unadjusted"], index=False, encoding="utf-8-sig")
    qfq.to_csv(paths["qfq"], index=False, encoding="utf-8-sig")
    combined.to_csv(paths["combined"], index=False, encoding="utf-8-sig")
    return paths


def parse_args() -> argparse.Namespace:
    end = date.today()
    start = end - timedelta(days=365)
    parser = argparse.ArgumentParser(description="Fetch Cambricon daily data from TuShare.")
    parser.add_argument("--start-date", default=start.strftime("%Y%m%d"))
    parser.add_argument("--end-date", default=end.strftime("%Y%m%d"))
    parser.add_argument("--token", default=None)
    return parser.parse_args()


def main() -> dict[str, Path]:
    args = parse_args()
    load_env()
    token = args.token or os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise SystemExit("Set TUSHARE_TOKEN, create Task1/.env, or pass --token.")

    daily, adj = fetch_raw_data(token, args.start_date, args.end_date)
    return save_outputs(*add_forward_adjusted_prices(daily, adj), args.start_date, args.end_date)


if __name__ == "__main__":
    outputs = main()
    for name, path in outputs.items():
        print(f"{name}: {path}")
