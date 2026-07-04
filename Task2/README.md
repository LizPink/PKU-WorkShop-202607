# Task2 金融数据技术指标分析 demo

## 任务需求与解决思路

Task2 的目标是基于 `data/` 中已经保存好的“平安集团”和“三一重工”CSV 行情文件，做一个简洁的技术指标 demo：先诊断数据，再计算指标，最后生成报告和网页。

解决过程拆成三步：

1. `calculate_indicators.py` 只负责分析：读取 CSV，检查缺失值，计算描述性统计量、绘制整体数据画像，计算 RSI、MACD、布林带和 ATR，并输出 CSV/PNG/Markdown。
2. `build_site.py` 只负责展示：读取 `outputs/` 中的结果，生成 `web/index.html`。
3. `run_all.py` 是薄入口：一键重新生成指标、图表、报告和网页。

指标公式：

- RSI：`RS = 平均上涨幅度 / 平均下跌幅度`，`RSI = 100 - 100 / (1 + RS)`。
- MACD：`MACD = EMA12 - EMA26`，信号线为 MACD 的 9 日 EMA，柱状图为两者差值。
- 布林带：中轨为 20 日均线，上下轨为中轨加减 2 倍滚动标准差。
- ATR：TR 取 `high-low`、`abs(high-前收盘)`、`abs(low-前收盘)` 三者最大值，再做 14 日平滑。

## 目录结构

```text
Task2/
  data/        # 原始 CSV 行情数据
  scripts/     # 指标计算、网页生成、notebook 生成脚本
  outputs/     # 诊断结果、指标 CSV、PNG 图和 Markdown 报告
  web/         # 静态 HTML 展示页面
  Task2_process_walkthrough.ipynb  # 教学型流程拆解 notebook
```

## 运行方式

```powershell
uv run python .\Task2\scripts\run_all.py
```

重新生成教学 notebook：

```powershell
uv run python .\Task2\scripts\build_walkthrough_notebook.py
```

## 输出文件

- `outputs/analysis_report.md`
- `outputs/diagnostics_summary.csv`
- `outputs/missing_values.csv`
- `outputs/latest_indicator_snapshot.csv`
- `outputs/data_description_overview.png`
- `outputs/price_volume_overview.png`
- `outputs/daily_return_distribution.png`
- `outputs/000001_SZ_indicators.csv`
- `outputs/600031_SH_indicators.csv`
- `outputs/000001_SZ_technical_indicators.png`
- `outputs/600031_SH_technical_indicators.png`
- `web/index.html`

打开 `web/index.html` 即可查看网页版结果。
