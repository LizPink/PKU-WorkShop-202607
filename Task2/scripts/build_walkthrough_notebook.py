from __future__ import annotations

import json
import textwrap
import uuid
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = TASK_DIR / "Task2_process_walkthrough.ipynb"


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
            # Task2 技术指标分析 walkthrough

            这份 notebook 用教学方式复盘 Task2：本地行情 CSV 如何诊断、指标如何计算、图表和网页如何生成。Notebook 展示关键路径，完整细节见 `scripts/`。
            """
        ),
        md(
            """
            ## Goal

            目标是把两个本地股票 CSV 做成一个技术指标 demo：

            1. 检查缺失值和描述性统计量。
            2. 绘制三类整体数据画像：缺失/特征分布、价格成交量、日收益率分布。
            3. 计算 RSI、MACD、布林带和 ATR。
            4. 用 matplotlib 绘制指标图。
            5. 生成 `outputs/` 和 `web/index.html`。
            """
        ),
        md(
            """
            ## Setup

            环境由根目录 `uv` 项目管理：

            ```powershell
            uv sync --group dev
            ```
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
            TASK_DIR = ROOT / "Task2" if (ROOT / "Task2").exists() else ROOT
            SCRIPTS = TASK_DIR / "scripts"
            if str(SCRIPTS) not in sys.path:
                sys.path.insert(0, str(SCRIPTS))

            from IPython.display import Image, display

            from build_site import build_site
            from calculate_indicators import (
                DATA_DIR,
                OUTPUT_DIR,
                add_indicators,
                diagnostics,
                load_prices,
                plot_data_description,
                plot_price_volume,
                plot_return_distribution,
                run,
            )
            """
        ),
        md(
            """
            ## Steps

            ### 1. 找到输入数据

            Task2 不需要联网，直接使用 `data/` 中的 CSV。
            """
        ),
        code(
            """
            csv_files = sorted(DATA_DIR.glob("*.csv"))
            pd.DataFrame({"file": [p.name for p in csv_files], "size_bytes": [p.stat().st_size for p in csv_files]})
            """
        ),
        md(
            """
            ### 2. 数据诊断

            先检查缺失值和基本统计量。真实分析里，这一步比直接画图更重要。
            """
        ),
        code(
            """
            frames = {p.stem.replace("行情数据", ""): load_prices(p) for p in csv_files}
            missing = pd.DataFrame(
                [{"stock": name, "missing_total": int(frame.isna().sum().sum()), "rows": len(frame)} for name, frame in frames.items()]
            )
            missing
            """
        ),
        code(
            """
            sample_name = next(iter(frames))
            frames[sample_name][["open", "high", "low", "close", "pct_chg", "vol"]].describe()
            """
        ),
        md(
            """
            ### 3. 绘制整体数据画像

            这里放三类图：缺失和主要特征分布、价格与成交量概览、日收益率分布。它们用于在技术指标之前先理解数据本身。
            """
        ),
        code(
            """
            frame_items = [{"name": name, "data": frame} for name, frame in frames.items()]
            missing_detail = pd.concat([diagnostics(name, frame)[0] for name, frame in frames.items()], ignore_index=True)
            overview_paths = [
                OUTPUT_DIR / "data_description_overview.png",
                OUTPUT_DIR / "price_volume_overview.png",
                OUTPUT_DIR / "daily_return_distribution.png",
            ]

            plot_data_description(frame_items, missing_detail, overview_paths[0])
            plot_price_volume(frame_items, overview_paths[1])
            plot_return_distribution(frame_items, overview_paths[2])

            for path in overview_paths:
                display(Image(filename=str(path)))
            """
        ),
        md(
            """
            ### 4. 指标公式的最小理解

            - RSI 衡量上涨和下跌动量的相对强弱。
            - MACD 比较短期 EMA 和长期 EMA 的差。
            - 布林带用均线和滚动标准差描述价格波动区间。
            - ATR 衡量真实波动幅度，不判断方向。
            """
        ),
        code(
            """
            sample = add_indicators(frames[sample_name])
            sample[["trade_date", "close", "rsi_14", "macd", "macd_signal", "bb_upper_20", "bb_lower_20", "atr_14"]].tail()
            """
        ),
        md(
            """
            ### 5. 用几行代码画一个核心图

            完整图表在 `calculate_indicators.py` 中生成。这里展示“收盘价 + 布林带”的核心。
            """
        ),
        code(
            """
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(sample["trade_date"], sample["close"], label="收盘价")
            ax.plot(sample["trade_date"], sample["bb_middle_20"], label="布林带中轨")
            ax.fill_between(sample["trade_date"], sample["bb_lower_20"], sample["bb_upper_20"], alpha=0.18)
            ax.set_title(f"{sample_name} 收盘价与布林带")
            ax.grid(True, alpha=0.25)
            ax.legend()
            fig.tight_layout()
            plt.show()
            """
        ),
        md(
            """
            ### 6. 一键生成交付文件

            `run()` 负责指标和图表，`build_site()` 负责网页。
            """
        ),
        code(
            """
            result = run()
            html_path = build_site()
            html_path, result["chart_paths"]
            """
        ),
        md(
            """
            ## Checks

            确认网页、指标 CSV 和图表都已经生成。
            """
        ),
        code(
            """
            assert html_path.exists()
            for path in result["indicator_paths"] + result["chart_paths"] + result["overview_chart_paths"]:
                assert path.exists() and path.stat().st_size > 0
            "Task2 walkthrough checks passed"
            """
        ),
        md(
            """
            ## Next Steps

            - 想换指标时，优先改 `calculate_indicators.py`。
            - 想改页面样式时，只改 `build_site.py`。
            - 想扩展更多股票时，把同字段 CSV 放进 `data/` 后重新运行 `run_all.py`。
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
