const taskLinks = [
  ["TASK1", "https://lizpink.github.io/PKU-WorkShop-202607/Task1/web/"],
  ["TASK2", "https://lizpink.github.io/PKU-WorkShop-202607/Task2/web/"],
  ["TASK3", "https://lizpink.github.io/PKU-WorkShop-202607/Task3/web/"],
  ["TASK4", "https://lizpink.github.io/PKU-WorkShop-202607/Task4/web/"],
  ["TASK5", "https://lizpink.github.io/PKU-WorkShop-202607/TASK5/web/"],
] as const;

const modelRows = [
  ["岭回归", "0.255", "-0.053", "-0.137", "25.0%"],
  ["决策树", "0.258", "-0.092", "-0.080", "50.0%"],
  ["随机森林", "0.254", "-0.033", "-0.097", "37.5%"],
] as const;

const backtestRows = [
  ["决策树", "30.04%", "14.04%", "-8.29%", "-1.039"],
  ["随机森林", "22.72%", "10.78%", "-7.14%", "-1.193"],
  ["岭回归", "9.67%", "4.72%", "-10.46%", "-1.401"],
] as const;

const charts = [
  ["样本覆盖与时间边界", "figure_1_sample_coverage.png", "季度面板共覆盖 41 个季度；验证期与测试期边界保持严格分离。"],
  ["因子相关性", "figure_2_factor_correlation.png", "动量与趋势变量存在明显相关，正则化与集成方法用于缓解冗余。"],
  ["测试期季度 Rank IC", "figure_3_quarterly_rank_ic.png", "三个模型的 Rank IC 均明显时变，单季正向结果并不代表稳定规律。"],
  ["模型平均净超额收益", "figure_4_model_excess_return.png", "三类 Top 30 组合的平均季度净超额收益均为负。"],
  ["累计净值对比", "figure_5_cumulative_nav.png", "决策树组合取得正收益，但累计净值低于同一股票池的等权平均。"],
  ["逐季度收益", "figure_6_quarterly_returns.png", "策略既有跑赢季度，也有明显落后季度，结果依赖市场环境。"],
  ["回撤路径", "figure_7_drawdown.png", "Top 30 组合最大回撤约为 8.29%，不能只看期末累计收益。"],
  ["随机森林特征重要度", "figure_8_random_forest_feature_importance.png", "126 日最大回撤等因子较重要，但重要度不代表因果关系。"],
] as const;

export default function Home() {
  return (
    <>
      <a className="skip-link" href="#main">跳到正文</a>
      <header className="hero">
        <div className="wrap">
          <nav className="task-nav" aria-label="工作坊任务导航">
            <div className="brand">PKU Workshop · Quantitative Trading</div>
            <div className="nav-links">
              {taskLinks.map(([label, href]) => (
                <a href={href} key={label}>{label}</a>
              ))}
              <a className="active" aria-current="page" href="#main">TASK6</a>
            </div>
          </nav>
          <span className="tag">PKU WORKSHOP · TASK6</span>
          <h1>用机器学习定制<br />专属量化策略</h1>
          <p>
            基于当前中证 300 成分列表等距抽取的 120 只股票，以 18 个动量、趋势、风险和流动性因子预测下一季度收益排序，构建 Top 30 等权组合。
          </p>
          <div className="pill-row hero-pills" aria-label="研究设定">
            <span className="pill">后复权日行情</span>
            <span className="pill">严格时间切分</span>
            <span className="pill">扩展窗口重训</span>
            <span className="pill">单边成本 0.2%</span>
          </div>
        </div>
      </header>

      <main id="main">
        <div className="wrap metrics" aria-label="研究概览">
          <div className="metric"><span>研究股票</span><strong>120</strong></div>
          <div className="metric"><span>模型因子</span><strong>18</strong></div>
          <div className="metric"><span>测试季度</span><strong>8</strong></div>
          <div className="metric"><span>等权持仓</span><strong>Top 30</strong></div>
        </div>

        <section>
          <div className="wrap">
            <div className="section-heading">
              <span>01 / VERDICT</span>
              <div>
                <h2>结论先行</h2>
                <p>策略取得正的绝对收益，但未跑赢同一研究样本的等权平均；机器学习排序信号并不稳定。</p>
              </div>
            </div>
            <div className="verdict-grid">
              <article className="card verdict-card">
                <span className="status">未跑赢基准</span>
                <strong className="headline-number">30.04%</strong>
                <h3>决策树 Top 30 累计净收益</h3>
                <p>同期样本等权组合累计收益为 48.42%。测试期只有 8 个季度，结果应视为教学型样本外证据。</p>
                <div className="comparison" aria-label="策略与基准累计收益比较">
                  <div><span>策略</span><i><b style={{ width: "62%" }} /></i><strong>30.04%</strong></div>
                  <div><span>样本等权</span><i><b className="benchmark" style={{ width: "100%" }} /></i><strong>48.42%</strong></div>
                </div>
              </article>
              <article className="card risk-card">
                <h3>预测质量</h3>
                <strong className="headline-number small">-0.080</strong>
                <p>最佳模型测试期平均 Rank IC；IC 为正的季度占 50.0%。</p>
                <hr />
                <h3>风险结果</h3>
                <dl>
                  <div><dt>年化净收益</dt><dd>14.04%</dd></div>
                  <div><dt>最大回撤</dt><dd>-8.29%</dd></div>
                  <div><dt>信息比率</dt><dd>-1.039</dd></div>
                </dl>
              </article>
            </div>
          </div>
        </section>

        <section>
          <div className="wrap">
            <div className="section-heading">
              <span>02 / METHOD</span>
              <div><h2>研究设计</h2><p>特征在季度末形成，下一季度首个可用交易日开盘建仓，避免把未来信息带入信号。</p></div>
            </div>
            <div className="grid">
              <article className="card phase"><span>训练集</span><strong>2016Q1—2023Q1</strong><p>29 个季度 · 2,851 行</p></article>
              <article className="card phase"><span>验证集</span><strong>2023Q2—2024Q1</strong><p>4 个季度 · 471 行</p></article>
              <article className="card phase"><span>测试集</span><strong>2024Q2—2026Q1</strong><p>8 个季度 · 959 行</p></article>
            </div>
            <div className="rules">
              <article className="card rule"><b>1</b><p>季度内缩尾、缺失值填补，再转为横截面百分位。</p></article>
              <article className="card rule"><b>2</b><p>每个测试季度只使用此前已完成样本，逐季扩展窗口重训。</p></article>
              <article className="card rule"><b>3</b><p>预测未来季度收益的横截面百分位，而非只追求点预测误差。</p></article>
              <article className="card rule"><b>4</b><p>基准采用相同股票池和交易价格的样本等权平均。</p></article>
            </div>
          </div>
        </section>

        <section>
          <div className="wrap">
            <div className="section-heading">
              <span>03 / MODELS</span>
              <div><h2>三类模型比较</h2><p>预测指标与策略指标必须联合判断，较低误差不等于更好的投资表现。</p></div>
            </div>
            <h3>预测层指标</h3>
            <div className="table-shell">
              <table className="data-table">
                <thead><tr><th>模型</th><th>MAE</th><th>R²</th><th>平均 Rank IC</th><th>IC&gt;0 比例</th></tr></thead>
                <tbody>{modelRows.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>
            <h3 className="subheading">策略层指标</h3>
            <div className="table-shell">
              <table className="data-table">
                <thead><tr><th>模型</th><th>累计净收益</th><th>年化收益</th><th>最大回撤</th><th>信息比率</th></tr></thead>
                <tbody>{backtestRows.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody>
              </table>
            </div>
          </div>
        </section>

        <section>
          <div className="wrap">
            <div className="section-heading">
              <span>04 / EVIDENCE</span>
              <div><h2>图形证据</h2><p>每张图都对应一个研究问题；点击图形可以在新窗口查看原始尺寸。</p></div>
            </div>
            <div className="chart-list">
              {charts.map(([title, filename, note], index) => (
                <article className={`chart-card ${index === 0 ? "wide" : ""}`} key={filename}>
                  <a href={`/figures/${filename}`} target="_blank" rel="noreferrer">
                    <img src={`/figures/${filename}`} alt={title} loading="lazy" />
                  </a>
                  <div className="chart-copy"><span>图 {index + 1}</span><h3>{title}</h3><p>{note}</p></div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section>
          <div className="wrap">
            <div className="section-heading">
              <span>05 / LIMITS</span>
              <div><h2>局限与复现</h2><p>结论可复现，但仍受幸存者偏差、交易可达性简化和有限样本期约束。</p></div>
            </div>
            <div className="grid two">
              <article className="card warning"><h3>幸存者与样本选择偏差</h3><p>使用抓取日当前中证 300 成分列表中的 120 只股票回溯历史，并非逐季真实成分股。</p></article>
              <article className="card warning"><h3>交易可达性简化</h3><p>历史 ST、停牌、涨跌停、滑点和冲击成本未被完整模拟。</p></article>
              <article className="card warning"><h3>数据字段缺口</h3><p>备用数据源缺少成交额和换手率，相关因子按横截面中位数填补。</p></article>
              <article className="card warning"><h3>样本期有限</h3><p>测试期只有 8 个季度，不能据此证明长期稳定性或未来收益。</p></article>
            </div>
            <p className="note">数据覆盖 2015-01-05 至 2026-07-03，共 294,312 条日频记录。本页面仅用于课程研究，不构成投资建议。</p>
          </div>
        </section>
      </main>

      <footer><div className="wrap">数据：AkShare / 中证指数成分与后复权日行情｜策略：季度排序 / Top 30 等权｜TASK6</div></footer>
    </>
  );
}
