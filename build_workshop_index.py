from __future__ import annotations

from html import escape
from pathlib import Path

from workshop_web_theme import WORKSHOP_CSS, render_task_nav


ROOT = Path(__file__).resolve().parent


TASKS = (
    {
        "label": "TASK1",
        "tag": "数据引擎",
        "title": "寒武纪行情获取与复权处理",
        "description": "从行情接口到本地 CSV 快照，统一日期、价格、成交量与前复权序列。",
        "links": (("打开网页", "Task1/web/index.html"), ("查看 Notebook", "Task1/Task1_process_walkthrough.ipynb")),
    },
    {
        "label": "TASK2",
        "tag": "指标诊断",
        "title": "数据诊断与技术指标构建",
        "description": "检查数据质量与分布，计算 RSI、MACD、布林带和 ATR。",
        "links": (("打开网页", "Task2/web/index.html"), ("查看 Notebook", "Task2/Task2_process_walkthrough.ipynb")),
    },
    {
        "label": "TASK3",
        "tag": "趋势策略",
        "title": "双均线策略与跨行业回测",
        "description": "使用金叉、死叉构建趋势跟踪策略，并比较股票、行业和均线参数。",
        "links": (("打开网页", "Task3/web/index.html"), ("查看 Notebook", "Task3/Task3_process_walkthrough.ipynb")),
    },
    {
        "label": "TASK4",
        "tag": "风险控制",
        "title": "海龟交易策略与参数研究",
        "description": "结合高低点通道、Wilder ATR、风险定仓和止损完成样本外回测。",
        "links": (("打开网页", "Task4/web/index.html"), ("查看 Notebook", "Task4/Task4_process_walkthrough.ipynb")),
    },
    {
        "label": "TASK5",
        "tag": "机器学习分类",
        "title": "AI 交易引擎算法实验",
        "description": "比较逻辑回归、决策树与随机森林，用混淆矩阵、ROC 和 AUC 评估分类效果。",
        "links": (("打开网页", "TASK5/web/index.html"), ("查看指标", "TASK5/outputs/metrics.csv"), ("查看 PDF", "TASK5/report/李子平-TASK5.pdf")),
    },
    {
        "label": "TASK6",
        "tag": "机器学习选股",
        "title": "智能决策者量化策略",
        "description": "用 18 个因子预测下一季度收益排序，构建 Top 30 组合并完成扩展窗口回测。",
        "links": (("打开网页", "TASK6/web/index.html"), ("查看指标", "TASK6/outputs/backtest_metrics.csv"), ("查看 PDF", "TASK6/report/李子平-TASK6.pdf")),
    },
)


def build_index() -> Path:
    cards = []
    for item in TASKS:
        links = "".join(
            f'<a class="pill" href="{escape(href)}">{escape(label)}</a>'
            for label, href in item["links"]
        )
        cards.append(
            f"""
            <article class="card">
              <span class="tag">{escape(item['label'])} · {escape(item['tag'])}</span>
              <h3>{escape(item['title'])}</h3>
              <p>{escape(item['description'])}</p>
              <div class="pill-row">{links}</div>
            </article>
            """.strip()
        )

    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>课程任务</span><strong>6 个</strong></div>
      <div class="metric"><span>数据与诊断</span><strong>Task1–2</strong></div>
      <div class="metric"><span>规则策略</span><strong>Task3–4</strong></div>
      <div class="metric"><span>机器学习</span><strong>Task5–6</strong></div>
    </div>
    <section><div class="wrap"><h2>学习路径</h2><p class="section-lede">从可靠行情数据出发，逐步完成指标构建、规则策略、风险控制与机器学习决策。</p><div class="grid two">{''.join(cards)}</div></div></section>
    <section><div class="wrap"><h2>统一的研究口径</h2><div class="grid">
      <article class="card"><h3>可复现</h3><p>每个任务保留代码、数据快照、Notebook、图表、报告或静态网页，可从本地重新生成。</p></article>
      <article class="card"><h3>控制前视偏差</h3><p>策略信号使用当时已知信息，训练与测试按时间划分，并明确交易执行时点。</p></article>
      <article class="card"><h3>收益与风险并重</h3><p>同时观察收益、回撤、风险调整指标、交易成本和可比基准。</p></article>
    </div><p class="note">本项目用于课程教学和研究演示，不构成投资建议。</p></div></section>
    """

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>PKU Workshop 202607｜量化交易任务集</title>
  <style>{WORKSHOP_CSS}</style>
</head>
<body>
  <header class="hero"><div class="wrap">
    {render_task_nav(0, root_prefix="")}
    <div class="tag">PKU WORKSHOP · 202607</div>
    <h1>量化交易工作坊<br>从数据到策略与风控</h1>
    <p>六个逐步递进的任务：行情数据、技术指标、规则策略、风险控制、机器学习分类与量化选股。</p>
  </div></header>
  <main>{body}</main>
  <footer><div class="wrap">PKU Workshop 202607｜Python / pandas / Matplotlib｜GitHub Pages 静态成果入口</div></footer>
</body>
</html>
"""
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    output = ROOT / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_index())
