# PKU Workshop 202607 Demo

这个工作区包含四个逐步递进的量化交易任务，统一用根目录 `pyproject.toml` 和 `uv.lock` 管理环境。

## 项目结构

```text
Task1/  # TuShare 获取寒武纪行情，计算前复权价格并生成网页
Task2/  # 基于本地 CSV 计算 RSI、MACD、布林带、ATR 并生成网页
Task3/  # 跨行业股票双均线策略、回测、参数比较、Notebook 与网页
Task4/  # 海龟交易策略、ATR风险定仓、止损、参数研究与网页
```

## 运行环境

```powershell
uv sync --group dev
```

如果本机默认 uv 缓存目录不可写，可以把缓存放在项目内：

```powershell
uv --cache-dir .uv-cache sync --group dev
```

## 常用命令

Task1 如果已经有 CSV，只重建网页：

```powershell
uv run python .\Task1\scripts\run_all.py --skip-fetch
```

Task1 如果要重新从 TuShare 获取数据：

```powershell
$env:TUSHARE_TOKEN = "your_token_here"
uv run python .\Task1\scripts\run_all.py --start-date 20250704 --end-date 20260704
```

Task2 重新生成指标、图表和网页：

```powershell
uv run python .\Task2\scripts\run_all.py
```

Task3 首次抓取跨行业行情并生成完整回测：

```powershell
uv run python .\Task3\scripts\run_all.py --force-fetch
```

Task3 使用本地行情快照重建结果：

```powershell
uv run python .\Task3\scripts\run_all.py --skip-fetch
```

Task4 使用 Task3 的本地行情快照重建海龟策略结果：

```powershell
uv --cache-dir .uv-cache run python .\Task4\scripts\run_all.py
```

重新生成教学 notebook：

```powershell
uv run python .\Task1\scripts\build_walkthrough_notebook.py
uv run python .\Task2\scripts\build_walkthrough_notebook.py
uv run python .\Task3\scripts\build_walkthrough_notebook.py
uv run python .\Task4\scripts\build_walkthrough_notebook.py
```
