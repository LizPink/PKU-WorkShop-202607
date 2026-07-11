from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockSpec:
    ts_code: str
    stock_name: str
    industry: str


@dataclass(frozen=True)
class TurtleParams:
    entry_window: int
    exit_window: int
    atr_window: int
    stop_atr: float


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

DEFAULT_PARAMS = TurtleParams(entry_window=20, exit_window=10, atr_window=20, stop_atr=2.0)
PARAMETER_SETS: tuple[TurtleParams, ...] = (
    TurtleParams(10, 5, 14, 1.5),
    TurtleParams(20, 10, 20, 1.5),
    DEFAULT_PARAMS,
    TurtleParams(20, 10, 20, 3.0),
    TurtleParams(40, 20, 20, 2.0),
    TurtleParams(55, 20, 20, 2.0),
)

DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_TRANSACTION_COST = 0.001
DEFAULT_RISK_FRACTION = 0.01
DEFAULT_MAX_ALLOCATION = 1.0
TRADING_DAYS_PER_YEAR = 252
OUT_OF_SAMPLE_START = "2024-01-01"


def code_slug(ts_code: str) -> str:
    return ts_code.replace(".", "_")


def parameter_label(params: TurtleParams) -> str:
    return (
        f"E{params.entry_window}/X{params.exit_window}/"
        f"ATR{params.atr_window}/S{params.stop_atr:g}"
    )


def parameter_slug(params: TurtleParams) -> str:
    stop = str(params.stop_atr).replace(".", "p")
    return f"T{params.entry_window}_{params.exit_window}_ATR{params.atr_window}_S{stop}"
