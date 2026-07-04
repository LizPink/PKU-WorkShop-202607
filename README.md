# PKU Workshop 202607 Demo

这个工作区包含两个小型金融数据 demo，统一用根目录 `pyproject.toml` 和 `uv.lock` 管理环境。

## 项目结构

```text
Task1/  # TuShare 获取寒武纪行情，计算前复权价格并生成网页
Task2/  # 基于本地 CSV 计算 RSI、MACD、布林带、ATR 并生成网页
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

重新生成两个教学 notebook：

```powershell
uv run python .\Task1\scripts\build_walkthrough_notebook.py
uv run python .\Task2\scripts\build_walkthrough_notebook.py
```
