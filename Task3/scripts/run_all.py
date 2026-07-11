from __future__ import annotations

import argparse
import getpass
import os
from datetime import date, timedelta

from analyze_results import build_analysis_outputs
from build_site import build_site
from build_walkthrough_notebook import build_notebook
from fetch_data import fetch_universe
from strategy_backtest import run_all_backtests
from validate_results import validate_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="一键生成 Task3 数据、回测、图表、报告、Notebook 和网页")
    parser.add_argument("--skip-fetch", action="store_true", help="使用本地数据快照，不访问网络")
    parser.add_argument("--force-fetch", action="store_true", help="覆盖已有本地数据快照")
    parser.add_argument("--start-date", default="20190101")
    parser.add_argument("--end-date", default=(date.today() - timedelta(days=1)).strftime("%Y%m%d"))
    parser.add_argument("--source", choices=["tushare", "eastmoney"], default="tushare")
    parser.add_argument("--prompt-token", action="store_true", help="安全地交互输入 TuShare Token")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_fetch:
        token = os.environ.get("TUSHARE_TOKEN")
        if args.source == "tushare" and not token and args.prompt_token:
            token = getpass.getpass("TuShare Token: ")
        fetch_universe(args.start_date, args.end_date, force=args.force_fetch, source=args.source, token=token)
    summary, industry_summary = run_all_backtests()
    print(f"参数回测结果: {len(summary)} rows")
    print(f"行业汇总结果: {len(industry_summary)} rows")
    for name, path in build_analysis_outputs().items():
        print(f"{name}: {path}")
    notebook = build_notebook()
    print(f"notebook: {notebook}")
    website = build_site()
    print(f"website: {website}")
    validation = validate_results()
    print(f"validation: {validation}")


if __name__ == "__main__":
    main()
