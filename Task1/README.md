# Task1 寒武纪行情数据 demo

## 任务需求与解决思路

Task1 的目标是演示一个最小可复现的数据项目：用 TuShare 获取寒武纪（`688256.SH`）日线行情，保存 CSV，再生成一个静态网页展示未复权和前复权收盘价。

解决过程拆成三步：

1. `fetch_data.py` 只负责数据：读取 token、调用 TuShare、合并 `daily` 和 `adj_factor`、计算前复权价格、保存 CSV。
2. `build_site.py` 只负责展示：读取已经保存的 combined CSV，用 matplotlib 画价格图，再写出 `web/index.html`。
3. `run_all.py` 是薄入口：需要联网抓数据时完整运行；已有 CSV 时用 `--skip-fetch` 只重建网页。

前复权公式：

```text
前复权价格 = 未复权价格 * 当日复权因子 / 区间最新复权因子
```

## 目录结构

```text
Task1/
  data/        # CSV 数据输出
  scripts/     # 数据获取、网页生成、notebook 生成脚本
  web/         # 静态 HTML 展示文件
  Task1_process_walkthrough.ipynb  # 流程复盘与学习 notebook
```

## 运行方式

本项目用根目录的 `uv` 环境。不要把真实 token 提交到 GitHub。推荐使用环境变量：

```powershell
$env:TUSHARE_TOKEN = "your_token_here"
uv run python .\Task1\scripts\run_all.py --start-date 20250704 --end-date 20260704
```

也可以在 `Task1/.env` 中保存：

```text
TUSHARE_TOKEN=your_token_here
```

`.env` 已被 `.gitignore` 排除，不会进入公开仓库。

如果只是重新生成网页，不需要 token：

```powershell
uv run python .\Task1\scripts\run_all.py --skip-fetch
```

## 输出文件

脚本会生成：

- `data/cambricon_688256_SH_daily_unadjusted_20250704_20260704.csv`
- `data/cambricon_688256_SH_daily_qfq_20250704_20260704.csv`
- `data/cambricon_688256_SH_daily_combined_20250704_20260704.csv`
- `web/cambricon_price.png`
- `web/index.html`
- `Task1_process_walkthrough.ipynb`

打开 `web/index.html` 即可查看图表和数据表。
