from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from matplotlib import font_manager
from sklearn.datasets import load_breast_cancer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

from config import (
    BOOTSTRAP_RANDOM_STATE,
    BOOTSTRAP_SAMPLES,
    COLORS,
    DATA_DIR,
    FIGURE_DIR,
    MODEL_NAMES_ZH,
    MODEL_ORDER,
    OUTPUT_DIR,
    RANDOM_STATE,
    TEST_SIZE,
    TITLE,
    ensure_directories,
)


def configure_plot_style() -> None:
    simsun_path = Path(r"C:\Windows\Fonts\simsun.ttc")
    if simsun_path.exists():
        try:
            font_manager.fontManager.addfont(simsun_path)
        except RuntimeError:
            pass
    plt.rcParams.update(
        {
            "font.sans-serif": ["SimSun", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": COLORS["ink"],
            "axes.labelcolor": COLORS["ink"],
            "text.color": COLORS["ink"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "axes.titleweight": "bold",
            "axes.titlesize": 13,
            "axes.labelsize": 10.5,
            "legend.frameon": False,
        }
    )


def build_models() -> dict[str, object]:
    return {
        "logistic_regression": Pipeline(
            steps=[
                ("standard_scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        solver="liblinear",
                        max_iter=5000,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "decision_tree": DecisionTreeClassifier(
            criterion="gini",
            max_depth=4,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }


def bootstrap_auc_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    n_bootstrap: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_RANDOM_STATE,
) -> tuple[float, float, int]:
    rng = np.random.default_rng(seed)
    auc_values: list[float] = []
    sample_count = len(y_true)
    for _ in range(n_bootstrap):
        indices = rng.integers(0, sample_count, sample_count)
        sampled_y = y_true[indices]
        if np.unique(sampled_y).size < 2:
            continue
        auc_values.append(roc_auc_score(sampled_y, y_score[indices]))
    low, high = np.quantile(auc_values, [0.025, 0.975])
    return float(low), float(high), len(auc_values)


def save_figure(fig: plt.Figure, filename: str) -> None:
    fig.savefig(FIGURE_DIR / filename, dpi=240, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_class_distribution(split_summary: pd.DataFrame) -> None:
    pivot = split_summary.pivot(index="class_name", columns="split", values="count")
    pivot = pivot.reindex(["良性（0）", "恶性（1）"])[["训练集", "测试集"]]
    fig, ax = plt.subplots(figsize=(7.2, 4.7))
    x = np.arange(len(pivot.index))
    width = 0.34
    bars_train = ax.bar(
        x - width / 2,
        pivot["训练集"],
        width,
        color=COLORS["blue"],
        edgecolor=COLORS["ink"],
        linewidth=0.6,
        label="训练集",
    )
    bars_test = ax.bar(
        x + width / 2,
        pivot["测试集"],
        width,
        color=COLORS["gold"],
        edgecolor=COLORS["ink"],
        linewidth=0.6,
        label="测试集",
    )
    ax.bar_label(bars_train, padding=3, fontsize=9)
    ax.bar_label(bars_test, padding=3, fontsize=9)
    ax.set_xticks(x, pivot.index)
    ax.set_ylabel("样本数")
    ax.set_title("图 1 训练集与测试集类别分布")
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right")
    save_figure(fig, "figure_1_class_distribution.png")


def plot_confusion_matrix(model_key: str, cm: np.ndarray, figure_number: int) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 4.8))
    image = ax.imshow(cm, cmap="Blues", vmin=0, vmax=max(1, int(cm.max())))
    threshold = cm.max() / 2
    for row in range(2):
        for col in range(2):
            ax.text(
                col,
                row,
                str(int(cm[row, col])),
                ha="center",
                va="center",
                fontsize=18,
                fontweight="bold",
                color="white" if cm[row, col] > threshold else COLORS["ink"],
            )
    ax.set_xticks([0, 1], ["良性（0）", "恶性（1）"])
    ax.set_yticks([0, 1], ["良性（0）", "恶性（1）"])
    ax.set_xlabel("预测类别")
    ax.set_ylabel("真实类别")
    ax.set_title(f"图 {figure_number} {MODEL_NAMES_ZH[model_key]}测试集混淆矩阵")
    for spine in ax.spines.values():
        spine.set_visible(False)
    colorbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    colorbar.set_label("样本数")
    save_figure(fig, f"figure_{figure_number}_{model_key}_confusion_matrix.png")


def plot_roc_curves(roc_rows: pd.DataFrame, metrics: pd.DataFrame) -> None:
    palette = {
        "logistic_regression": COLORS["blue"],
        "decision_tree": COLORS["gold"],
        "random_forest": COLORS["pink"],
    }
    line_styles = {
        "logistic_regression": "-",
        "decision_tree": "--",
        "random_forest": "-.",
    }
    fig, ax = plt.subplots(figsize=(7.2, 5.5))
    metric_index = metrics.set_index("model")
    for model_key in MODEL_ORDER:
        subset = roc_rows.loc[roc_rows["model"] == model_key]
        auc_value = metric_index.loc[model_key, "roc_auc"]
        ax.plot(
            subset["fpr"],
            subset["tpr"],
            color=palette[model_key],
            linestyle=line_styles[model_key],
            linewidth=2.3,
            label=f"{MODEL_NAMES_ZH[model_key]}（AUC={auc_value:.3f}）",
        )
    ax.plot([0, 1], [0, 1], color=COLORS["ink"], linestyle=":", linewidth=1.4, label="随机分类基准（AUC=0.500）")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("假正率 FPR")
    ax.set_ylabel("真正率 TPR（召回率）")
    ax.set_title("图 5 三种分类模型的 ROC 曲线")
    ax.grid(color=COLORS["grid"], linewidth=0.7, alpha=0.85)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="lower right", fontsize=9)
    save_figure(fig, "figure_5_roc_curves.png")


def main() -> None:
    ensure_directories()
    configure_plot_style()

    bunch = load_breast_cancer(as_frame=True)
    features = bunch.data.copy()
    original_target = bunch.target.astype(int)
    target = (1 - original_target).rename("target_malignant")

    train_index, test_index = train_test_split(
        features.index,
        test_size=TEST_SIZE,
        stratify=target,
        random_state=RANDOM_STATE,
    )
    x_train = features.loc[train_index].copy()
    x_test = features.loc[test_index].copy()
    y_train = target.loc[train_index].copy()
    y_test = target.loc[test_index].copy()

    exported_data = features.copy()
    exported_data.insert(0, "sample_index", exported_data.index)
    exported_data["target_original_sklearn"] = original_target.values
    exported_data["target_malignant"] = target.values
    exported_data["split"] = ""
    exported_data.loc[exported_data["sample_index"].isin(train_index), "split"] = "train"
    exported_data.loc[exported_data["sample_index"].isin(test_index), "split"] = "test"
    exported_data.to_csv(DATA_DIR / "breast_cancer_binary.csv", index=False, encoding="utf-8-sig")

    quality = {
        "dataset_name": "scikit-learn breast cancer Wisconsin diagnostic dataset",
        "source": "sklearn.datasets.load_breast_cancer",
        "samples": int(features.shape[0]),
        "features": int(features.shape[1]),
        "missing_values": int(features.isna().sum().sum()),
        "duplicate_feature_rows": int(features.duplicated().sum()),
        "positive_class": "恶性（malignant）= 1",
        "negative_class": "良性（benign）= 0",
        "original_sklearn_encoding": "恶性（malignant）= 0，良性（benign）= 1",
        "train_samples": int(len(train_index)),
        "test_samples": int(len(test_index)),
        "test_size": TEST_SIZE,
        "stratified_split": True,
        "random_state": RANDOM_STATE,
        "data_as_of": f"scikit-learn {sklearn.__version__} bundled dataset",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    (OUTPUT_DIR / "data_quality.json").write_text(
        json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dataset_summary = pd.DataFrame(
        [
            ("样本数", features.shape[0], "条"),
            ("数值特征数", features.shape[1], "个"),
            ("恶性样本（正类）", int((target == 1).sum()), "条"),
            ("良性样本（负类）", int((target == 0).sum()), "条"),
            ("缺失值", int(features.isna().sum().sum()), "个"),
            ("重复特征记录", int(features.duplicated().sum()), "条"),
        ],
        columns=["item", "value", "unit"],
    )
    dataset_summary.to_csv(OUTPUT_DIR / "dataset_summary.csv", index=False, encoding="utf-8-sig")

    split_records: list[dict[str, object]] = []
    for split_name, y_values in (("训练集", y_train), ("测试集", y_test)):
        for class_value, class_name in ((0, "良性（0）"), (1, "恶性（1）")):
            count = int((y_values == class_value).sum())
            split_records.append(
                {
                    "split": split_name,
                    "class_value": class_value,
                    "class_name": class_name,
                    "count": count,
                    "proportion": count / len(y_values),
                }
            )
    split_summary = pd.DataFrame(split_records)
    split_summary.to_csv(OUTPUT_DIR / "split_summary.csv", index=False, encoding="utf-8-sig")

    models = build_models()
    metric_rows: list[dict[str, object]] = []
    roc_records: list[pd.DataFrame] = []
    predictions = pd.DataFrame(
        {
            "sample_index": x_test.index.astype(int),
            "true_label": y_test.astype(int).values,
        }
    )
    parameter_snapshot: dict[str, dict[str, object]] = {}
    confusion_matrices: dict[str, np.ndarray] = {}

    for model_position, model_key in enumerate(MODEL_ORDER, start=2):
        model = models[model_key]
        model.fit(x_train, y_train)
        test_prediction = model.predict(x_test).astype(int)
        test_probability = model.predict_proba(x_test)[:, 1]
        train_prediction = model.predict(x_train).astype(int)
        train_probability = model.predict_proba(x_train)[:, 1]

        tn, fp, fn, tp = confusion_matrix(y_test, test_prediction, labels=[0, 1]).ravel()
        auc_value = roc_auc_score(y_test, test_probability)
        ci_low, ci_high, valid_bootstraps = bootstrap_auc_ci(
            y_test.to_numpy(), test_probability, seed=BOOTSTRAP_RANDOM_STATE + model_position
        )
        fpr, tpr, thresholds = roc_curve(y_test, test_probability, pos_label=1)
        roc_records.append(
            pd.DataFrame(
                {
                    "model": model_key,
                    "model_zh": MODEL_NAMES_ZH[model_key],
                    "fpr": fpr,
                    "tpr": tpr,
                    "threshold": thresholds,
                }
            )
        )

        train_accuracy = accuracy_score(y_train, train_prediction)
        train_auc = roc_auc_score(y_train, train_probability)
        metric_rows.append(
            {
                "model": model_key,
                "model_zh": MODEL_NAMES_ZH[model_key],
                "accuracy": accuracy_score(y_test, test_prediction),
                "precision": precision_score(y_test, test_prediction, zero_division=0),
                "recall": recall_score(y_test, test_prediction, zero_division=0),
                "specificity": tn / (tn + fp),
                "f1": f1_score(y_test, test_prediction, zero_division=0),
                "roc_auc": auc_value,
                "auc_ci_low": ci_low,
                "auc_ci_high": ci_high,
                "bootstrap_valid_samples": valid_bootstraps,
                "tn": int(tn),
                "fp": int(fp),
                "fn": int(fn),
                "tp": int(tp),
                "train_accuracy": train_accuracy,
                "train_roc_auc": train_auc,
                "accuracy_gap_train_minus_test": train_accuracy - accuracy_score(y_test, test_prediction),
                "auc_gap_train_minus_test": train_auc - auc_value,
            }
        )
        predictions[f"{model_key}_prediction"] = test_prediction
        predictions[f"{model_key}_probability_malignant"] = test_probability
        confusion_matrices[model_key] = np.array([[tn, fp], [fn, tp]])

        raw_params = model.get_params(deep=True)
        parameter_snapshot[model_key] = {
            key: value
            for key, value in raw_params.items()
            if key
            in {
                "classifier__solver",
                "classifier__max_iter",
                "classifier__random_state",
                "criterion",
                "max_depth",
                "min_samples_leaf",
                "class_weight",
                "random_state",
                "n_estimators",
                "n_jobs",
            }
        }

    metrics = pd.DataFrame(metric_rows)
    metrics["model"] = pd.Categorical(metrics["model"], categories=MODEL_ORDER, ordered=True)
    metrics = metrics.sort_values("model").reset_index(drop=True)
    metrics["model"] = metrics["model"].astype(str)
    metrics.to_csv(OUTPUT_DIR / "metrics.csv", index=False, encoding="utf-8-sig", float_format="%.8f")
    predictions.to_csv(OUTPUT_DIR / "predictions.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    roc_rows = pd.concat(roc_records, ignore_index=True)
    roc_rows.to_csv(OUTPUT_DIR / "roc_curve_points.csv", index=False, encoding="utf-8-sig", float_format="%.10f")
    (OUTPUT_DIR / "model_parameters.json").write_text(
        json.dumps(parameter_snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

    plot_class_distribution(split_summary)
    for figure_number, model_key in enumerate(MODEL_ORDER, start=2):
        plot_confusion_matrix(model_key, confusion_matrices[model_key], figure_number)
    plot_roc_curves(roc_rows, metrics)

    chart_map = pd.DataFrame(
        [
            {
                "figure": "图 1",
                "section": "数据划分",
                "question": "分层抽样是否保持类别结构",
                "family": "Comparison",
                "chart_type": "grouped bar",
                "fields": "split, class_name, count",
                "takeaway": "训练集与测试集的良性/恶性比例基本一致",
                "palette": "blue + gold + neutrals",
                "artifact": "figure_1_class_distribution.png",
            },
            *[
                {
                    "figure": f"图 {index}",
                    "section": "模型评价",
                    "question": f"{MODEL_NAMES_ZH[key]}在固定阈值下产生了哪些正确与错误分类",
                    "family": "Matrix",
                    "chart_type": "confusion matrix heatmap",
                    "fields": "true_label, predicted_label, count",
                    "takeaway": "同时查看 TN、FP、FN、TP，避免只依赖准确率",
                    "palette": "single blue root",
                    "artifact": f"figure_{index}_{key}_confusion_matrix.png",
                }
                for index, key in enumerate(MODEL_ORDER, start=2)
            ],
            {
                "figure": "图 5",
                "section": "ROC/AUC",
                "question": "三个模型跨阈值的区分能力如何",
                "family": "Uncertainty & Benchmark",
                "chart_type": "multi-series ROC line",
                "fields": "fpr, tpr, model, roc_auc",
                "takeaway": "曲线越靠左上且 AUC 越高，排序区分能力越强",
                "palette": "blue + gold + pink + neutral benchmark",
                "artifact": "figure_5_roc_curves.png",
            },
        ]
    )
    chart_map.to_csv(OUTPUT_DIR / "chart_map.csv", index=False, encoding="utf-8-sig")

    best_row = metrics.sort_values(["roc_auc", "recall", "f1"], ascending=False).iloc[0]
    notes = {
        "title": TITLE,
        "best_model_by_test_auc": str(best_row["model"]),
        "best_model_zh": str(best_row["model_zh"]),
        "best_test_auc": float(best_row["roc_auc"]),
        "best_auc_ci": [float(best_row["auc_ci_low"]), float(best_row["auc_ci_high"])],
        "best_recall": float(best_row["recall"]),
        "interpretation_boundary": "该实验验证分类流程，不构成医学诊断或投资建议。",
    }
    (OUTPUT_DIR / "analysis_summary.json").write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(metrics[["model_zh", "accuracy", "precision", "recall", "specificity", "f1", "roc_auc"]].to_string(index=False))
    print(f"\n数据和图表已输出至：{OUTPUT_DIR}")


if __name__ == "__main__":
    sys.exit(main())
