from __future__ import annotations

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
WEB_DIR = PROJECT_DIR / "web"
REPORT_DIR = PROJECT_DIR / "report"
QA_DIR = PROJECT_DIR / "tmp" / "qa"

TITLE = "TASK5 AI交易引擎：机器学习算法与场景应用"
SUBMISSION_STEM = "姓名TASK5"
RANDOM_STATE = 42
TEST_SIZE = 0.20
BOOTSTRAP_RANDOM_STATE = 20260717
BOOTSTRAP_SAMPLES = 2000

MODEL_ORDER = ["logistic_regression", "decision_tree", "random_forest"]
MODEL_NAMES_ZH = {
    "logistic_regression": "逻辑回归",
    "decision_tree": "决策树",
    "random_forest": "随机森林",
}

COLORS = {
    "blue": "#31688E",
    "gold": "#D39C2C",
    "pink": "#C45A8D",
    "ink": "#263238",
    "muted": "#68737D",
    "grid": "#DCE2E8",
    "light_blue": "#E8F1F6",
    "light_gray": "#F5F7F9",
}


def ensure_directories() -> None:
    for path in (DATA_DIR, OUTPUT_DIR, FIGURE_DIR, WEB_DIR, REPORT_DIR, QA_DIR):
        path.mkdir(parents=True, exist_ok=True)
