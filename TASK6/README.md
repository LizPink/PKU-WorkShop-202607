# TASK6 智能决策者：用机器学习定制专属策略

本目录实现“季度预测收益排序 - Top 30 等权选股 - 市场平均比较”的完整机器学习回测，并生成符合课程格式要求的 DOCX/PDF 报告和可离线浏览的单文件网页报告。

## 数据口径

- 股票池：从抓取日的中证 300 当前成分列表按代码排序等距抽取 120 只；
- 行情：AkShare 提供的东方财富后复权日行情，接口限流时使用腾讯后复权行情补充；后复权可避免长期前复权价格过小及四舍五入造成的收益伪影；
- 因子：18 个动量、趋势、风险和流动性因子；
- 标签：季度末形成信号，下一季度首个交易日开盘建仓，到再下一季度首个交易日开盘的收益及其横截面排名；
- 测试：最后 8 个完整季度，逐季度扩展窗口重训；
- 策略：预测前 30 等权，市场基准为同季度可投资研究样本等权平均；
- 成本：主假设为单边综合成本 0.2%，并分析 0.1%/0.2%/0.3%。

注意：当前成分股回溯存在幸存者偏差，历史 ST、停牌、涨跌停和冲击成本未被完整模拟。结果只用于课程研究，不构成投资建议。

## 运行方式

公开数据已经缓存时，在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe .\TASK6\scripts\run_all.py
```

若要重新联网抓取数据，需要使用安装了 AkShare 的 Python：

```powershell
python .\TASK6\scripts\fetch_data.py --max-stocks 120 --workers 2
```

使用 Microsoft Word 导出 PDF：

```powershell
powershell -ExecutionPolicy Bypass -File .\TASK6\scripts\export_pdf.ps1 `
  -InputDocx .\TASK6\report\姓名TASK6.docx `
  -OutputPdf .\TASK6\report\姓名TASK6.pdf
```

最终校验：

```powershell
.\.venv\Scripts\python.exe .\TASK6\scripts\validate_outputs.py
```

重新生成并校验网页报告：

```powershell
.\.venv\Scripts\python.exe .\TASK6\scripts\build_web_report.py
.\.venv\Scripts\python.exe .\TASK6\scripts\validate_web_report.py
```

## 主要输出

- `data/processed/quarterly_panel.csv`：股票 - 季度因子和未来收益；
- `outputs/test_predictions.csv`：三类模型测试期逐股票预测；
- `outputs/holdings.csv`：每季度 Top 30 持仓；
- `outputs/quarterly_returns.csv`：策略和市场平均季度收益；
- `outputs/model_metrics.csv`、`backtest_metrics.csv`：预测和回测指标；
- `outputs/figures/`：8 幅带编号的统计图；
- `TASK6_walkthrough.ipynb`：已执行的教学型审计 Notebook；
- `report/姓名TASK6.docx`、`report/姓名TASK6.pdf`：报告和正式提交件；
- `report/姓名TASK6.html`：图表、样式和交互均内嵌的离线网页报告；
- `outputs/validation_report.md`：计算与交付校验记录。
