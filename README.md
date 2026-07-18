# PKU Workshop 202607 Demo

这个工作区包含六个逐步递进的金融数据与量化研究任务，统一使用根目录 `pyproject.toml` 和 `uv.lock` 管理 Python 环境，并通过根目录网页提供 GitHub Pages 导航。

## 项目结构

```text
Task1/  # TuShare 获取寒武纪行情，计算前复权价格并生成网页
Task2/  # 基于本地 CSV 计算 RSI、MACD、布林带、ATR 并生成网页
Task3/  # 跨行业股票双均线策略、回测、参数比较、Notebook 与网页
Task4/  # 海龟交易策略、ATR 风险定仓、止损、参数研究与网页
TASK5/  # 逻辑回归、决策树、随机森林分类实验与报告
TASK6/  # 季度收益排序、Top 30 组合、机器学习回测与报告
```

## 运行环境

在仓库根目录安装依赖：

```powershell
uv sync
```

## 常用命令

Task1 重新抓取行情并生成网页：

```powershell
uv run python .\Task1\scripts\run_all.py
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

Task5 和 Task6 的数据、模型、报告与校验命令见各自目录中的 `README.md`。

重新生成前四个教学 Notebook：

```powershell
uv run python .\Task1\scripts\build_walkthrough_notebook.py
uv run python .\Task2\scripts\build_walkthrough_notebook.py
uv run python .\Task3\scripts\build_walkthrough_notebook.py
uv run python .\Task4\scripts\build_walkthrough_notebook.py
```

重新生成统一站点首页：

```powershell
uv run python .\build_workshop_index.py
```
