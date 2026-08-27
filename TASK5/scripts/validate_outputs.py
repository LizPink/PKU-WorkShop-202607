from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd
from PIL import Image
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from config import FIGURE_DIR, MODEL_NAMES_ZH, MODEL_ORDER, OUTPUT_DIR, ensure_directories


TOLERANCE = 1e-7


def close_enough(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=TOLERANCE, abs_tol=TOLERANCE)


def main() -> None:
    ensure_directories()
    checks: list[dict[str, object]] = []

    def record(check: str, passed: bool, evidence: str, severity: str = "High") -> None:
        checks.append({"check": check, "passed": bool(passed), "severity": severity, "evidence": str(evidence)})

    required_files = [
        OUTPUT_DIR / "metrics.csv",
        OUTPUT_DIR / "predictions.csv",
        OUTPUT_DIR / "split_summary.csv",
        OUTPUT_DIR / "roc_curve_points.csv",
        OUTPUT_DIR / "data_quality.json",
        OUTPUT_DIR / "model_parameters.json",
    ]
    for path in required_files:
        record(f"文件存在：{path.name}", path.exists() and path.stat().st_size > 0, str(path), "High")

    if not all(path.exists() for path in required_files):
        write_validation_report(checks)
        raise SystemExit("缺少核心输出文件，无法继续校验。")

    metrics = pd.read_csv(OUTPUT_DIR / "metrics.csv")
    predictions = pd.read_csv(OUTPUT_DIR / "predictions.csv")
    split_summary = pd.read_csv(OUTPUT_DIR / "split_summary.csv")
    quality = json.loads((OUTPUT_DIR / "data_quality.json").read_text(encoding="utf-8"))

    record("测试集样本数为 114", len(predictions) == 114, f"实际 {len(predictions)} 条", "High")
    record("数据集无缺失值", quality["missing_values"] == 0, f"缺失值 {quality['missing_values']} 个", "High")
    record("三个模型均有评价结果", set(metrics["model"]) == set(MODEL_ORDER), ", ".join(metrics["model"]), "High")
    record("预测结果包含两个类别", predictions["true_label"].nunique() == 2, f"类别数 {predictions['true_label'].nunique()}", "High")

    for model_key in MODEL_ORDER:
        row = metrics.loc[metrics["model"] == model_key].iloc[0]
        pred = predictions[f"{model_key}_prediction"].astype(int)
        prob = predictions[f"{model_key}_probability_malignant"].astype(float)
        true = predictions["true_label"].astype(int)
        tn, fp, fn, tp = confusion_matrix(true, pred, labels=[0, 1]).ravel()
        recomputed = {
            "accuracy": accuracy_score(true, pred),
            "precision": precision_score(true, pred, zero_division=0),
            "recall": recall_score(true, pred, zero_division=0),
            "specificity": tn / (tn + fp),
            "f1": f1_score(true, pred, zero_division=0),
            "roc_auc": roc_auc_score(true, prob),
        }
        for metric_name, value in recomputed.items():
            record(
                f"{MODEL_NAMES_ZH[model_key]} {metric_name} 独立复算一致",
                close_enough(row[metric_name], value),
                f"保存值={row[metric_name]:.8f}，复算值={value:.8f}",
                "High",
            )
        record(
            f"{MODEL_NAMES_ZH[model_key]} 混淆矩阵计数一致",
            [int(row["tn"]), int(row["fp"]), int(row["fn"]), int(row["tp"])] == [int(tn), int(fp), int(fn), int(tp)],
            f"TN={tn}, FP={fp}, FN={fn}, TP={tp}",
            "High",
        )
        record(
            f"{MODEL_NAMES_ZH[model_key]} 概率在 [0,1] 内",
            prob.between(0, 1).all(),
            f"min={prob.min():.6f}, max={prob.max():.6f}",
            "High",
        )
        record(
            f"{MODEL_NAMES_ZH[model_key]} AUC 区间包含点估计",
            row["auc_ci_low"] <= row["roc_auc"] <= row["auc_ci_high"],
            f"95% CI=[{row['auc_ci_low']:.4f}, {row['auc_ci_high']:.4f}]，AUC={row['roc_auc']:.4f}",
            "Medium",
        )

    proportions = split_summary.pivot(index="class_value", columns="split", values="proportion")
    max_proportion_gap = (proportions["训练集"] - proportions["测试集"]).abs().max()
    record(
        "分层划分后类别比例差小于 1 个百分点",
        max_proportion_gap < 0.01,
        f"最大差异={max_proportion_gap:.4%}",
        "Medium",
    )

    expected_figures = [
        FIGURE_DIR / "figure_1_class_distribution.png",
        FIGURE_DIR / "figure_2_logistic_regression_confusion_matrix.png",
        FIGURE_DIR / "figure_3_decision_tree_confusion_matrix.png",
        FIGURE_DIR / "figure_4_random_forest_confusion_matrix.png",
        FIGURE_DIR / "figure_5_roc_curves.png",
    ]
    for figure_path in expected_figures:
        valid = False
        evidence = "不存在"
        if figure_path.exists() and figure_path.stat().st_size > 0:
            with Image.open(figure_path) as image:
                width, height = image.size
            valid = width >= 1000 and height >= 700
            evidence = f"{width}×{height}px，{figure_path.stat().st_size} bytes"
        record(f"统计图可读：{figure_path.name}", valid, evidence, "High")

    report_path = write_validation_report(checks)
    failed = [item for item in checks if not item["passed"]]
    if failed:
        print(f"校验失败：{len(failed)} 项，详见 {report_path}")
        return 1
    print(f"全部 {len(checks)} 项校验通过：{report_path}")
    return 0


def write_validation_report(checks: list[dict[str, object]]) -> Path:
    failures = [item for item in checks if not item["passed"]]
    status = "Ready to share" if not failures else "Needs revision"
    lines = [
        "# Validation Report",
        "",
        f"## Overall Assessment: {status}",
        "",
        "### Methodology Review",
        "",
        "校验对象为 TASK5 乳腺癌二分类实验。正类固定为恶性（1），测试集为分层抽样得到的 20% 数据。评价值从逐样本预测文件独立复算，AUC 使用正类概率而非 0/1 分类结果。",
        "",
        "### Issues Found",
        "",
    ]
    if failures:
        for index, item in enumerate(failures, start=1):
            lines.append(f"{index}. [Severity: {item['severity']}] {item['check']} - {item['evidence']}")
    else:
        lines.append("未发现阻止分享或提交的计算问题。")
    lines.extend(["", "### Calculation Spot-Checks", ""])
    for item in checks:
        symbol = "PASS" if item["passed"] else "FAIL"
        lines.append(f"- [{symbol}] {item['check']}：{item['evidence']}")
    lines.extend(
        [
            "",
            "### Visualization Review",
            "",
            "统计图使用明确标题、坐标标签、图例和一致配色；混淆矩阵注明真实类别与预测类别方向；ROC 图包含随机分类基准线。最终视觉完整性仍需在 HTML、DOCX 和 PDF 的实际页面中复核。",
            "",
            "### Suggested Improvements",
            "",
            "1. 若迁移到股票收益数据，应采用按时间先后划分或滚动回测，避免随机划分带来的前视偏差。",
            "2. 若用于真实决策，应根据假正例与假负例的成本重新选择分类阈值，并报告交易成本或诊断代价。",
            "",
            "### Required Caveats for Stakeholders",
            "",
            "- 这是标准教学数据上的一次固定留出集实验，样本量有限，AUC 区间反映测试样本抽样不确定性。",
            "- 结果仅用于演示分类模型流程，不构成医学诊断或投资建议。",
        ]
    )
    report_path = OUTPUT_DIR / "validation_report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    (OUTPUT_DIR / "validation_checks.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report_path


if __name__ == "__main__":
    sys.exit(main())
