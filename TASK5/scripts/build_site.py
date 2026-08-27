from __future__ import annotations

import base64
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    FIGURE_DIR,
    MODEL_NAMES_ZH,
    MODEL_ORDER,
    OUTPUT_DIR,
    PROJECT_DIR,
    TITLE,
    WEB_DIR,
    ensure_directories,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from workshop_web_theme import restyle_portable_report


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    clean = frame.copy()
    clean = clean.replace([np.inf, -np.inf], np.nan)
    clean = clean.astype(object).where(pd.notna(clean), None)
    return clean.to_dict(orient="records")


def image_figure_block(image_path: Path, alt_text: str, caption: str) -> str:
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return (
        '<figure style="margin:0">'
        f'<img src="data:image/png;base64,{encoded}" alt="{alt_text}" '
        'style="display:block;width:100%;height:auto;border-radius:10px">'
        f'<figcaption style="margin-top:10px;color:#5d6670;line-height:1.6">{caption}</figcaption>'
        "</figure>"
    )


def find_node() -> Path:
    bundled = (
        Path.home()
        / ".cache"
        / "codex-runtimes"
        / "codex-primary-runtime"
        / "dependencies"
        / "node"
        / "bin"
        / "node.exe"
    )
    if bundled.exists():
        return bundled
    system_node = shutil.which("node")
    if system_node:
        return Path(system_node)
    raise FileNotFoundError("未找到 Node.js，无法运行离线报告打包器。")


def find_delivery_script() -> Path:
    root = (
        Path.home()
        / ".codex"
        / "plugins"
        / "cache"
        / "openai-curated-remote"
        / "data-analytics"
    )
    candidates = sorted(
        root.glob("*/skills/build-report/scripts/deliver_portable_artifact.mjs"),
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError("未找到 Data Analytics 离线报告打包器。")
    return candidates[0]


def main() -> int:
    ensure_directories()
    required = [
        OUTPUT_DIR / "metrics.csv",
        OUTPUT_DIR / "split_summary.csv",
        OUTPUT_DIR / "roc_curve_points.csv",
        OUTPUT_DIR / "data_quality.json",
        *[
            FIGURE_DIR / filename
            for filename in (
                "figure_1_class_distribution.png",
                "figure_2_logistic_regression_confusion_matrix.png",
                "figure_3_decision_tree_confusion_matrix.png",
                "figure_4_random_forest_confusion_matrix.png",
                "figure_5_roc_curves.png",
            )
        ],
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("请先运行 train_and_evaluate.py，缺少：" + ", ".join(str(path) for path in missing))

    metrics = pd.read_csv(OUTPUT_DIR / "metrics.csv")
    split_summary = pd.read_csv(OUTPUT_DIR / "split_summary.csv")
    roc = pd.read_csv(OUTPUT_DIR / "roc_curve_points.csv")
    quality = json.loads((OUTPUT_DIR / "data_quality.json").read_text(encoding="utf-8"))

    metrics["model_order"] = metrics["model"].map({key: index for index, key in enumerate(MODEL_ORDER, start=1)})
    metrics = metrics.sort_values("model_order")
    best = metrics.sort_values(["roc_auc", "recall", "f1"], ascending=False).iloc[0]
    logistic = metrics.loc[metrics["model"] == "logistic_regression"].iloc[0]
    tree = metrics.loc[metrics["model"] == "decision_tree"].iloc[0]
    forest = metrics.loc[metrics["model"] == "random_forest"].iloc[0]

    headline = [
        {
            "best_auc": float(best["roc_auc"]),
            "best_model": str(best["model_zh"]),
            "logistic_auc": float(logistic["roc_auc"]),
            "forest_auc": float(forest["roc_auc"]),
            "tree_auc": float(tree["roc_auc"]),
            "test_samples": int(quality["test_samples"]),
        }
    ]
    metric_rows = metrics[
        [
            "model",
            "model_zh",
            "accuracy",
            "precision",
            "recall",
            "specificity",
            "f1",
            "roc_auc",
            "auc_ci_low",
            "auc_ci_high",
            "tn",
            "fp",
            "fn",
            "tp",
            "train_accuracy",
            "train_roc_auc",
        ]
    ].copy()
    metric_rows["auc_95_ci"] = metric_rows.apply(
        lambda row: f"[{row['auc_ci_low']:.3f}, {row['auc_ci_high']:.3f}]", axis=1
    )
    metric_rows["sample_size"] = int(quality["test_samples"])
    metric_rows["positive_class"] = "恶性=1"

    roc_rows = roc[["model", "model_zh", "fpr", "tpr", "threshold"]].copy()
    roc_rows["sample_size"] = int(quality["test_samples"])
    roc_rows["positive_count"] = int(split_summary.loc[(split_summary["split"] == "测试集") & (split_summary["class_value"] == 1), "count"].iloc[0])
    baseline = pd.DataFrame(
        [
            {"model": "random_baseline", "model_zh": "随机基准", "fpr": 0.0, "tpr": 0.0, "threshold": None, "sample_size": int(quality["test_samples"]), "positive_count": 42},
            {"model": "random_baseline", "model_zh": "随机基准", "fpr": 1.0, "tpr": 1.0, "threshold": None, "sample_size": int(quality["test_samples"]), "positive_count": 42},
        ]
    )
    roc_rows = pd.concat([roc_rows, baseline], ignore_index=True)

    split_rows = split_summary.copy()
    split_rows["total_in_split"] = split_rows.groupby("split")["count"].transform("sum")
    split_rows["positive_class"] = "恶性=1"

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    headline_frame = pd.DataFrame(headline)
    quality_frame = pd.DataFrame([quality])
    sql_queries = {
        "headline_query": "SELECT best_auc, best_model, logistic_auc, forest_auc, tree_auc, test_samples FROM headline",
        "metrics_query": (
            "SELECT model, model_zh, accuracy, precision, recall, specificity, f1, roc_auc, "
            "auc_ci_low, auc_ci_high, tn, fp, fn, tp, train_accuracy, train_roc_auc, "
            "auc_95_ci, sample_size, positive_class FROM metrics ORDER BY roc_auc DESC"
        ),
        "split_query": (
            "SELECT split, class_value, class_name, count, proportion, total_in_split, positive_class "
            "FROM split_summary ORDER BY split, class_value"
        ),
        "roc_query": (
            "SELECT model, model_zh, fpr, tpr, threshold, sample_size, positive_count "
            "FROM roc_points ORDER BY model_zh, fpr, tpr"
        ),
        "quality_query": (
            "SELECT dataset_name, samples, features, missing_values, duplicate_feature_rows, "
            "positive_class, negative_class, train_samples, test_samples, test_size, random_state "
            "FROM data_quality"
        ),
    }
    connection = sqlite3.connect(":memory:")
    try:
        headline_frame.to_sql("headline", connection, index=False, if_exists="replace")
        metric_rows.to_sql("metrics", connection, index=False, if_exists="replace")
        split_rows.to_sql("split_summary", connection, index=False, if_exists="replace")
        roc_rows.to_sql("roc_points", connection, index=False, if_exists="replace")
        quality_frame.to_sql("data_quality", connection, index=False, if_exists="replace")
        queried_datasets = {
            "headline": pd.read_sql_query(sql_queries["headline_query"], connection),
            "metrics": pd.read_sql_query(sql_queries["metrics_query"], connection),
            "split_summary": pd.read_sql_query(sql_queries["split_query"], connection),
            "roc_points": pd.read_sql_query(sql_queries["roc_query"], connection),
            "data_quality": pd.read_sql_query(sql_queries["quality_query"], connection),
        }
    finally:
        connection.close()

    query_labels = {
        "headline_query": "TASK5 核心指标查询",
        "metrics_query": "TASK5 模型评价结果查询",
        "split_query": "TASK5 数据划分类别查询",
        "roc_query": "TASK5 ROC 曲线点查询",
        "quality_query": "TASK5 数据质量摘要查询",
    }
    query_tables = {
        "headline_query": ["headline"],
        "metrics_query": ["metrics"],
        "split_query": ["split_summary"],
        "roc_query": ["roc_points"],
        "quality_query": ["data_quality"],
    }
    source_entries = [
        {"id": source_key, "label": query_labels[source_key], "path": "web/source_queries.sql"}
        for source_key in sql_queries
    ]
    source_details = []
    for source_key, sql_text in sql_queries.items():
        query = {
            "engine": "sqlite",
            "language": "sql",
            "sql": sql_text,
            "description": f"从 Python 模型流程导出的内存 SQLite 表读取{query_labels[source_key]}。",
            "tables_used": query_tables[source_key],
            "filters": ["正类：恶性=1", "测试集比例：20%", "random_state=42"],
            "executed_at": generated_at,
        }
        if source_key in {"headline_query", "metrics_query"}:
            query["metric_definitions"] = {
                "accuracy": "(TP+TN)/(TP+TN+FP+FN)",
                "precision": "TP/(TP+FP)",
                "recall": "TP/(TP+FN)",
                "specificity": "TN/(TN+FP)",
                "f1": "2×Precision×Recall/(Precision+Recall)",
                "roc_auc": "基于测试集恶性正类预测概率计算的 ROC 曲线下面积",
            }
        source_details.append(
            {
                "id": source_key,
                "label": query_labels[source_key],
                "path": "web/source_queries.sql",
                "query": query,
            }
        )
    query_file = WEB_DIR / "source_queries.sql"
    query_file.write_text(
        "\n\n".join(f"-- {query_labels[key]}\n{sql};" for key, sql in sql_queries.items()) + "\n",
        encoding="utf-8",
    )

    figures = {
        1: (
            FIGURE_DIR / "figure_1_class_distribution.png",
            "训练集与测试集类别分布柱状图",
            "图 1 训练集与测试集类别分布。分层划分后两部分的良性与恶性比例基本一致。",
        ),
        2: (
            FIGURE_DIR / "figure_2_logistic_regression_confusion_matrix.png",
            "逻辑回归测试集混淆矩阵",
            "图 2 逻辑回归测试集混淆矩阵。TN=71、FP=1、FN=2、TP=40。",
        ),
        3: (
            FIGURE_DIR / "figure_3_decision_tree_confusion_matrix.png",
            "决策树测试集混淆矩阵",
            "图 3 决策树测试集混淆矩阵。TN=68、FP=4、FN=6、TP=36。",
        ),
        4: (
            FIGURE_DIR / "figure_4_random_forest_confusion_matrix.png",
            "随机森林测试集混淆矩阵",
            "图 4 随机森林测试集混淆矩阵。TN=72、FP=0、FN=3、TP=39。",
        ),
        5: (
            FIGURE_DIR / "figure_5_roc_curves.png",
            "三种分类模型 ROC 曲线",
            "图 5 三种分类模型 ROC 曲线。逻辑回归和随机森林接近左上角，明显优于单棵决策树。",
        ),
    }

    artifact = {
        "surface": "report",
        "manifest": {
            "version": 1,
            "surface": "report",
            "title": TITLE,
            "description": "乳腺癌二分类教学实验：算法原理、评价指标、三模型训练、混淆矩阵与 ROC/AUC。",
            "generatedAt": generated_at,
            "cards": [
                {
                    "id": "best_auc",
                    "description": "三个模型中测试集 ROC-AUC 最高的结果。",
                    "dataset": "headline",
                    "sourceId": "headline_query",
                    "metrics": [
                        {"label": "最高测试集 AUC", "field": "best_auc", "format": "number"},
                    ],
                },
                {
                    "id": "logistic_auc",
                    "description": "逻辑回归测试集排序区分能力。",
                    "dataset": "headline",
                    "sourceId": "headline_query",
                    "metrics": [{"label": "逻辑回归 AUC", "field": "logistic_auc", "format": "number"}],
                },
                {
                    "id": "forest_auc",
                    "description": "随机森林测试集排序区分能力。",
                    "dataset": "headline",
                    "sourceId": "headline_query",
                    "metrics": [{"label": "随机森林 AUC", "field": "forest_auc", "format": "number"}],
                },
                {
                    "id": "test_samples",
                    "description": "最终评价阶段未参与模型训练的样本数量。",
                    "dataset": "headline",
                    "sourceId": "headline_query",
                    "metrics": [{"label": "测试集样本", "field": "test_samples", "format": "number"}],
                },
            ],
            "charts": [
                {
                    "id": "auc_comparison",
                    "title": "三种模型测试集 ROC-AUC",
                    "subtitle": "测试集 n=114；恶性为正类；数值越接近 1，区分能力越强。",
                    "type": "bar",
                    "dataset": "metrics",
                    "sourceId": "metrics_query",
                    "encodings": {
                        "x": {"field": "model_zh", "type": "nominal", "label": "模型"},
                        "y": {"field": "roc_auc", "type": "quantitative", "label": "ROC-AUC", "format": "number"},
                        "tooltip": [
                            {"field": "recall", "type": "quantitative", "label": "召回率", "format": "percent"},
                            {"field": "sample_size", "type": "quantitative", "label": "测试样本"},
                        ],
                    },
                    "valueFormat": "number",
                    "layout": "full",
                },
                {
                    "id": "class_distribution",
                    "title": "训练集与测试集类别分布",
                    "subtitle": "80%/20% 分层划分；良性=0，恶性=1。",
                    "type": "bar",
                    "dataset": "split_summary",
                    "sourceId": "split_query",
                    "encodings": {
                        "x": {"field": "class_name", "type": "nominal", "label": "类别"},
                        "y": {"field": "count", "type": "quantitative", "label": "样本数"},
                        "color": {"field": "split", "type": "nominal", "label": "数据划分"},
                        "tooltip": [
                            {"field": "proportion", "type": "quantitative", "label": "组内占比", "format": "percent"},
                            {"field": "total_in_split", "type": "quantitative", "label": "划分总样本"},
                        ],
                    },
                    "layout": "full",
                },
                {
                    "id": "roc_curves",
                    "title": "三种分类模型 ROC 曲线",
                    "subtitle": "横轴 FPR，纵轴 TPR；随机基准为对角线。",
                    "type": "line",
                    "dataset": "roc_points",
                    "sourceId": "roc_query",
                    "encodings": {
                        "x": {"field": "fpr", "type": "quantitative", "label": "假正率 FPR"},
                        "y": {"field": "tpr", "type": "quantitative", "label": "真正率 TPR"},
                        "color": {"field": "model_zh", "type": "nominal", "label": "模型"},
                        "tooltip": [
                            {"field": "threshold", "type": "quantitative", "label": "分类阈值"},
                            {"field": "positive_count", "type": "quantitative", "label": "测试集正类数"},
                        ],
                    },
                    "layout": "full",
                },
            ],
            "tables": [
                {
                    "id": "model_metrics",
                    "title": "三种分类模型测试集评价结果",
                    "subtitle": "恶性为正类；阈值为模型默认 0.5；AUC 使用正类概率。",
                    "dataset": "metrics",
                    "sourceId": "metrics_query",
                    "defaultSort": {"field": "roc_auc", "direction": "desc"},
                    "columns": [
                        {"field": "model_zh", "label": "模型", "type": "text"},
                        {"field": "accuracy", "label": "Accuracy", "format": "percent"},
                        {"field": "precision", "label": "Precision", "format": "percent"},
                        {"field": "recall", "label": "Recall", "format": "percent"},
                        {"field": "specificity", "label": "Specificity", "format": "percent"},
                        {"field": "f1", "label": "F1", "format": "percent"},
                        {"field": "roc_auc", "label": "AUC", "format": "number"},
                        {"field": "auc_95_ci", "label": "AUC 95%区间", "type": "text"},
                    ],
                    "layout": "full",
                }
            ],
            "sources": source_entries,
            "blocks": [
                {"id": "title", "type": "markdown", "body": f"# {TITLE}"},
                {
                    "id": "technical_summary",
                    "type": "markdown",
                    "body": (
                        "## 技术摘要\n\n"
                        f"本实验在 **{quality['samples']}** 条样本、**{quality['features']}** 个数值特征上比较三种二分类模型。"
                        f"测试集上，随机森林 AUC 为 **{forest['roc_auc']:.4f}**，逻辑回归为 **{logistic['roc_auc']:.4f}**，"
                        f"决策树为 **{tree['roc_auc']:.4f}**。逻辑回归与随机森林的排序能力非常接近，"
                        "而单棵决策树的区分能力和召回率明显较低。由于测试集仅 114 条，结果应视为教学性留出集证据。"
                    ),
                },
                {"id": "headline_metrics", "type": "metric-strip", "cardIds": ["best_auc", "logistic_auc", "forest_auc", "test_samples"]},
                {
                    "id": "key_findings",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": (
                        "## 逻辑回归与随机森林表现领先\n\n"
                        f"两者准确率均为 **{logistic['accuracy']:.2%}**。逻辑回归识别出 42 个恶性样本中的 40 个，"
                        f"召回率为 **{logistic['recall']:.2%}**；随机森林没有产生假正例，但漏掉 3 个恶性样本。"
                        "因此，如果漏判风险更重要，不能只按最高 AUC 机械选择模型。"
                    ),
                },
                {"id": "auc_chart", "type": "chart", "chartId": "auc_comparison", "layout": "full"},
                {
                    "id": "auc_interpretation",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": (
                        "**如何解读：** AUC 衡量跨阈值的排序区分能力，不等同于固定 0.5 阈值下的准确率。"
                        f"随机森林的 AUC 95% bootstrap 区间为 **[{forest['auc_ci_low']:.3f}, {forest['auc_ci_high']:.3f}]**，"
                        f"逻辑回归为 **[{logistic['auc_ci_low']:.3f}, {logistic['auc_ci_high']:.3f}]**；区间高度重叠，"
                        "不足以证明随机森林在总体上必然优于逻辑回归。"
                    ),
                },
                {"id": "metrics_table", "type": "table", "tableId": "model_metrics", "layout": "full"},
                {
                    "id": "scope",
                    "type": "markdown",
                    "sourceId": "quality_query",
                    "body": (
                        "## 数据范围与标签定义\n\n"
                        "数据来自 `sklearn.datasets.load_breast_cancer`。scikit-learn 原始标签为恶性=0、良性=1；"
                        "本项目重编码为 **恶性=1、良性=0**，使正类代表风险事件。数据无缺失值，"
                        f"训练集 {quality['train_samples']} 条、测试集 {quality['test_samples']} 条，采用分层抽样保持类别比例。"
                    ),
                },
                {"id": "class_chart", "type": "chart", "chartId": "class_distribution", "layout": "full"},
                {"id": "figure_1", "type": "html", "body": image_figure_block(*figures[1])},
                {
                    "id": "class_interpretation",
                    "type": "markdown",
                    "sourceId": "split_query",
                    "body": "**图 1 解读：** 训练集包含良性 285 条、恶性 170 条；测试集包含良性 72 条、恶性 42 条。两部分的恶性占比相差约 0.52 个百分点，说明分层划分达到预期。",
                },
                {
                    "id": "algorithm_theory",
                    "type": "markdown",
                    "body": (
                        "## 三种分类算法如何工作\n\n"
                        "### 逻辑回归\n"
                        "将特征线性组合通过 Sigmoid 函数映射为正类概率。它训练快、概率输出清晰、可解释性较强，但默认形成线性决策边界，并对特征尺度敏感。本实验把标准化放入管道，只在训练集拟合。\n\n"
                        "### 决策树\n"
                        "通过基尼不纯度递归选择切分特征和阈值，形成可读的 if-then 规则。它能拟合非线性和交互关系，也无需标准化，但容易对训练样本过拟合，因此本实验限制最大深度与叶节点最小样本数。\n\n"
                        "### 随机森林\n"
                        "对 bootstrap 样本训练多棵随机特征子集决策树，再平均概率或投票。它通常比单棵树稳定，能捕捉非线性，但模型体量和解释成本更高。"
                    ),
                },
                {
                    "id": "metric_theory",
                    "type": "markdown",
                    "body": (
                        "## 混淆矩阵、ROC 与 AUC\n\n"
                        "混淆矩阵由 TN、FP、FN、TP 构成。Accuracy 反映总体正确率；Precision 关注预测为恶性的样本中有多少确为恶性；Recall 关注真实恶性被识别出的比例；Specificity 衡量良性被正确排除的比例；F1 综合 Precision 与 Recall。\n\n"
                        "ROC 曲线在不同分类阈值下，以 FPR=FP/(FP+TN) 为横轴、TPR=TP/(TP+FN) 为纵轴。AUC 是 ROC 曲线下面积，可理解为随机抽取一个正类和一个负类时，模型把正类概率排在负类之前的概率。AUC 只衡量排序能力，不能代替阈值选择或成本收益分析。"
                    ),
                },
                {
                    "id": "confusion_heading",
                    "type": "markdown",
                    "body": "## 固定阈值下的误判结构\n\n以下混淆矩阵统一规定横轴为预测类别、纵轴为真实类别，恶性为正类。每幅图后给出实际决策含义。",
                },
                {"id": "figure_2", "type": "html", "body": image_figure_block(*figures[2])},
                {
                    "id": "figure_2_note",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": "**图 2 解读：** 逻辑回归只有 1 个假正例和 2 个假负例，兼顾了较高召回率与特异度，是固定阈值下最均衡的模型。",
                },
                {"id": "figure_3", "type": "html", "body": image_figure_block(*figures[3])},
                {
                    "id": "figure_3_note",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": "**图 3 解读：** 决策树产生 4 个假正例和 6 个假负例，召回率只有 85.71%。其规则虽易解释，但单棵树对有限样本的划分更不稳定。",
                },
                {"id": "figure_4", "type": "html", "body": image_figure_block(*figures[4])},
                {
                    "id": "figure_4_note",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": "**图 4 解读：** 随机森林没有把良性样本误判为恶性，但漏判 3 个恶性样本。若业务更重视避免漏判，可以下调概率阈值，而不应仅保留默认 0.5。",
                },
                {
                    "id": "roc_heading",
                    "type": "markdown",
                    "body": "## 跨阈值比较确认集成模型优势\n\nROC 曲线把所有可能阈值下的真正率与假正率放在一起比较，避免结论被单一阈值绑定。",
                },
                {"id": "roc_chart", "type": "chart", "chartId": "roc_curves", "layout": "full"},
                {"id": "figure_5", "type": "html", "body": image_figure_block(*figures[5])},
                {
                    "id": "roc_note",
                    "type": "markdown",
                    "sourceId": "metrics_query",
                    "body": f"**图 5 解读：** 随机森林和逻辑回归曲线几乎贴近左上角，AUC 分别为 {forest['roc_auc']:.3f} 和 {logistic['roc_auc']:.3f}；决策树曲线明显更靠近对角基准，AUC 为 {tree['roc_auc']:.3f}。",
                },
                {
                    "id": "methodology",
                    "type": "markdown",
                    "body": (
                        "## 模型设定与防泄漏措施\n\n"
                        "1. 使用 `train_test_split(test_size=0.20, stratify=y, random_state=42)` 固定划分。\n"
                        "2. 逻辑回归采用 `StandardScaler` 与分类器组成的 Pipeline，标准化参数只从训练集学习。\n"
                        "3. 决策树使用 `max_depth=4`、`min_samples_leaf=5` 和平衡类别权重。\n"
                        "4. 随机森林使用 500 棵树、`min_samples_leaf=2` 和平衡类别权重。\n"
                        "5. 测试集不参与参数拟合；AUC 使用 `predict_proba` 输出的恶性概率；95% 区间由测试集 2,000 次 bootstrap 得到。"
                    ),
                },
                {
                    "id": "limitations",
                    "type": "markdown",
                    "body": (
                        "## 局限性与稳健性边界\n\n"
                        "- 本实验只有一次固定留出集，测试集样本较少；bootstrap 区间只能描述该测试集上的抽样不确定性。\n"
                        "- 乳腺癌数据是独立同分布的标准分类样例，不包含金融时间序列常见的制度变化、非平稳性、交易成本和标签重叠。\n"
                        "- 训练 AUC 与测试 AUC 的差距在决策树上最大，提示其更容易过拟合；逻辑回归与随机森林的差距较小。\n"
                        "- 结果仅用于演示分类方法，不构成医学诊断或投资建议。"
                    ),
                },
                {
                    "id": "next_steps",
                    "type": "markdown",
                    "body": (
                        "## 迁移到量化交易的下一步\n\n"
                        "- 把应变量改为未来持有期收益是否大于 0、是否跑赢基准或是否进入收益率前分位。\n"
                        "- 以财务质量、估值、动量、波动率和流动性作为特征，但所有特征必须按当时可获得时间对齐。\n"
                        "- 使用按时间先后划分、滚动窗口或扩展窗口验证，严禁随机打乱未来和过去。\n"
                        "- 根据手续费、滑点、换手率和错失机会设定分类阈值，并用回测收益、最大回撤等指标补充 AUC。"
                    ),
                },
                {
                    "id": "further_questions",
                    "type": "markdown",
                    "body": (
                        "## 后续可研究的问题\n\n"
                        "1. 下调恶性预测阈值后，三种模型的召回率与假正率如何变化？\n"
                        "2. 使用分层交叉验证选择树深后，决策树的测试 AUC 能否稳定改善？\n"
                        "3. 迁移到股票收益标签时，模型排序能力能否在不同时期、行业和市场状态下保持？"
                    ),
                },
            ],
        },
        "snapshot": {
            "version": 1,
            "generatedAt": generated_at,
            "status": "ready",
            "datasets": {key: dataframe_records(value) for key, value in queried_datasets.items()},
        },
        "sources": source_details,
    }

    artifact_path = WEB_DIR / "artifact.json"
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    node = find_node()
    delivery_script = find_delivery_script()
    output_path = WEB_DIR / "index.html"
    result = subprocess.run(
        [str(node), str(delivery_script), "--input", str(artifact_path), "--output", str(output_path)],
        cwd=PROJECT_DIR,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        return result.returncode
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("离线 HTML 打包器未生成有效的 index.html。")
    restyle_portable_report(
        output_path,
        current_task=5,
        hero_title="AI 交易引擎：机器学习<br>算法与场景应用",
        hero_subtitle=(
            "用逻辑回归、决策树与随机森林完成二分类教学实验，"
            "从混淆矩阵、ROC 与 AUC 理解模型选择和风险取舍。"
        ),
        metrics=(
            ("数据样本", f"{quality['samples']} 条"),
            ("数值特征", f"{quality['features']} 个"),
            ("最高测试集 AUC", f"{best['roc_auc']:.3f}"),
            ("最佳模型", str(best["model_zh"])),
        ),
        footer_text=(
            "数据：scikit-learn Wisconsin 乳腺癌诊断数据集｜"
            "模型：逻辑回归 / 决策树 / 随机森林｜仅用于课程研究演示"
        ),
    )
    stdout_lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    receipt = {
        "status": "unknown",
        "note": "打包器未返回可解析的 JSON 回执。",
        "raw_stdout": result.stdout,
    }
    for line in stdout_lines:
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            receipt = candidate
            break
    (WEB_DIR / "delivery_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"HTML 成果页已生成：{output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
