from __future__ import annotations

from html import escape
from pathlib import Path

from workshop_web_theme import WORKSHOP_CSS, task_navigation


ROOT = Path(__file__).resolve().parent


TASKS = (
    {
        "label": "TASK1",
        "tag": "数据引擎",
        "title": "寒武纪行情获取与复权处理",
        "description": "从行情接口到本地CSV快照，统一日期、价格、成交量与前复权序列。",
        "web": "Task1/web/index.html",
        "notebook": "Task1/Task1_process_walkthrough.ipynb",
    },
    {
        "label": "TASK2",
        "tag": "指标诊断",
        "title": "数据诊断与技术指标构建",
        "description": "检查数据质量与分布，计算RSI、MACD、布林带和ATR。",
        "web": "Task2/web/index.html",
        "notebook": "Task2/Task2_process_walkthrough.ipynb",
    },
    {
        "label": "TASK3",
        "tag": "趋势策略",
        "title": "双均线策略与跨行业回测",
        "description": "使用金叉、死叉构建趋势跟踪策略，并比较股票、行业和均线参数。",
        "web": "Task3/web/index.html",
        "notebook": "Task3/Task3_process_walkthrough.ipynb",
    },
    {
        "label": "TASK4",
        "tag": "风险控制",
        "title": "海龟交易策略与参数研究",
        "description": "结合高低点通道、Wilder ATR、风险定仓和止损完成样本外回测。",
        "web": "Task4/web/index.html",
        "notebook": "Task4/Task4_process_walkthrough.ipynb",
    },
)


def build_index() -> Path:
    cards = []
    for item in TASKS:
        cards.append(
            f"""
            <article class="card">
              <span class="tag">{escape(item['label'])} · {escape(item['tag'])}</span>
              <h3>{escape(item['title'])}</h3>
              <p>{escape(item['description'])}</p>
              <div class="pill-row">
                <a class="pill" href="{item['web']}">打开网页</a>
                <a class="pill" href="{item['notebook']}">查看 Notebook</a>
              </div>
            </article>
            """.strip()
        )

    body = f"""
    <div class="wrap metrics">
      <div class="metric"><span>课程任务</span><strong>4 个</strong></div>
      <div class="metric"><span>数据与诊断</span><strong>Task1–2</strong></div>
      <div class="metric"><span>策略与回测</span><strong>Task3–4</strong></div>
      <div class="metric"><span>统一交付</span><strong>Web + Notebook</strong></div>
    </div>
    <section><div class="wrap"><h2>学习路径</h2><p class="section-lede">从可靠行情数据出发，逐步完成指标构建、趋势策略和风险控制。</p><div class="grid two">{''.join(cards)}</div></div></section>
    <section><div class="wrap"><h2>统一的研究口径</h2><div class="grid">
      <article class="card"><h3>可复现</h3><p>每个任务保留代码、数据快照、Notebook、图表和静态网页，可从本地重新生成。</p></article>
      <article class="card"><h3>防止前视偏差</h3><p>策略信号使用已知历史信息，并将普通收盘信号错后一交易日执行。</p></article>
      <article class="card"><h3>收益与风险并重</h3><p>同时观察累计回报、最大回撤、夏普比率、交易成本和买入持有基准。</p></article>
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
    {task_navigation(0, root_prefix="")}
    <div class="tag">PKU WORKSHOP · 202607</div>
    <h1>量化交易工作坊<br>从数据到策略与风控</h1>
    <p>四个逐步递进的任务：行情数据引擎、数据诊断与指标、双均线策略，以及海龟交易法则。</p>
  </div></header>
  <main>{body}</main>
  <footer><div class="wrap">PKU Workshop 202607｜Python / pandas / Matplotlib｜GitHub Pages 静态成果入口</div></footer>
</body>
</html>
"""
    output = ROOT / "index.html"
    output.write_text(html, encoding="utf-8")
    return output


if __name__ == "__main__":
    print(build_index())
