from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    DATA_END,
    DATA_START,
    INDEX_CODE,
    MAX_STOCKS,
    RAW_DAILY_DIR,
    RAW_DIR,
    ensure_directories,
)


HISTORY_COLUMNS = [
    "trade_date",
    "ts_code",
    "open",
    "close",
    "high",
    "low",
    "volume",
    "amount",
    "amplitude_pct",
    "pct_change",
    "price_change",
    "turnover_rate",
]


def import_akshare():
    try:
        import akshare as ak
    except ImportError as exc:
        raise SystemExit(
            "AkShare is required only for data fetching. Install it or run this script "
            "with the Codex bundled Python runtime that already includes AkShare."
        ) from exc
    return ak


def load_constituents(index_code: str, max_stocks: int) -> pd.DataFrame:
    ak = import_akshare()
    raw = ak.index_stock_cons_csindex(symbol=index_code)
    if raw.empty or raw.shape[1] < 6:
        raise RuntimeError("AkShare returned an empty or unexpected constituent table.")
    result = pd.DataFrame(
        {
            "constituent_as_of": pd.to_datetime(raw.iloc[:, 0], errors="coerce"),
            "index_code": raw.iloc[:, 1].astype(str).str.zfill(6),
            "index_name": raw.iloc[:, 2].astype(str),
            "ts_code": raw.iloc[:, 4].astype(str).str.extract(r"(\d{6})", expand=False),
            "stock_name": raw.iloc[:, 5].astype(str),
            "exchange": raw.iloc[:, 7].astype(str) if raw.shape[1] > 7 else "",
        }
    ).dropna(subset=["ts_code"])
    result = result.drop_duplicates("ts_code").sort_values("ts_code").reset_index(drop=True)
    if max_stocks < len(result):
        positions = np.linspace(0, len(result) - 1, max_stocks, dtype=int)
        result = result.iloc[positions].reset_index(drop=True)
    if len(result) < 31:
        raise RuntimeError(f"Only {len(result)} constituents were returned; at least 31 are required.")
    return result


def normalize_history(raw: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    if raw.empty or raw.shape[1] < len(HISTORY_COLUMNS):
        raise RuntimeError("empty or unexpected daily history")
    out = raw.iloc[:, : len(HISTORY_COLUMNS)].copy()
    out.columns = HISTORY_COLUMNS
    out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    out["ts_code"] = code
    out["stock_name"] = name
    numeric_columns = [column for column in HISTORY_COLUMNS if column not in {"trade_date", "ts_code"}]
    out[numeric_columns] = out[numeric_columns].apply(pd.to_numeric, errors="coerce")
    out = out.dropna(subset=["trade_date", "open", "close"]).sort_values("trade_date")
    out = out.drop_duplicates(["ts_code", "trade_date"], keep="last")
    if len(out) < 300:
        raise RuntimeError(f"insufficient history: {len(out)} rows")
    return out.reset_index(drop=True)


def normalize_tencent_history(raw: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
    required = {"date", "open", "close", "high", "low", "amount"}
    if raw.empty or not required.issubset(raw.columns):
        raise RuntimeError("empty or unexpected Tencent daily history")
    out = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(raw["date"], errors="coerce"),
            "ts_code": code,
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "volume": pd.to_numeric(raw["amount"], errors="coerce"),
            "amount": np.nan,
        }
    )
    out["amplitude_pct"] = (out["high"] - out["low"]) / out["close"].replace(0, np.nan) * 100
    out["pct_change"] = out["close"].pct_change(fill_method=None) * 100
    out["price_change"] = out["close"].diff()
    out["turnover_rate"] = np.nan
    out["stock_name"] = name
    out = out.dropna(subset=["trade_date", "open", "close"]).sort_values("trade_date")
    out = out.drop_duplicates(["ts_code", "trade_date"], keep="last")
    if len(out) < 300:
        raise RuntimeError(f"insufficient Tencent history: {len(out)} rows")
    return out.reset_index(drop=True)


def fetch_one(code: str, name: str, start_date: str, end_date: str, retries: int) -> tuple[str, int, str]:
    destination = RAW_DAILY_DIR / f"{code}.csv"
    if destination.exists() and destination.stat().st_size > 10_000:
        cached = pd.read_csv(destination, usecols=["trade_date"])
        if len(cached) >= 300:
            return code, len(cached), "cached"

    ak = import_akshare()
    last_error = ""
    for attempt in range(1, retries + 1):
        try:
            raw = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="hfq",
                timeout=30,
            )
            normalized = normalize_history(raw, code, name)
            normalized.to_csv(destination, index=False, encoding="utf-8-sig", float_format="%.8f")
            return code, len(normalized), "downloaded"
        except Exception as exc:  # network providers can fail transiently
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(2**attempt, 12))

    exchange_prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
    for attempt in range(1, 3):
        try:
            raw = ak.stock_zh_a_hist_tx(
                symbol=f"{exchange_prefix}{code}",
                start_date=start_date,
                end_date=end_date,
                adjust="hfq",
                timeout=30,
            )
            normalized = normalize_tencent_history(raw, code, name)
            normalized.to_csv(destination, index=False, encoding="utf-8-sig", float_format="%.8f")
            return code, len(normalized), "downloaded_tencent_fallback"
        except Exception as exc:
            last_error = f"Eastmoney failed; Tencent {type(exc).__name__}: {exc}"
            time.sleep(min(2**attempt, 6))
    return code, 0, last_error


def combine_history(constituents: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    available_codes: list[str] = []
    for path in sorted(RAW_DAILY_DIR.glob("*.csv")):
        try:
            frame = pd.read_csv(path, parse_dates=["trade_date"])
        except Exception:
            continue
        if not frame.empty:
            frames.append(frame)
            available_codes.append(path.stem)
    if not frames:
        raise RuntimeError("No stock history files were successfully downloaded.")
    combined = pd.concat(frames, ignore_index=True)
    allowed = set(constituents["ts_code"])
    combined = combined.loc[combined["ts_code"].astype(str).str.zfill(6).isin(allowed)].copy()
    combined["ts_code"] = combined["ts_code"].astype(str).str.zfill(6)
    # Older cached Tencent fallback files used the provider's sixth k-line field
    # as amount. It is a volume-like field, so normalize those rows here.
    tencent_legacy_mask = combined["volume"].isna() & combined["amount"].notna() & combined["turnover_rate"].isna()
    combined.loc[tencent_legacy_mask, "volume"] = combined.loc[tencent_legacy_mask, "amount"]
    combined.loc[tencent_legacy_mask, "amount"] = np.nan
    combined = combined.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    combined.to_csv(RAW_DIR / "csi300_current_constituents_daily_hfq.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    return combined


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch current CSI 300 constituents and adjusted daily history with AkShare.")
    parser.add_argument("--index-code", default=INDEX_CODE)
    parser.add_argument("--start-date", default=DATA_START)
    parser.add_argument("--end-date", default=DATA_END)
    parser.add_argument("--max-stocks", type=int, default=MAX_STOCKS)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--retries", type=int, default=4)
    args = parser.parse_args()

    ensure_directories()
    constituents = load_constituents(args.index_code, args.max_stocks)
    constituents.to_csv(RAW_DIR / "csi300_current_constituents.csv", index=False, encoding="utf-8-sig")

    failures: list[dict[str, str]] = []
    statuses: list[dict[str, object]] = []
    print(f"Fetching {len(constituents)} stocks from {args.start_date} to {args.end_date} ...", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        future_map = {
            executor.submit(
                fetch_one,
                row.ts_code,
                row.stock_name,
                args.start_date,
                args.end_date,
                args.retries,
            ): row.ts_code
            for row in constituents.itertuples(index=False)
        }
        completed = 0
        for future in as_completed(future_map):
            code = future_map[future]
            completed += 1
            try:
                code, rows, status = future.result()
            except Exception as exc:
                rows, status = 0, f"{type(exc).__name__}: {exc}"
            statuses.append({"ts_code": code, "rows": rows, "status": status})
            if rows == 0:
                failures.append({"ts_code": code, "error": status})
            if completed % 10 == 0 or rows == 0 or completed == len(future_map):
                print(
                    f"[{completed:03d}/{len(future_map):03d}] {code}: rows={rows}, status={status}",
                    flush=True,
                )

    status_frame = pd.DataFrame(statuses).sort_values("ts_code")
    status_frame.to_csv(RAW_DIR / "fetch_status.csv", index=False, encoding="utf-8-sig")
    combined = combine_history(constituents)
    metadata = {
        "source": "AkShare 1.18.64; CSI index constituent list; Eastmoney/Tencent backward-adjusted daily history",
        "price_adjustment": "hfq (backward adjusted)",
        "index_code": args.index_code,
        "constituent_selection": "current constituents as returned on fetch date",
        "fetched_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "requested_start": args.start_date,
        "requested_end": args.end_date,
        "requested_stocks": int(len(constituents)),
        "successful_stocks": int(combined["ts_code"].nunique()),
        "daily_rows": int(len(combined)),
        "min_trade_date": str(combined["trade_date"].min().date()),
        "max_trade_date": str(combined["trade_date"].max().date()),
        "failed_stocks": failures,
        "known_limitation": "The constituent list is current rather than point-in-time, so historical results have survivorship/selection bias.",
    }
    (RAW_DIR / "source_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in metadata.items() if key != "failed_stocks"}, ensure_ascii=False, indent=2))
    if metadata["successful_stocks"] < 60:
        raise SystemExit("Fewer than 60 stocks were downloaded; the cross-sectional sample is too small.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
