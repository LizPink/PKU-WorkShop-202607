from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockSpec:
    ts_code: str
    stock_name: str
    industry: str


UNIVERSE: tuple[StockSpec, ...] = (
    StockSpec("000001.SZ", "平安银行", "银行"),
    StockSpec("600036.SH", "招商银行", "银行"),
    StockSpec("600519.SH", "贵州茅台", "食品饮料"),
    StockSpec("000858.SZ", "五粮液", "食品饮料"),
    StockSpec("002594.SZ", "比亚迪", "新能源汽车"),
    StockSpec("300750.SZ", "宁德时代", "新能源汽车"),
    StockSpec("002371.SZ", "北方华创", "半导体"),
    StockSpec("600584.SH", "长电科技", "半导体"),
    StockSpec("600031.SH", "三一重工", "工程机械"),
    StockSpec("000425.SZ", "徐工机械", "工程机械"),
)

DEFAULT_START_DATE = "20190101"
DEFAULT_SHORT_WINDOW = 5
DEFAULT_LONG_WINDOW = 15
DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_TRANSACTION_COST = 0.001
TRADING_DAYS_PER_YEAR = 252
OUT_OF_SAMPLE_START = "2024-01-01"
CROSS_TOLERANCE = 1e-10

PARAMETER_PAIRS: tuple[tuple[int, int], ...] = (
    (5, 10),
    (5, 15),
    (10, 20),
    (10, 30),
    (20, 60),
)


def code_slug(ts_code: str) -> str:
    return ts_code.replace(".", "_")


def parameter_label(short_window: int, long_window: int) -> str:
    return f"MA{short_window}/MA{long_window}"
