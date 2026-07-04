# Task2 金融数据技术指标分析 demo

## 任务需求与解决思路

Task2 的目标是基于 `data/` 中已经保存好的“平安集团”和“三一重工”CSV 行情文件，做一个简洁的技术指标 demo：先诊断数据，再计算指标，最后生成报告和网页。

解决过程拆成三步：

1. `calculate_indicators.py` 只负责分析：读取 CSV，检查缺失值，计算描述性统计量、绘制整体数据画像，计算 RSI、MACD、布林带和 ATR，并输出 CSV/PNG/Markdown。
2. `build_site.py` 只负责展示：读取 `outputs/` 中的结果，生成 `web/index.html`。
3. `run_all.py` 是薄入口：一键重新生成指标、图表、报告和网页。

## 技术指标说明

### RSI：Relative Strength Index / 相对强弱指数

- 计算方法：先计算每日收盘价变化，`U=max(涨跌幅, 0)`，`D=max(-涨跌幅, 0)`；`RS=WilderAvg(U, 14)/WilderAvg(D, 14)`；`RSI=100-100/(1+RS)`。
- 金融应用：衡量上涨动能与下跌动能的相对强弱。常用 `70` 以上观察超买、`30` 以下观察超卖，也常配合价格背离判断动能衰减。
- 解读提醒：RSI 是动量指标，不是单独买卖信号。强趋势中 RSI 可以长时间维持高位或低位，需要结合趋势和成交量判断。

### MACD：Moving Average Convergence Divergence / 指数平滑异同移动平均线

- 计算方法：`EMA_n` 使用 `alpha=2/(n+1)` 递推；`DIF=EMA12(收盘价)-EMA26(收盘价)`；`Signal/DEA=EMA9(DIF)`；本 demo 的柱状图为 `DIF-Signal`。
- 金融应用：识别趋势动量变化。常看 DIF 与 Signal 的金叉/死叉、零轴上方或下方的位置，以及价格与 MACD 的背离。
- 解读提醒：MACD 本质上来自移动平均，天然滞后；震荡行情里交叉信号容易反复。一些行情软件会把柱状图写成 `2*(DIF-DEA)`，本项目没有乘以 2。

### Bollinger Bands：布林带

- 计算方法：中轨为 `SMA20(收盘价)`；标准差为收盘价的 20 日滚动标准差；上轨为 `中轨+2*标准差`；下轨为 `中轨-2*标准差`。
- 金融应用：用均线和波动率描述价格运行区间。带宽收窄常表示波动压缩，突破后可能进入趋势扩张；价格靠近上下轨可辅助观察短期偏热或偏冷。
- 解读提醒：触及上轨不等于必须卖出，触及下轨也不等于必须买入。趋势行情中价格可能沿上轨或下轨运行，需要结合方向和带宽变化。

### ATR：Average True Range / 平均真实波幅

- 计算方法：`TR=max(high-low, abs(high-前收盘), abs(low-前收盘))`；`ATR=WilderAvg(TR, 14)`。
- 金融应用：衡量价格波动幅度，常用于设置止损距离、比较不同股票的波动水平、辅助仓位管理。
- 解读提醒：ATR 只衡量波动大小，不判断涨跌方向。ATR 上升说明波动变大，但不代表一定上涨或下跌。

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
