from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import pandas as pd

from config import FIGURE_DIR, OUTPUT_DIR, PROJECT_DIR, REPORT_DIR, TOP_N, ensure_directories


CHARTS = [
    (
        "样本覆盖与时间边界",
        "figure_1_sample_coverage.png",
        "季度面板共覆盖 41 个季度，可用股票数从 68 只逐步增至约 120 只；验证期与测试期边界保持严格分离。",
    ),
    (
        "因子相关性",
        "figure_2_factor_correlation.png",
        "动量与趋势变量存在明显相关，说明树模型可能在相关变量之间替代选择，岭回归则通过正则化缓解共线性。",
    ),
    (
        "测试期季度 Rank IC",
        "figure_3_quarterly_rank_ic.png",
        "三个模型的 Rank IC 均表现出显著时变性，单个季度的正向结果不能被解释为稳定规律。",
    ),
    (
        "模型平均净超额收益",
        "figure_4_model_excess_return.png",
        "三类 Top 30 组合的平均季度净超额收益均为负，提示绝对收益上涨主要来自同期市场环境。",
    ),
    (
        "累计净值对比",
        "figure_5_cumulative_nav.png",
        "决策树 Top 30 组合在测试期取得正收益，但累计净值持续低于同一研究样本的等权平均组合。",
    ),
    (
        "逐季度收益",
        "figure_6_quarterly_returns.png",
        "策略既有跑赢季度，也有明显落后季度；2024Q2 与 2025Q2 的市场上涨对累计结果影响较大。",
    ),
    (
        "回撤路径",
        "figure_7_drawdown.png",
        "Top 30 组合最大回撤约为 8.29%，路径风险低于只看期末累计收益时的直观感受。",
    ),
    (
        "随机森林特征重要度",
        "figure_8_random_forest_feature_importance.png",
        "126 日最大回撤、126 日收益率和价格相对 60 日均线重要度较高，但不应解释为因果关系。",
    ),
]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def pct(value: float, digits: int = 2, signed: bool = False) -> str:
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value * 100:.{digits}f}%"


def image_data_url(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def table_rows(frame: pd.DataFrame, columns: list[tuple[str, str]], formatters: dict[str, object] | None = None) -> str:
    formatters = formatters or {}
    rows: list[str] = []
    for record in frame.to_dict("records"):
        cells: list[str] = []
        for key, _ in columns:
            value = record[key]
            formatter = formatters.get(key)
            if formatter:
                value = formatter(value)
            cells.append(f"<td>{esc(value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "".join(rows)


def main() -> int:
    ensure_directories()
    summary = json.loads((OUTPUT_DIR / "analysis_summary.json").read_text(encoding="utf-8"))
    quality = json.loads((OUTPUT_DIR / "data_quality.json").read_text(encoding="utf-8"))
    model_metrics = pd.read_csv(OUTPUT_DIR / "model_metrics.csv")
    backtest = pd.read_csv(OUTPUT_DIR / "backtest_metrics.csv")
    quarterly = pd.read_csv(OUTPUT_DIR / "quarterly_returns.csv")
    importance = pd.read_csv(OUTPUT_DIR / "feature_importance.csv").head(12)

    best_model = summary["best_model_by_test_mean_rank_ic"]
    best_name = summary["best_model_zh"]
    best_quarterly = quarterly.loc[quarterly["model"] == best_model].sort_values("quarter_index")
    best_backtest = backtest.loc[backtest["model"] == best_model].iloc[0]

    model_columns = [
        ("model_zh", "模型"),
        ("mae_rank", "MAE"),
        ("r2_rank", "R²"),
        ("mean_rank_ic", "平均 Rank IC"),
        ("positive_ic_ratio", "IC>0 比例"),
    ]
    model_table = table_rows(
        model_metrics,
        model_columns,
        {
            "mae_rank": lambda x: f"{x:.3f}",
            "r2_rank": lambda x: f"{x:.3f}",
            "mean_rank_ic": lambda x: f"{x:.3f}",
            "positive_ic_ratio": lambda x: pct(x, 1),
        },
    )

    backtest_columns = [
        ("model_zh", "模型"),
        ("cumulative_return", "累计净收益"),
        ("annualized_return", "年化收益"),
        ("max_drawdown", "最大回撤"),
        ("information_ratio", "信息比率"),
    ]
    backtest_table = table_rows(
        backtest,
        backtest_columns,
        {
            "cumulative_return": pct,
            "annualized_return": pct,
            "max_drawdown": pct,
            "information_ratio": lambda x: f"{x:.3f}",
        },
    )

    quarter_columns = [
        ("quarter", "信号季度"),
        ("net_return", "策略净收益"),
        ("benchmark_return", "样本等权"),
        ("net_excess_return", "净超额"),
        ("turnover", "换手率"),
    ]
    quarter_table = table_rows(
        best_quarterly,
        quarter_columns,
        {
            "net_return": lambda x: pct(x, signed=True),
            "benchmark_return": lambda x: pct(x, signed=True),
            "net_excess_return": lambda x: pct(x, signed=True),
            "turnover": lambda x: pct(x, 1),
        },
    )

    importance_rows = "".join(
        f"<li><span>{esc(row.feature)}</span><strong>{row.mean_importance:.3f}</strong>"
        f"<i style=\"--w:{row.mean_importance / importance.mean_importance.max() * 100:.1f}%\"></i></li>"
        for row in importance.itertuples(index=False)
    )

    chart_cards = "".join(
        f"""
        <article class="chart-card reveal">
          <button class="chart-open" type="button" aria-label="放大查看：{esc(title)}">
            <img src="{image_data_url(FIGURE_DIR / filename)}" alt="{esc(title)}" loading="lazy">
          </button>
          <div class="chart-copy"><span>图 {index}</span><h3>{esc(title)}</h3><p>{esc(note)}</p></div>
        </article>
        """
        for index, (title, filename, note) in enumerate(CHARTS, start=1)
    )

    template = """<!doctype html>
<html lang="zh-CN" data-theme="light">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="TASK6 智能决策者：机器学习季度收益排序与 Top 30 策略回测">
  <title>TASK6 智能决策者｜机器学习策略回测</title>
  <style>
    :root{--ink:#172033;--muted:#64748b;--paper:#f4f7fb;--surface:#fff;--blue:#2563eb;--blue2:#173b76;--gold:#d97706;--pink:#7c3aed;--line:#dbe4ee;--good:#15803d;--bad:#b91c1c;--shadow:0 10px 30px rgba(15,23,42,.06);--radius:18px}
    *{box-sizing:border-box}html{scroll-behavior:smooth;color-scheme:light}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Microsoft YaHei","PingFang SC",system-ui,-apple-system,sans-serif;line-height:1.7}button,a{font:inherit}a{color:inherit}.skip{position:fixed;left:12px;top:-60px;background:var(--ink);color:white;padding:8px 14px;border-radius:8px;z-index:99}.skip:focus{top:12px}.wrap{width:min(1180px,calc(100% - 32px));margin:0 auto}
    main{min-width:0}.hero{padding:24px 0 58px;background:linear-gradient(135deg,#0f172a,#173b76);color:white}.task-nav{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:54px}.brand{font-size:13px;font-weight:800;letter-spacing:.08em;color:#dbeafe;text-transform:uppercase}.nav-links{display:flex;flex-wrap:wrap;gap:8px}.nav-links a{text-decoration:none;color:#dbeafe;border:1px solid rgba(219,234,254,.28);border-radius:999px;padding:6px 12px;font-size:13px;transition:.18s ease}.nav-links a:hover,.nav-links a.active{color:white;background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.48)}.eyebrow{display:inline-block;padding:4px 10px;border-radius:999px;background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:800}.hero h1{font-size:clamp(34px,5vw,58px);line-height:1.12;margin:16px 0 0;letter-spacing:-.03em;max-width:900px}.hero p{max-width:840px;color:#dbeafe;font-size:18px;margin:16px 0 0}.chips{display:flex;flex-wrap:wrap;gap:9px;margin-top:22px}.chip{border:1px solid rgba(219,234,254,.28);background:rgba(255,255,255,.1);color:#dbeafe;padding:5px 10px;border-radius:999px;font-size:12px;font-weight:700}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-top:-32px;position:relative;z-index:2}.metric{padding:22px;min-height:112px;border:1px solid var(--line);border-radius:18px;background:white;box-shadow:var(--shadow)}.metric strong{display:block;font-size:27px;line-height:1.25;color:var(--ink)}.metric span{display:block;color:var(--muted);font-size:13px;margin-top:6px}
    .content{width:min(1180px,calc(100% - 32px));margin:0 auto;padding:12px 0 96px}.section{scroll-margin-top:24px;padding:42px 0}.section-head{display:grid;grid-template-columns:80px 1fr;gap:20px;align-items:start;margin-bottom:24px}.section-num{font:800 13px/1 monospace;color:var(--gold);letter-spacing:.12em}.section h2{font-size:28px;line-height:1.3;margin:0}.section-intro{color:#475569;max-width:820px;margin:8px 0 0}.verdict{display:grid;grid-template-columns:1.15fr .85fr;gap:18px}.verdict-main,.verdict-side,.phase,.rule,.chart-card,.table-wrap,.caveat{border:1px solid var(--line);background:var(--surface);box-shadow:var(--shadow)}.verdict-main,.verdict-side{border-radius:18px;padding:28px}.verdict-main{border-left:4px solid var(--blue)}.flag{display:inline-block;color:white;background:var(--bad);padding:5px 10px;border-radius:999px;font-size:12px;font-weight:800}.big-number{font-size:clamp(44px,7vw,72px);line-height:1;margin:18px 0 8px;color:var(--blue2);font-weight:900;letter-spacing:-.05em}.verdict h3{margin:0 0 10px;font-size:22px}.verdict p{color:var(--muted)}.compare{display:grid;gap:14px;margin-top:22px}.compare div{display:grid;grid-template-columns:110px 1fr 68px;gap:10px;align-items:center;font-size:13px}.bar{height:10px;border-radius:99px;background:var(--line);overflow:hidden}.bar i{display:block;height:100%;border-radius:inherit;background:var(--blue)}.bar.gold i{background:var(--gold)}
    .timeline{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.phase{position:relative;padding:24px;border-radius:18px}.phase:before{content:"";display:block;width:42px;height:5px;border-radius:99px;background:var(--blue);margin-bottom:18px}.phase:nth-child(2):before{background:var(--gold)}.phase:nth-child(3):before{background:var(--pink)}.phase b{font-size:18px}.phase span{display:block;color:var(--muted);font-size:14px}.rules{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:18px}.rule{display:flex;gap:14px;padding:18px;border-radius:16px}.rule b{display:grid;place-items:center;flex:0 0 32px;height:32px;border-radius:10px;background:#dbeafe;color:#1d4ed8}
    .table-wrap{overflow:auto;border-radius:16px;margin-top:18px}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:13px 16px;border-bottom:1px solid var(--line);white-space:nowrap}th{font-size:12px;letter-spacing:.04em;color:#334155;background:#eaf1fb}tbody tr:last-child td{border-bottom:0}tbody tr:hover{background:#f8fafc}.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.chart-card{overflow:hidden;border-radius:18px}.chart-open{display:block;width:100%;padding:0;border:0;background:white;cursor:zoom-in}.chart-open img{display:block;width:100%;aspect-ratio:1.52/1;object-fit:contain}.chart-copy{padding:20px}.chart-copy span{color:var(--gold);font-size:12px;font-weight:900}.chart-copy h3{margin:3px 0 8px;font-size:19px}.chart-copy p{margin:0;color:var(--muted);font-size:14px}.chart-card:first-child{grid-column:1/-1}.chart-card:first-child .chart-open img{aspect-ratio:2/1}
    .importance{list-style:none;padding:0;margin:0;display:grid;gap:10px}.importance li{display:grid;grid-template-columns:minmax(160px,1fr) 50px 2fr;align-items:center;gap:12px}.importance span{font-family:ui-monospace,Consolas,monospace;font-size:13px}.importance strong{font-size:13px}.importance i{height:10px;border-radius:99px;background:linear-gradient(90deg,var(--gold) var(--w),var(--line) var(--w))}.split{display:grid;grid-template-columns:1fr 1fr;gap:22px}.caveats{display:grid;gap:10px}.caveat{padding:18px;border-left:4px solid var(--gold);border-radius:0 14px 14px 0}.caveat b{display:block}.caveat p{margin:4px 0 0;color:var(--muted);font-size:14px}.downloads{display:flex;flex-wrap:wrap;gap:12px}.download{display:inline-flex;align-items:center;gap:9px;text-decoration:none;border:1px solid var(--line);background:var(--surface);padding:12px 16px;border-radius:14px;font-weight:700}.download:hover{border-color:var(--blue);color:var(--blue2)}
    dialog{width:min(1100px,94vw);max-height:92vh;border:1px solid var(--line);border-radius:22px;padding:14px;background:var(--surface);color:var(--ink);box-shadow:var(--shadow)}dialog::backdrop{background:rgba(9,18,22,.78);backdrop-filter:blur(6px)}dialog img{display:block;width:100%;max-height:80vh;object-fit:contain;background:white;border-radius:14px}.dialog-close{position:absolute;right:24px;top:24px;border:0;border-radius:999px;background:var(--ink);color:white;width:38px;height:38px;cursor:pointer}.reveal{opacity:1;transform:none}.js .reveal{opacity:0;transform:translateY(18px);transition:.55s ease}.js .reveal.visible{opacity:1;transform:none}
    @media(max-width:900px){.task-nav{align-items:flex-start;flex-direction:column;margin-bottom:42px}.metrics{grid-template-columns:repeat(2,1fr)}.verdict,.split{grid-template-columns:1fr}.timeline{grid-template-columns:1fr}.charts{grid-template-columns:1fr}.chart-card:first-child{grid-column:auto}.chart-card:first-child .chart-open img,.chart-open img{aspect-ratio:auto}.rules{grid-template-columns:1fr}}
    @media(max-width:540px){.hero p{font-size:16px}.nav-links a{padding:5px 9px}.metrics{grid-template-columns:1fr 1fr}.metric strong{font-size:23px}.section-head{grid-template-columns:1fr;gap:8px}.section{padding:34px 0}.compare div{grid-template-columns:86px 1fr 58px}.importance li{grid-template-columns:1fr 44px}.importance i{grid-column:1/-1}}
    @media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.js .reveal{opacity:1;transform:none;transition:none}}
    @media print{.task-nav,.chart-open:after{display:none}.hero{padding:30px}.section{break-inside:avoid}.content{width:auto;padding:20px}.chart-card{box-shadow:none}.charts{grid-template-columns:1fr 1fr}}
  </style>
  <script>document.documentElement.classList.add('js')</script>
</head>
<body>
  <a class="skip" href="#main">跳到正文</a>
  <main id="main">
    <header class="hero">
      <div class="wrap">
        <nav class="task-nav" aria-label="工作坊任务导航"><div class="brand">PKU Workshop · Quantitative Trading</div><div class="nav-links"><a href="../../Task1/web/index.html">TASK1</a><a href="../../Task2/web/index.html">TASK2</a><a href="../../Task3/web/index.html">TASK3</a><a href="../../Task4/web/index.html">TASK4</a><a href="../../TASK5/web/index.html">TASK5</a><a href="../../TASK6/web/index.html" class="active" aria-current="page">TASK6</a></div></nav>
        <span class="eyebrow">PKU Workshop · TASK6</span>
        <h1>用机器学习定制<br>专属量化策略</h1>
        <p>基于当前中证 300 成分列表等距抽取的 120 只股票，以 18 个动量、趋势、风险和流动性因子预测下一季度收益排序，构建 Top 30 等权组合。</p>
        <div class="chips"><span class="chip">后复权日行情</span><span class="chip">严格时间切分</span><span class="chip">扩展窗口重训</span><span class="chip">单边成本 0.2%</span></div>
      </div>
    </header>
    <div class="wrap metrics">
      <div class="metric"><strong>@@STOCKS@@</strong><span>研究股票</span></div><div class="metric"><strong>@@FACTORS@@</strong><span>模型因子</span></div><div class="metric"><strong>@@QUARTERS@@</strong><span>测试季度</span></div><div class="metric"><strong>Top @@TOPN@@</strong><span>等权持仓</span></div>
    </div>
    <div class="content">
        <section class="section" id="verdict">
          <div class="section-head"><span class="section-num">01 / VERDICT</span><div><h2>结论先行</h2><p class="section-intro">策略在测试期取得正的绝对收益，但未跑赢同一研究样本的等权平均；机器学习排序信号并不稳定。</p></div></div>
          <div class="verdict">
            <article class="verdict-main reveal"><span class="flag">未跑赢基准</span><div class="big-number">@@CUM_RETURN@@</div><h3>@@BEST_MODEL@@ Top 30 累计净收益</h3><p>同期样本等权组合累计收益为 <strong>@@BENCH_RETURN@@</strong>。测试期只有 8 个季度，结果应视为教学型样本外证据。</p><div class="compare"><div><span>策略</span><span class="bar"><i style="width:@@STRATEGY_BAR@@%"></i></span><strong>@@CUM_RETURN@@</strong></div><div><span>样本等权</span><span class="bar gold"><i style="width:100%"></i></span><strong>@@BENCH_RETURN@@</strong></div></div></article>
            <article class="verdict-side reveal"><h3>预测质量</h3><div class="big-number">@@RANK_IC@@</div><p>最佳模型测试期平均 Rank IC；IC 为正的季度占 <strong>@@POS_IC@@</strong>。</p><hr style="border:0;border-top:1px solid var(--line);margin:24px 0"><h3>风险结果</h3><p>年化净收益 <strong>@@ANN_RETURN@@</strong><br>最大回撤 <strong>@@MAX_DD@@</strong><br>信息比率 <strong>@@IR@@</strong></p></article>
          </div>
        </section>
        <section class="section" id="method">
          <div class="section-head"><span class="section-num">02 / METHOD</span><div><h2>研究设计</h2><p class="section-intro">所有特征均在季度末形成，下一季度首个可用交易日开盘建仓，再下一季度首个可用交易日开盘退出，避免把未来信息带入信号。</p></div></div>
          <div class="timeline"><div class="phase reveal"><b>训练集</b><span>2016Q1—2023Q1</span><strong>29 个季度 · 2,851 行</strong></div><div class="phase reveal"><b>验证集</b><span>2023Q2—2024Q1</span><strong>4 个季度 · 471 行</strong></div><div class="phase reveal"><b>测试集</b><span>2024Q2—2026Q1</span><strong>8 个季度 · 959 行</strong></div></div>
          <div class="rules"><div class="rule"><b>1</b><span>季度内 1%/99% 分位缩尾，中位数填补缺失，再转为横截面百分位。</span></div><div class="rule"><b>2</b><span>每个测试季度只使用此前已完成样本，采用扩展窗口逐季重训。</span></div><div class="rule"><b>3</b><span>预测目标为未来季度收益的横截面百分位，而非单纯最小化点预测误差。</span></div><div class="rule"><b>4</b><span>基准使用完全相同股票池和交易价格的样本等权平均，便于公平比较。</span></div></div>
        </section>
        <section class="section" id="models">
          <div class="section-head"><span class="section-num">03 / MODELS</span><div><h2>三类模型比较</h2><p class="section-intro">岭回归提供线性基准，决策树捕捉非线性规则，随机森林通过多树平均降低单树方差。</p></div></div>
          <h3>预测层指标</h3><div class="table-wrap"><table><thead><tr>@@MODEL_HEAD@@</tr></thead><tbody>@@MODEL_TABLE@@</tbody></table></div>
          <h3 style="margin-top:30px">策略层指标</h3><div class="table-wrap"><table><thead><tr>@@BACKTEST_HEAD@@</tr></thead><tbody>@@BACKTEST_TABLE@@</tbody></table></div>
        </section>
        <section class="section" id="charts">
          <div class="section-head"><span class="section-num">04 / EVIDENCE</span><div><h2>图形证据</h2><p class="section-intro">点击任意图形可放大。每张图均配有结论性解读，避免只展示图表而不回答研究问题。</p></div></div>
          <div class="charts">@@CHART_CARDS@@</div>
        </section>
        <section class="section" id="returns">
          <div class="section-head"><span class="section-num">05 / BACKTEST</span><div><h2>逐季度回测</h2><p class="section-intro">@@BEST_MODEL@@是三类模型中测试期平均 Rank IC 相对最高者，但平均值仍为负。下表展示其 Top 30 组合逐季净收益、基准和换手率。</p></div></div>
          <div class="table-wrap"><table><thead><tr>@@QUARTER_HEAD@@</tr></thead><tbody>@@QUARTER_TABLE@@</tbody></table></div>
          <div class="split" style="margin-top:28px"><div><h3>随机森林重要因子</h3><ol class="importance">@@IMPORTANCE@@</ol></div><div class="caveats"><div class="caveat"><b>成本敏感性</b><p>单边成本由 0.1% 提高至 0.3% 后，决策树累计净收益由 30.78% 降至 29.31%，高换手会持续侵蚀收益。</p></div><div class="caveat"><b>统计与投资表现不同步</b><p>Rank IC、净超额收益和最大回撤需要联合判断；预测误差较小不代表组合必然跑赢。</p></div></div></div>
        </section>
        <section class="section" id="limits">
          <div class="section-head"><span class="section-num">06 / LIMITS</span><div><h2>局限与复现</h2><p class="section-intro">本网页与 PDF、DOCX、Notebook 使用同一份已校验结果。结论可复现，但仍受数据和执行假设限制。</p></div></div>
          <div class="caveats"><div class="caveat"><b>幸存者与样本选择偏差</b><p>使用抓取日当前中证 300 成分列表中的 120 只股票回溯历史，并非逐季真实成分股。</p></div><div class="caveat"><b>交易可达性简化</b><p>历史 ST、停牌、涨跌停、佣金结构、印花税变化、滑点和冲击成本未被完整模拟。</p></div><div class="caveat"><b>数据源字段缺口</b><p>腾讯备用记录缺少成交额和换手率，相关因子按当季横截面中位数进行中性填充。</p></div><div class="caveat"><b>样本期有限</b><p>测试期只有 8 个季度，不能据此证明长期稳定性或未来收益。</p></div></div>
          <h3 style="margin-top:32px">相关交付件</h3><div class="downloads"><a class="download" href="姓名TASK6.pdf">PDF 报告</a><a class="download" href="姓名TASK6.docx">DOCX 源稿</a><a class="download" href="../TASK6_walkthrough.ipynb">分析 Notebook</a><a class="download" href="../SPEC.md">实施规格</a></div>
          <p style="margin-top:28px;color:var(--muted);font-size:13px">数据覆盖 @@DATE_MIN@@ 至 @@DATE_MAX@@，共 @@ROWS@@ 条日频记录。最终自动校验 67/67 通过。本页面仅用于课程研究，不构成投资建议。</p>
        </section>
    </div>
  </main>
  <dialog id="chartDialog"><button class="dialog-close" type="button" aria-label="关闭">×</button><img alt="放大的统计图"></dialog>
  <script>
    const dialog=document.querySelector('#chartDialog'),dialogImg=dialog.querySelector('img');document.querySelectorAll('.chart-open').forEach(b=>b.addEventListener('click',()=>{const img=b.querySelector('img');dialogImg.src=img.src;dialogImg.alt=img.alt;dialog.showModal()}));dialog.querySelector('.dialog-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
    const reveals=document.querySelectorAll('.reveal');const ro=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');ro.unobserve(e.target)}}),{threshold:.08});reveals.forEach(x=>ro.observe(x));
  </script>
</body></html>"""

    replacements = {
        "@@STOCKS@@": str(quality["raw_stock_count"]),
        "@@FACTORS@@": str(quality["feature_count"]),
        "@@QUARTERS@@": str(len(quality["test_quarters"])),
        "@@TOPN@@": str(TOP_N),
        "@@CUM_RETURN@@": pct(summary["best_strategy_cumulative_net_return"]),
        "@@BENCH_RETURN@@": pct(summary["benchmark_cumulative_return"]),
        "@@BEST_MODEL@@": esc(best_name),
        "@@STRATEGY_BAR@@": f"{summary['best_strategy_cumulative_net_return'] / summary['benchmark_cumulative_return'] * 100:.1f}",
        "@@RANK_IC@@": f"{summary['best_mean_rank_ic']:.3f}",
        "@@POS_IC@@": pct(summary["best_positive_ic_ratio"], 1),
        "@@ANN_RETURN@@": pct(best_backtest["annualized_return"]),
        "@@MAX_DD@@": pct(best_backtest["max_drawdown"]),
        "@@IR@@": f"{best_backtest['information_ratio']:.3f}",
        "@@MODEL_HEAD@@": "".join(f"<th>{esc(label)}</th>" for _, label in model_columns),
        "@@MODEL_TABLE@@": model_table,
        "@@BACKTEST_HEAD@@": "".join(f"<th>{esc(label)}</th>" for _, label in backtest_columns),
        "@@BACKTEST_TABLE@@": backtest_table,
        "@@CHART_CARDS@@": chart_cards,
        "@@QUARTER_HEAD@@": "".join(f"<th>{esc(label)}</th>" for _, label in quarter_columns),
        "@@QUARTER_TABLE@@": quarter_table,
        "@@IMPORTANCE@@": importance_rows,
        "@@DATE_MIN@@": esc(quality["raw_date_min"]),
        "@@DATE_MAX@@": esc(quality["raw_date_max"]),
        "@@ROWS@@": f"{quality['raw_daily_rows']:,}",
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    template = "\n".join(line.rstrip() for line in template.splitlines()) + "\n"

    destination = REPORT_DIR / "姓名TASK6.html"
    destination.write_text(template, encoding="utf-8")
    web_destination = PROJECT_DIR / "web" / "index.html"
    web_destination.write_text(template, encoding="utf-8")
    print(f"Standalone web report created: {destination}")
    print(f"GitHub Pages report created: {web_destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
