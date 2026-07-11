# Task3：双均线策略与跨行业回测

## 任务目标

本任务在 Task1 数据引擎和 Task2 数据诊断、技术指标的基础上，实现一个可复现的双均线趋势跟随策略：

1. 解释金叉、死叉和趋势跟随；
2. 明确何时买入、何时卖出；
3. 对 5 个行业、10 只代表性股票进行回测；
4. 计算累计回报、最大回撤和夏普比率；
5. 比较不同股票和均线参数的样本内、样本外表现；
6. 输出 CSV、PNG、Markdown、教学 Notebook 和静态网页。

## 股票池

| 行业 | 股票 |
|---|---|
| 银行 | 平安银行、招商银行 |
| 食品饮料 | 贵州茅台、五粮液 |
| 新能源汽车 | 比亚迪、宁德时代 |
| 半导体 | 北方华创、长电科技 |
| 工程机械 | 三一重工、徐工机械 |

行情为日频前复权本地快照，默认从 2019-01-01 开始。优先使用 TuShare Pro 的 `daily + adj_factor`；若 `adj_factor` 受 Token 频率限制，则保留 TuShare Pro 日线作为日期校验，并从公开前复权接口或 TuShare legacy qfq 补充前复权 OHLC。每只股票都会保存实际数据来源和抓取日期，Token 不写入项目文件。

## 交易规则

- 短均线默认 MA5，长均线默认 MA15。
- 当短均线从不高于长均线变为高于长均线时，产生金叉买入信号。
- 当短均线从高于长均线变为不高于长均线时，产生死叉卖出信号。
- 当日收盘后生成信号，下一交易期才应用仓位。
- 只做多，不做空，不使用杠杆；仓位只在 0% 和 100% 之间切换。
- 初始资金 100,000 元，单边综合交易成本默认为 0.1%。
- 长均线尚未形成时保持空仓。

核心代码使用 `position = target_position.shift(1)`，避免信号当日的前视偏差。

## 指标定义

- 累计回报：`期末净值 / 期初净值 - 1`
- 最大回撤：`净值 / 历史最高净值 - 1` 的最小值
- 夏普比率：`日均收益 / 日收益标准差 × sqrt(252)`，无风险利率设为 0
- 买入持有基准：从比较区间开始持续持有同一只股票

## 运行方式

首次抓取数据并生成全部结果：

```powershell
uv run python .\Task3\scripts\run_all.py --force-fetch --prompt-token
```

使用已经保存的数据快照重新生成全部结果：

```powershell
uv run python .\Task3\scripts\run_all.py --skip-fetch
```

执行教学 Notebook：

```powershell
uv run jupyter nbconvert --execute --to notebook --inplace .\Task3\Task3_process_walkthrough.ipynb
```

## 主要输出

```text
Task3/
  data/       10 只股票行情、股票池信息和数据质量汇总
  scripts/    数据抓取、策略、分析、网页、Notebook 和验证脚本
  outputs/    回测明细、参数比较、行业汇总、图表和报告
  web/        静态教学网页
  Task3_process_walkthrough.ipynb
```

打开 `web/index.html` 可以查看网页版本结果。

## 研究限制

股票池按代表性人工选择，存在幸存者偏差；参数组合经过多重比较；交易成本为简化假设，未模拟涨跌停、滑点差异、成交量约束和整手交易。结果用于教学和研究演示，不构成投资建议。
