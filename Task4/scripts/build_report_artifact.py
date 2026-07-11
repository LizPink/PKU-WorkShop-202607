from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config import DEFAULT_PARAMS, parameter_label


TASK_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = TASK_DIR / "outputs"
WEB_DIR = TASK_DIR / "web"
ARTIFACT_PATH = WEB_DIR / "artifact.json"


def clean_number(value: float | int) -> float | int | None:
    if pd.isna(value) or not np.isfinite(float(value)):
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    return float(value)


def records(frame: pd.DataFrame) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in frame.to_dict(orient="records"):
        output.append(
            {
                str(key): clean_number(value) if isinstance(value, (int, float, np.integer, np.floating)) else value
                for key, value in row.items()
            }
        )
    return output


def build_artifact() -> Path:
    summary = pd.read_csv(OUTPUT_DIR / "parameter_comparison.csv")
    default_label = parameter_label(DEFAULT_PARAMS)
    default_full = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "full")].copy()
    default_oos = summary.loc[(summary["parameter"] == default_label) & (summary["sample_period"] == "out_of_sample")].copy()
    parameter_oos = (
        summary.loc[summary["sample_period"] == "out_of_sample"]
        .groupby("parameter", as_index=False)
        .agg(
            median_return=("cumulative_return", "median"),
            median_sharpe=("sharpe_ratio", "median"),
            median_mdd=("max_drawdown", "median"),
            positive_share=("cumulative_return", lambda values: float((values > 0).mean())),
            median_trades=("completed_trades", "median"),
        )
        .sort_values(["median_sharpe", "median_return"], ascending=False)
    )
    default_oos["mdd_magnitude"] = -default_oos["max_drawdown"]
    default_full = default_full.rename(columns={"cumulative_return": "strategy_return"})

    median_return = float(default_oos["cumulative_return"].median())
    median_sharpe = float(default_oos["sharpe_ratio"].median())
    median_mdd = float(default_oos["max_drawdown"].median())
    positive_count = int((default_oos["cumulative_return"] > 0).sum())
    best_stock = default_oos.sort_values("sharpe_ratio", ascending=False).iloc[0]
    best_parameter = parameter_oos.iloc[0]
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    sources = [
        {
            "id": "prices",
            "label": "A股前复权日线行情",
            "path": "Task3/data/*_daily_qfq.csv",
            "query": {
                "language": "python",
                "description": "读取10只股票的本地前复权日线OHLCV数据并按交易日排序去重。",
                "tables_used": ["Task3/data/*_daily_qfq.csv"],
                "filters": ["2019-01-02至2026-07-10", "10只人工选择的跨行业代表性股票"],
            },
        },
        {
            "id": "backtest_summary",
            "label": "海龟策略批量回测汇总",
            "path": "Task4/outputs/parameter_comparison.csv",
            "query": {
                "language": "sql",
                "engine": "DuckDB",
                "sql": "SELECT * FROM read_csv_auto('Task4/outputs/parameter_comparison.csv') WHERE sample_period IN ('full', 'out_of_sample');",
                "description": "使用前一日通道、Wilder ATR、次日开盘执行、1%风险定仓和0.1%单边成本计算绩效。",
                "tables_used": ["Task4/outputs/parameter_comparison.csv"],
                "filters": ["样本外从2024-01-01开始", "只做多", "不加杠杆", "不加仓"],
                "metric_definitions": [
                    "累计回报=(1+日策略收益)连乘-1",
                    "最大回撤=min(累计净值/历史最高净值-1)",
                    "夏普比率=日均收益/日收益标准差×sqrt(252)，无风险利率为0",
                    "ATR为真实波幅的Wilder递推平均",
                ],
            },
        },
    ]

    headline = [
        {
            "median_return": median_return,
            "median_sharpe": median_sharpe,
            "median_mdd": median_mdd,
            "positive_share": positive_count / len(default_oos),
            "positive_count": positive_count,
            "stock_count": int(len(default_oos)),
        }
    ]

    title = "Task4 海龟交易策略回测与参数研究"
    summary_markdown = (
        "## 技术摘要\n\n"
        f"- 默认参数 `{default_label}` 在样本外10只股票中有 **{positive_count}/10** 取得正累计回报；"
        f"中位累计回报为 **{median_return:.1%}**，中位夏普比率为 **{median_sharpe:.2f}**，"
        f"中位最大回撤为 **{median_mdd:.1%}**。\n"
        f"- 默认参数样本外夏普最高的是 **{best_stock['stock_name']}**，累计回报 **{best_stock['cumulative_return']:.1%}**、"
        f"最大回撤 **{best_stock['max_drawdown']:.1%}**。\n"
        f"- 跨股票中位夏普最高的参数为 **{best_parameter['parameter']}**。参数排序仅用于稳健性观察，不代表未来最优。"
    )

    manifest = {
        "version": 1,
        "surface": "report",
        "title": title,
        "description": "基于10只A股2019年至2026年日线数据的海龟策略教学回测、风险指标与参数敏感性研究。",
        "generatedAt": generated_at,
        "sources": sources,
        "cards": [
            {
                "id": "median-return",
                "dataset": "headline",
                "sourceId": "backtest_summary",
                "description": "默认参数在10只股票样本外累计回报的中位数。",
                "metrics": [{"label": "样本外中位累计回报", "field": "median_return", "format": "percent"}],
            },
            {
                "id": "median-sharpe",
                "dataset": "headline",
                "sourceId": "backtest_summary",
                "description": "默认参数样本外日收益按252日年化的中位夏普比率。",
                "metrics": [{"label": "样本外中位夏普", "field": "median_sharpe", "format": "number"}],
            },
            {
                "id": "median-mdd",
                "dataset": "headline",
                "sourceId": "backtest_summary",
                "description": "默认参数在10只股票样本外最大回撤的中位数。",
                "metrics": [{"label": "样本外中位最大回撤", "field": "median_mdd", "format": "percent"}],
            },
            {
                "id": "positive-share",
                "dataset": "headline",
                "sourceId": "backtest_summary",
                "description": "默认参数样本外累计回报大于零的股票占比。",
                "metrics": [{"label": "正收益股票占比", "field": "positive_share", "format": "percent"}],
            },
        ],
        "charts": [
            {
                "id": "default-returns",
                "title": "默认参数下各股票累计回报",
                "subtitle": "2019-01至2026-07；海龟策略与买入持有，单位为累计回报率",
                "showDescription": True,
                "intent": "comparison",
                "question": "默认海龟策略相对买入持有的跨股票表现如何？",
                "rationale": "横向分组柱形能够在股票名称较长的情况下直接比较同一标的的策略与基准累计回报。",
                "comparisonContext": {"baseline": "买入持有", "grain": "股票", "unit": "累计回报率"},
                "type": "horizontalBar",
                "dataset": "default_full",
                "sourceId": "backtest_summary",
                "encodings": {
                    "x": {"field": "stock_name", "type": "nominal", "label": "股票"},
                    "y": {"fields": ["strategy_return", "benchmark_return"], "type": "quantitative", "format": "percent", "label": "累计回报"},
                },
                "valueFormat": "percent",
                "palette": {"kind": "categorical"},
                "legend": {"position": "bottom", "sort": "spec", "title": "序列"},
                "layout": "full",
                "surface": {"surface": "card", "viewMode": "both"},
            },
            {
                "id": "parameter-sharpe",
                "title": "参数组合的样本外中位夏普比率",
                "subtitle": "2024-01至2026-07；每个参数汇总10只股票的中位数",
                "showDescription": True,
                "intent": "comparison",
                "question": "哪组参数在跨股票样本外比较中更稳健？",
                "rationale": "横向柱形适合按中位夏普排序六组参数，并保留较长的参数标签。",
                "comparisonContext": {"grain": "参数组合", "unit": "夏普比率", "normalization": "10只股票中位数"},
                "type": "horizontalBar",
                "dataset": "parameter_oos",
                "sourceId": "backtest_summary",
                "encodings": {
                    "x": {"field": "parameter", "type": "nominal", "label": "参数组合"},
                    "y": {"field": "median_sharpe", "type": "quantitative", "format": "number", "label": "中位夏普比率"},
                },
                "valueFormat": "number",
                "palette": {"kind": "sequential"},
                "layout": "full",
                "surface": {"surface": "card", "viewMode": "both"},
            },
            {
                "id": "risk-return",
                "title": "默认参数样本外风险—收益分布",
                "subtitle": "2024-01至2026-07；横轴为最大回撤幅度，纵轴为累计回报",
                "showDescription": True,
                "intent": "relationship",
                "question": "默认参数下哪些股票实现了更好的风险收益组合？",
                "rationale": "散点图能够同时显示每只股票的最大回撤幅度、累计回报、行业和身份标签。",
                "comparisonContext": {"grain": "股票", "unit": "回报率", "denominator": "各股票策略净值"},
                "type": "scatter",
                "dataset": "default_oos",
                "sourceId": "backtest_summary",
                "encodings": {
                    "x": {"field": "mdd_magnitude", "type": "quantitative", "format": "percent", "label": "最大回撤幅度"},
                    "y": {"field": "cumulative_return", "type": "quantitative", "format": "percent", "label": "累计回报"},
                    "color": {"field": "industry", "type": "nominal", "label": "行业"},
                    "label": {"field": "stock_name", "type": "text", "label": "股票"},
                    "tooltip": [
                        {"field": "stock_name", "type": "text", "label": "股票"},
                        {"field": "industry", "type": "text", "label": "行业"},
                        {"field": "sharpe_ratio", "type": "quantitative", "format": "number", "label": "夏普比率"},
                        {"field": "completed_trades", "type": "quantitative", "format": "number", "label": "完成交易"},
                    ],
                },
                "layout": "full",
                "surface": {"surface": "card", "viewMode": "both"},
            },
        ],
        "tables": [
            {
                "id": "default-oos-table",
                "title": "默认参数样本外绩效明细",
                "subtitle": "2024-01至2026-07；按夏普比率从高到低排序",
                "showDescription": True,
                "dataset": "default_oos",
                "sourceId": "backtest_summary",
                "defaultSort": {"field": "sharpe_ratio", "direction": "desc"},
                "density": "spacious",
                "layout": "full",
                "columns": [
                    {"field": "stock_name", "label": "股票", "type": "text"},
                    {"field": "industry", "label": "行业", "type": "text"},
                    {"field": "cumulative_return", "label": "累计回报", "format": "percent", "role": "movement"},
                    {"field": "benchmark_return", "label": "基准回报", "format": "percent", "role": "movement"},
                    {"field": "max_drawdown", "label": "最大回撤", "format": "percent", "role": "movement"},
                    {"field": "sharpe_ratio", "label": "夏普比率", "format": "number"},
                    {"field": "completed_trades", "label": "完成交易", "format": "number"},
                    {"field": "win_rate", "label": "胜率", "format": "percent"},
                ],
            }
        ],
        "blocks": [
            {"id": "title", "type": "markdown", "body": f"# {title}", "layout": "full"},
            {"id": "summary", "type": "markdown", "body": summary_markdown, "sourceId": "backtest_summary", "layout": "full"},
            {"id": "headline-metrics", "type": "metric-strip", "cardIds": ["median-return", "median-sharpe", "median-mdd", "positive-share"], "layout": "full"},
            {"id": "finding-default", "type": "markdown", "body": "## 默认参数在不同股票上的结果分化明显\n\n下图比较全样本海龟策略与买入持有。趋势策略并不保证跑赢单边上涨的股票，但在部分标的上能够通过风险定仓和退出规则限制回撤。应把策略收益、基准收益和回撤一起阅读。", "layout": "full"},
            {"id": "default-returns-block", "type": "chart", "chartId": "default-returns", "layout": "full"},
            {"id": "finding-parameters", "type": "markdown", "body": f"## 参数变化改变交易频率和趋势敏感度\n\n样本外跨股票中位夏普最高的是 `{best_parameter['parameter']}`。短通道响应快但容易受噪声影响；长通道减少交易，却可能错过趋势前段。参数比较的用途是寻找不过度失真的区域，而不是追逐单一最高值。", "sourceId": "backtest_summary", "layout": "full"},
            {"id": "parameter-sharpe-block", "type": "chart", "chartId": "parameter-sharpe", "layout": "full"},
            {"id": "finding-risk", "type": "markdown", "body": "## 风险与收益必须联合评估\n\n风险—收益图把累计回报与最大回撤放在同一坐标中；越靠左上方表示回撤较小且收益较高。点位分散说明海龟策略对个股趋势结构敏感，适合通过多标的分散，而不适合作为单只股票的确定性预测工具。", "layout": "full"},
            {"id": "risk-return-block", "type": "chart", "chartId": "risk-return", "layout": "full"},
            {"id": "definitions", "type": "markdown", "body": "## 数据、指标与模拟口径\n\n- **数据**：10只A股前复权日线，2019-01至2026-07。\n- **入场/离场**：突破前N日最高通道入场；跌破较短低点通道或触发初始ATR止损离场。普通通道信号下一交易日开盘执行。\n- **ATR与仓位**：真实波幅采用三项最大值，ATR使用Wilder递推；每笔计划风险为账户权益1%，资金占用不超过100%。\n- **绩效**：累计回报、年化收益/波动、MDD、夏普、胜率、交易次数和基准收益；样本外从2024-01-01开始。", "sourceId": "prices", "layout": "full"},
            {"id": "details-table", "type": "table", "tableId": "default-oos-table", "layout": "full"},
            {"id": "limitations", "type": "markdown", "body": "## 局限与稳健性检查\n\n股票池为人工选择的当前代表性股票，存在幸存者偏差；每个行业仅2只股票。模型未模拟100股整手、涨跌停无法成交、停牌、滑点和容量约束，允许教学用小数股。参数排名不能证明未来最优，结论应优先依据跨标的和样本外稳定性。", "layout": "full"},
            {"id": "next-steps", "type": "markdown", "body": "## 建议的下一步\n\n1. 扩大股票池并使用历史成分股，降低幸存者偏差。\n2. 加入滚动样本外检验和组合级风险预算。\n3. 模拟整手、涨跌停、滑点、停牌和成交量限制。\n4. 与双均线和买入持有在相同成本口径下比较。", "layout": "full"},
            {"id": "further-questions", "type": "markdown", "body": "## 进一步问题\n\n不同市场状态下最稳健的通道区间是否一致？加入组合分散和趋势过滤后，能否在不显著牺牲收益的情况下改善回撤？这些问题需要更大股票池和滚动样本外研究。", "layout": "full"},
        ],
    }

    snapshot = {
        "version": 1,
        "generatedAt": generated_at,
        "status": "ready",
        "datasets": {
            "headline": headline,
            "default_full": records(default_full[["ts_code", "stock_name", "industry", "strategy_return", "benchmark_return", "sharpe_ratio", "max_drawdown"]]),
            "default_oos": records(default_oos[["ts_code", "stock_name", "industry", "cumulative_return", "benchmark_return", "max_drawdown", "mdd_magnitude", "sharpe_ratio", "completed_trades", "win_rate", "average_exposure"]]),
            "parameter_oos": records(parameter_oos),
        },
    }

    artifact = {
        "surface": "report",
        "manifest": manifest,
        "snapshot": snapshot,
        "sources": sources,
    }
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return ARTIFACT_PATH


if __name__ == "__main__":
    print(build_artifact())
