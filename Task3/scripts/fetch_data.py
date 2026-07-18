from __future__ import annotations

import argparse
import getpass
import json
import os
import time
from datetime import date, timedelta
from http.client import RemoteDisconnected
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import tushare as ts

from config import DEFAULT_START_DATE, UNIVERSE, StockSpec, code_slug


TASK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = TASK_DIR / "data"
SOURCE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
NUMERIC_COLUMNS = [
    "open",
    "close",
    "high",
    "low",
    "vol",
    "amount",
    "amplitude",
    "pct_chg",
    "change",
    "turnover_rate",
]


def market_secid(ts_code: str) -> str:
    code, exchange = ts_code.split(".")
    market = "1" if exchange == "SH" else "0"
    return f"{market}.{code}"


def output_path(spec: StockSpec) -> Path:
    return DATA_DIR / f"{code_slug(spec.ts_code)}_daily_qfq.csv"


def fetch_one(spec: StockSpec, start_date: str, end_date: str, retries: int = 3) -> pd.DataFrame:
    params = {
        "secid": market_secid(spec.ts_code),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": start_date,
        "end": end_date,
        "rtntype": "6",
    }
    request = Request(
        f"{SOURCE_URL}?{urlencode(params)}",
        headers={"User-Agent": "Mozilla/5.0 PKU-Workshop-Task3/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            data = payload.get("data")
            if not data or not data.get("klines"):
                raise RuntimeError(f"行情接口未返回 {spec.ts_code} 的有效数据")
            rows = [item.split(",") for item in data["klines"]]
            frame = pd.DataFrame(
                rows,
                columns=[
                    "trade_date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "vol",
                    "amount",
                    "amplitude",
                    "pct_chg",
                    "change",
                    "turnover_rate",
                ],
            )
            frame[NUMERIC_COLUMNS] = frame[NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce")
            frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
            frame.insert(0, "ts_code", spec.ts_code)
            frame.insert(1, "stock_name", spec.stock_name)
            frame.insert(2, "industry", spec.industry)
            frame["pre_close"] = frame["close"].shift(1)
            frame["price_type"] = "前复权"
            frame["source"] = "东方财富历史行情公开接口"
            return frame.sort_values("trade_date").reset_index(drop=True)
        except (HTTPError, URLError, TimeoutError, RemoteDisconnected, ConnectionError, RuntimeError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.2 * attempt)
    raise RuntimeError(f"抓取 {spec.ts_code} 失败: {last_error}") from last_error


def fetch_one_tushare(spec: StockSpec, start_date: str, end_date: str, token: str) -> pd.DataFrame:
    pro = ts.pro_api(token)
    daily = pro.daily(ts_code=spec.ts_code, start_date=start_date, end_date=end_date)
    try:
        adjustment = pro.adj_factor(ts_code=spec.ts_code, start_date=start_date, end_date=end_date)
    except Exception as exc:
        if "频率超限" not in str(exc):
            raise
        print(f"{spec.ts_code} TuShare 复权因子受限，改用公开前复权行情并与 TuShare 日线日期校验。")
        try:
            adjusted = fetch_one(spec, start_date, end_date)
        except RuntimeError:
            print(f"{spec.ts_code} 公开前复权接口连接失败，改用 TuShare 旧版前复权接口。")
            adjusted = fetch_one_tushare_legacy(spec, start_date, end_date, daily)
        tushare_dates = set(pd.to_datetime(daily["trade_date"], format="%Y%m%d", errors="coerce").dropna())
        adjusted_dates = set(adjusted["trade_date"].dropna())
        coverage = len(tushare_dates & adjusted_dates) / max(1, len(tushare_dates))
        if coverage < 0.98:
            raise RuntimeError(f"{spec.ts_code} 双来源交易日期覆盖率仅 {coverage:.2%}") from exc
        adjusted["adj_factor"] = pd.NA
        if not adjusted["source"].astype(str).str.contains("TuShare legacy").all():
            adjusted["source"] = "TuShare Pro daily 日期校验 + 东方财富前复权行情"
        return adjusted
    if daily.empty or adjustment.empty:
        raise RuntimeError(f"TuShare 未返回 {spec.ts_code} 的 daily 或 adj_factor 数据")

    daily["trade_date"] = pd.to_datetime(daily["trade_date"], format="%Y%m%d", errors="coerce")
    adjustment["trade_date"] = pd.to_datetime(adjustment["trade_date"], format="%Y%m%d", errors="coerce")
    raw_numeric = ["open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"]
    daily[raw_numeric] = daily[raw_numeric].apply(pd.to_numeric, errors="coerce")
    adjustment["adj_factor"] = pd.to_numeric(adjustment["adj_factor"], errors="coerce")
    combined = daily.merge(adjustment[["trade_date", "adj_factor"]], on="trade_date", how="left")
    combined = combined.sort_values("trade_date").reset_index(drop=True)
    if combined["adj_factor"].isna().any():
        raise RuntimeError(f"{spec.ts_code} 存在缺失复权因子")

    latest_factor = combined["adj_factor"].iloc[-1]
    for column in ["open", "high", "low", "close"]:
        combined[column] = combined[column] * combined["adj_factor"] / latest_factor
    combined["pre_close"] = combined["close"].shift(1)
    combined["change"] = combined["close"].diff()
    combined["pct_chg"] = combined["close"].pct_change() * 100
    combined["amplitude"] = (combined["high"] - combined["low"]) / combined["pre_close"] * 100
    combined["turnover_rate"] = pd.NA
    combined.insert(1, "stock_name", spec.stock_name)
    combined.insert(2, "industry", spec.industry)
    combined["price_type"] = "前复权"
    combined["source"] = "TuShare Pro: daily + adj_factor"
    return combined[
        [
            "ts_code",
            "stock_name",
            "industry",
            "trade_date",
            "open",
            "close",
            "high",
            "low",
            "pre_close",
            "change",
            "pct_chg",
            "vol",
            "amount",
            "amplitude",
            "turnover_rate",
            "adj_factor",
            "price_type",
            "source",
        ]
    ]


def fetch_one_tushare_legacy(spec: StockSpec, start_date: str, end_date: str, daily: pd.DataFrame) -> pd.DataFrame:
    # TuShare 旧接口仍依赖 pandas.DataFrame.append；为 pandas 3 提供最小兼容层。
    if not hasattr(pd.DataFrame, "append"):
        pd.DataFrame.append = lambda self, other, ignore_index=False, **kwargs: pd.concat(  # type: ignore[attr-defined,method-assign]
            [self, other], ignore_index=ignore_index
        )
    code = spec.ts_code.split(".")[0]
    adjusted = ts.get_k_data(
        code,
        start=pd.to_datetime(start_date).strftime("%Y-%m-%d"),
        end=pd.to_datetime(end_date).strftime("%Y-%m-%d"),
        ktype="D",
        autype="qfq",
        retry_count=3,
        pause=0.3,
    )
    if adjusted.empty:
        raise RuntimeError(f"TuShare 旧版接口未返回 {spec.ts_code} 前复权数据")
    adjusted = adjusted.rename(columns={"date": "trade_date"})
    adjusted["trade_date"] = pd.to_datetime(adjusted["trade_date"], errors="coerce")
    adjusted[["open", "high", "low", "close"]] = adjusted[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")

    daily_copy = daily.copy()
    daily_copy["trade_date"] = pd.to_datetime(daily_copy["trade_date"], format="%Y%m%d", errors="coerce")
    daily_copy[["vol", "amount"]] = daily_copy[["vol", "amount"]].apply(pd.to_numeric, errors="coerce")
    frame = adjusted[["trade_date", "open", "close", "high", "low"]].merge(
        daily_copy[["trade_date", "vol", "amount"]], on="trade_date", how="inner"
    )
    frame.insert(0, "ts_code", spec.ts_code)
    frame.insert(1, "stock_name", spec.stock_name)
    frame.insert(2, "industry", spec.industry)
    frame["pre_close"] = frame["close"].shift(1)
    frame["change"] = frame["close"].diff()
    frame["pct_chg"] = frame["close"].pct_change() * 100
    frame["amplitude"] = (frame["high"] - frame["low"]) / frame["pre_close"] * 100
    frame["turnover_rate"] = pd.NA
    frame["price_type"] = "前复权"
    frame["source"] = "TuShare Pro daily + TuShare legacy qfq"
    return frame.sort_values("trade_date").reset_index(drop=True)


def validate_frame(spec: StockSpec, frame: pd.DataFrame, start_date: str, end_date: str) -> dict[str, object]:
    required = {"trade_date", "open", "high", "low", "close", "vol", "amount"}
    missing_columns = sorted(required - set(frame.columns))
    duplicate_dates = int(frame["trade_date"].duplicated().sum()) if "trade_date" in frame else -1
    missing_required = int(frame[list(required - {"trade_date"})].isna().sum().sum()) if not missing_columns else -1
    invalid_ohlc = int(
        (
            (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
            | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
            | (frame[["open", "high", "low", "close"]] <= 0).any(axis=1)
        ).sum()
    ) if not missing_columns else -1
    usable = not missing_columns and duplicate_dates == 0 and missing_required == 0 and invalid_ohlc == 0 and len(frame) >= 60
    return {
        "ts_code": spec.ts_code,
        "stock_name": spec.stock_name,
        "industry": spec.industry,
        "requested_start": pd.to_datetime(start_date).strftime("%Y-%m-%d"),
        "requested_end": pd.to_datetime(end_date).strftime("%Y-%m-%d"),
        "actual_start": frame["trade_date"].min().strftime("%Y-%m-%d") if len(frame) else "",
        "actual_end": frame["trade_date"].max().strftime("%Y-%m-%d") if len(frame) else "",
        "rows": len(frame),
        "duplicate_dates": duplicate_dates,
        "missing_required_values": missing_required,
        "invalid_ohlc_rows": invalid_ohlc,
        "source": str(frame["source"].iloc[0]) if "source" in frame and len(frame) else "",
        "is_usable": usable,
    }


def fetch_universe(
    start_date: str,
    end_date: str,
    force: bool = False,
    pause: float = 0.25,
    source: str = "tushare",
    token: str | None = None,
) -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    quality_rows: list[dict[str, object]] = []
    universe_rows: list[dict[str, object]] = []

    for index, spec in enumerate(UNIVERSE):
        path = output_path(spec)
        if path.exists() and not force:
            frame = pd.read_csv(path, parse_dates=["trade_date"])
        else:
            if source == "tushare":
                if not token:
                    raise RuntimeError("使用 TuShare 数据源时必须通过环境变量或交互输入提供 Token")
                frame = fetch_one_tushare(spec, start_date, end_date, token)
            elif source == "eastmoney":
                frame = fetch_one(spec, start_date, end_date)
            else:
                raise ValueError(f"不支持的数据源: {source}")
            frame.to_csv(path, index=False, encoding="utf-8-sig")
            if index < len(UNIVERSE) - 1:
                time.sleep(pause)
        quality_rows.append(validate_frame(spec, frame, start_date, end_date))
        universe_rows.append(
            {
                "ts_code": spec.ts_code,
                "stock_name": spec.stock_name,
                "industry": spec.industry,
                "file": path.name,
                "price_type": "前复权",
                "source": str(frame["source"].iloc[0]) if "source" in frame and len(frame) else "",
                "downloaded_on": date.today().isoformat(),
            }
        )
        print(f"{spec.ts_code} {spec.stock_name}: {len(frame)} rows")

    universe = pd.DataFrame(universe_rows)
    quality = pd.DataFrame(quality_rows)
    universe.to_csv(DATA_DIR / "universe.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(DATA_DIR / "data_quality_summary.csv", index=False, encoding="utf-8-sig")
    if not quality["is_usable"].all():
        failed = quality.loc[~quality["is_usable"], "ts_code"].tolist()
        raise RuntimeError(f"以下股票未通过数据质量检查: {failed}")
    return quality


def parse_args() -> argparse.Namespace:
    latest_complete_day = date.today() - timedelta(days=1)
    parser = argparse.ArgumentParser(description="抓取 Task3 跨行业股票日线前复权数据")
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=latest_complete_day.strftime("%Y%m%d"))
    parser.add_argument("--force", action="store_true", help="覆盖本地数据快照")
    parser.add_argument("--source", choices=["tushare", "eastmoney"], default="tushare")
    parser.add_argument("--prompt-token", action="store_true", help="安全地交互输入 TuShare Token")
    return parser.parse_args()


def main() -> pd.DataFrame:
    args = parse_args()
    token = os.environ.get("TUSHARE_TOKEN")
    if args.source == "tushare" and not token and args.prompt_token:
        token = getpass.getpass("TuShare Token: ")
    return fetch_universe(args.start_date, args.end_date, force=args.force, source=args.source, token=token)


if __name__ == "__main__":
    result = main()
    print(result.to_string(index=False))
