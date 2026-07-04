# 寒武纪 A 股近一年交易数据展示

本项目使用 TuShare 查询寒武纪（`688256.SH`）过去一年的 A 股交易日行情，保存未复权与前复权两份 CSV 数据，并生成一个可直接打开的静态 HTML 页面展示每日收盘价曲线。

## 数据口径

- 股票：寒武纪，TuShare 代码 `688256.SH`
- 区间：`2025-07-04` 至 `2026-07-04`，以 TuShare 返回的可用交易日为准
- 未复权：TuShare `daily` 接口原始日线行情
- 复权：前复权（qfq），由 `daily` 价格与 `adj_factor` 复权因子计算
- 前复权公式：`前复权价格 = 未复权价格 * 当日复权因子 / 区间最新复权因子`

前复权是 A 股行情软件中最常见的展示口径之一，优点是最新价格与真实交易价格一致，同时历史价格会按分红、送转等因素调整，便于观察连续收益走势。

## 目录结构

```text
Task1/
  data/        # CSV 数据输出
  scripts/     # 数据获取与静态网页生成脚本
  web/         # 静态 HTML 展示文件
  Task1_process_walkthrough.ipynb  # 流程复盘与学习 notebook
```

## 运行方式

不要把真实 token 提交到 GitHub。推荐使用环境变量：

```powershell
$env:TUSHARE_TOKEN = "your_token_here"
python .\scripts\fetch_tushare_cambricon.py --start-date 20250704 --end-date 20260704
```

也可以在 `Task1/.env` 中保存：

```text
TUSHARE_TOKEN=your_token_here
```

`.env` 已被 `.gitignore` 排除，不会进入公开仓库。

## 输出文件

脚本会生成：

- `data/cambricon_688256_SH_daily_unadjusted_20250704_20260704.csv`
- `data/cambricon_688256_SH_daily_qfq_20250704_20260704.csv`
- `data/cambricon_688256_SH_daily_combined_20250704_20260704.csv`
- `web/index.html`
- `Task1_process_walkthrough.ipynb`

打开 `web/index.html` 即可查看图表和数据表。
