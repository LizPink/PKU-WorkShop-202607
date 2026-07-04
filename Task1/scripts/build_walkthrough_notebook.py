from __future__ import annotations

import json
import textwrap
import uuid
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = TASK_DIR / "Task1_process_walkthrough.ipynb"


def cell(kind: str, source: str) -> dict[str, object]:
    data = {
        "cell_type": kind,
        "id": uuid.uuid4().hex[:8],
        "metadata": {},
        "source": textwrap.dedent(source).strip().splitlines(keepends=True),
    }
    if kind == "code":
        data.update({"execution_count": None, "outputs": []})
    return data


def md(source: str) -> dict[str, object]:
    return cell("markdown", source)


def code(source: str) -> dict[str, object]:
    return cell("code", source)


def build_notebook() -> dict[str, object]:
    cells = [
        md(
            """
            # Task1 寒武纪行情 demo walkthrough

            这份 notebook 用教学方式复盘 Task1：数据从哪里来、前复权怎么计算、网页怎么生成。Notebook 不复制长脚本，只展示关键步骤；完整实现见 `scripts/`。
            """
        ),
        md(
            """
            ## Goal

            Task1 要做的是一个最小数据产品：

            1. 从 TuShare 获取寒武纪日线行情和复权因子。
            2. 计算前复权价格，并保存三份 CSV。
            3. 用 matplotlib 生成价格图。
            4. 写出一个静态网页 `web/index.html`。
            """
        ),
        md(
            """
            ## Setup

            项目环境由根目录 `pyproject.toml` 和 `uv.lock` 管理：

            ```powershell
            uv sync --group dev
            ```

            如果只是学习流程，可以直接读取已经保存好的 CSV，不需要 TuShare token。
            """
        ),
        code(
            """
            from pathlib import Path
            import sys

            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import pandas as pd

            ROOT = Path.cwd()
            TASK_DIR = ROOT / "Task1" if (ROOT / "Task1").exists() else ROOT
            SCRIPTS = TASK_DIR / "scripts"
            if str(SCRIPTS) not in sys.path:
                sys.path.insert(0, str(SCRIPTS))

            from build_site import build_site

            DATA_DIR = TASK_DIR / "data"
            WEB_DIR = TASK_DIR / "web"
            """
        ),
        md(
            """
            ## Steps

            ### 1. 读取已经保存的 combined CSV

            `combined` 文件把未复权价格、复权因子、前复权价格合在一张表里，最适合后续展示。
            """
        ),
        code(
            """
            combined_csv = sorted(DATA_DIR.glob("cambricon_688256_SH_daily_combined_*.csv"))[-1]
            df = pd.read_csv(combined_csv, parse_dates=["trade_date"])
            df.head()
            """
        ),
        md(
            """
            ### 2. 做一个最小摘要

            这里不需要复杂统计，只要确认日期区间、最新价格和区间收益即可。
            """
        ),
        code(
            """
            first, latest = df.iloc[0], df.iloc[-1]
            summary = {
                "rows": len(df),
                "start": first["date"],
                "end": latest["date"],
                "latest_close": latest["close"],
                "qfq_return": latest["qfq_close"] / first["qfq_close"] - 1,
            }
            summary
            """
        ),
        md(
            """
            ### 3. 理解前复权公式

            复权的目的是把分红、送转等因素调整进历史价格。Task1 使用的公式是：

            ```text
            前复权价格 = 未复权价格 * 当日复权因子 / 区间最新复权因子
            ```
            """
        ),
        code(
            """
            demo = df[["date", "close", "adj_factor", "qfq_close"]].head(3).copy()
            latest_factor = df["adj_factor"].iloc[-1]
            demo["manual_qfq_close"] = demo["close"] * demo["adj_factor"] / latest_factor
            demo
            """
        ),
        md(
            """
            ### 4. 画出价格走势

            实际网页由 `scripts/build_site.py` 完成。这里用几行代码展示核心图形是什么。
            """
        ),
        code(
            """
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(df["trade_date"], df["close"], label="未复权收盘价")
            ax.plot(df["trade_date"], df["qfq_close"], label="前复权收盘价")
            ax.set_title("寒武纪收盘价走势")
            ax.grid(True, alpha=0.25)
            ax.legend()
            fig.tight_layout()
            plt.show()
            """
        ),
        md(
            """
            ### 5. 生成网页

            代码拆分后，网页生成只需要读取 CSV、画图、写 HTML。
            """
        ),
        code(
            """
            html_path = build_site(combined_csv)
            html_path
            """
        ),
        md(
            """
            ## Checks

            确认网页和图片都存在。
            """
        ),
        code(
            """
            assert html_path.exists()
            assert (WEB_DIR / "cambricon_price.png").exists()
            "Task1 walkthrough checks passed"
            """
        ),
        md(
            """
            ## Next Steps

            - 需要刷新数据时，运行 `uv run python .\\Task1\\scripts\\run_all.py --start-date ... --end-date ...`。
            - 只改网页样式时，运行 `uv run python .\\Task1\\scripts\\run_all.py --skip-fetch`。
            """
        ),
    ]
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    NOTEBOOK_PATH.write_text(json.dumps(build_notebook(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Notebook written to: {NOTEBOOK_PATH}")


if __name__ == "__main__":
    main()
