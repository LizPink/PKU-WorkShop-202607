from __future__ import annotations

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
RAW_DAILY_DIR = RAW_DIR / "akshare_daily_hfq"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_DIR / "outputs"
FIGURE_DIR = OUTPUT_DIR / "figures"
REPORT_DIR = PROJECT_DIR / "report"
QA_DIR = PROJECT_DIR / "tmp" / "qa"

TITLE = "TASK6 智能决策者：用机器学习定制专属策略"
SUBMISSION_STEM = "姓名TASK6"
RANDOM_STATE = 42

DATA_START = "20150101"
DATA_END = "20260705"
INDEX_CODE = "000300"
MAX_STOCKS = 300

TEST_QUARTERS = 8
VALIDATION_QUARTERS = 4
TOP_N = 30
ONE_WAY_COST = 0.002
COST_SCENARIOS = [0.001, 0.002, 0.003]

FEATURE_COLUMNS = [
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "ret_126d",
    "ret_252d",
    "momentum_12_1",
    "volatility_20d",
    "volatility_60d",
    "downside_volatility_60d",
    "max_drawdown_126d",
    "turnover_20d",
    "turnover_60d",
    "log_amount_20d",
    "amihud_20d",
    "volume_ratio_20_60",
    "price_to_ma20",
    "price_to_ma60",
    "intraday_range_20d",
]

MODEL_ORDER = ["ridge", "decision_tree", "random_forest"]
MODEL_NAMES_ZH = {
    "ridge": "岭回归",
    "decision_tree": "决策树",
    "random_forest": "随机森林",
}

COLORS = {
    "blue": "#2F6B8A",
    "gold": "#C6912B",
    "orange": "#D56A3A",
    "pink": "#B65C83",
    "olive": "#7A8532",
    "ink": "#263238",
    "muted": "#6B747C",
    "grid": "#DDE3E8",
    "light_blue": "#E8F1F5",
    "light_gray": "#F4F6F7",
}


def ensure_directories() -> None:
    for path in (
        RAW_DIR,
        RAW_DAILY_DIR,
        PROCESSED_DIR,
        OUTPUT_DIR,
        FIGURE_DIR,
        REPORT_DIR,
        QA_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
