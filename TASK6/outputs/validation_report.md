# TASK6 Validation Report

## Overall Assessment: Ready to share

### Methodology Review

本校验覆盖季度主键、信号/交易时间顺序、时间划分、Rank IC、Top 30 持仓、权重、交易成本、累计收益、最大回撤、统计图、DOCX 排版和 PDF 内容。

### Issues Found

未发现阻止提交的自动校验问题。

### Calculation Spot-Checks

- [PASS] Files/quarterly_panel.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\data\processed\quarterly_panel.csv
- [PASS] Files/test_predictions.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\test_predictions.csv
- [PASS] Files/model_metrics.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\model_metrics.csv
- [PASS] Files/quarterly_ic.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\quarterly_ic.csv
- [PASS] Files/quarterly_returns.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\quarterly_returns.csv
- [PASS] Files/holdings.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\holdings.csv
- [PASS] Files/backtest_metrics.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\backtest_metrics.csv
- [PASS] Files/cost_sensitivity.csv: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\cost_sensitivity.csv
- [PASS] Files/data_quality.json: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\data_quality.json
- [PASS] Files/selected_parameters.json: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\outputs\selected_parameters.json
- [PASS] Data/季度面板主键唯一: duplicates=0
- [PASS] Data/信号早于进场且进场早于退出: signal < entry < exit
- [PASS] Data/18 个模型因子完整: features=18
- [PASS] Data/数据质量元数据一致: metadata=4281, actual=4281
- [PASS] Method/时间划分严格递增: 2023Q1 < 2023Q2 <= 2024Q1 < 2024Q2
- [PASS] Method/测试集为 8 个季度: quarters=8
- [PASS] Prediction/ridge 季度 Rank IC 独立复算: max_diff=5.00e-09
- [PASS] Prediction/ridge 平均 Rank IC 一致: saved=-0.13713377, recomputed=-0.13713377
- [PASS] Portfolio/ridge 每季度 Top 30: {8098: 30, 8099: 30, 8100: 30, 8101: 30, 8102: 30, 8103: 30, 8104: 30, 8105: 30}
- [PASS] Portfolio/ridge 权重和为 1: range=1.00000000..1.00000000
- [PASS] Portfolio/ridge Top 30 收益复算: max_diff=5.00e-11
- [PASS] Portfolio/ridge 净收益成本公式: net = gross - cost
- [PASS] Performance/ridge 累计收益复算: saved=0.09665727, recomputed=0.09665727
- [PASS] Performance/ridge 最大回撤复算: saved=-0.10464056, recomputed=-0.10464056
- [PASS] Prediction/decision_tree 季度 Rank IC 独立复算: max_diff=4.39e-09
- [PASS] Prediction/decision_tree 平均 Rank IC 一致: saved=-0.07972374, recomputed=-0.07972374
- [PASS] Portfolio/decision_tree 每季度 Top 30: {8098: 30, 8099: 30, 8100: 30, 8101: 30, 8102: 30, 8103: 30, 8104: 30, 8105: 30}
- [PASS] Portfolio/decision_tree 权重和为 1: range=1.00000000..1.00000000
- [PASS] Portfolio/decision_tree Top 30 收益复算: max_diff=5.33e-11
- [PASS] Portfolio/decision_tree 净收益成本公式: net = gross - cost
- [PASS] Performance/decision_tree 累计收益复算: saved=0.30040039, recomputed=0.30040039
- [PASS] Performance/decision_tree 最大回撤复算: saved=-0.08290180, recomputed=-0.08290180
- [PASS] Prediction/random_forest 季度 Rank IC 独立复算: max_diff=4.60e-09
- [PASS] Prediction/random_forest 平均 Rank IC 一致: saved=-0.09680494, recomputed=-0.09680494
- [PASS] Portfolio/random_forest 每季度 Top 30: {8098: 30, 8099: 30, 8100: 30, 8101: 30, 8102: 30, 8103: 30, 8104: 30, 8105: 30}
- [PASS] Portfolio/random_forest 权重和为 1: range=1.00000000..1.00000000
- [PASS] Portfolio/random_forest Top 30 收益复算: max_diff=5.00e-11
- [PASS] Portfolio/random_forest 净收益成本公式: net = gross - cost
- [PASS] Performance/random_forest 累计收益复算: saved=0.22718249, recomputed=0.22718249
- [PASS] Performance/random_forest 最大回撤复算: saved=-0.07135046, recomputed=-0.07135046
- [PASS] Figure/figure_1_sample_coverage.png: 1768x1181px, 127913 bytes
- [PASS] Figure/figure_2_factor_correlation.png: 1984x1788px, 201701 bytes
- [PASS] Figure/figure_3_quarterly_rank_ic.png: 1785x1177px, 227462 bytes
- [PASS] Figure/figure_4_model_excess_return.png: 1568x1092px, 86922 bytes
- [PASS] Figure/figure_5_cumulative_nav.png: 1785x1177px, 167298 bytes
- [PASS] Figure/figure_6_quarterly_returns.png: 1788x1177px, 114452 bytes
- [PASS] Figure/figure_7_drawdown.png: 1751x1121px, 148777 bytes
- [PASS] Figure/figure_8_random_forest_feature_importance.png: 1924x1240px, 130924 bytes
- [PASS] DOCX/文件存在: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\report\姓名TASK6.docx
- [PASS] DOCX/正式标题: TASK6 智能决策者：用机器学习定制专属策略
- [PASS] DOCX/8 幅统计图: actual=8
- [PASS] DOCX/7 张核心表: actual=7
- [PASS] DOCX/图号完整: figure_numbers=['1', '2', '3', '4', '5', '6', '7', '8']
- [PASS] DOCX/A4 页面: 21.00x29.70cm
- [PASS] DOCX/正文宋体: SimSun
- [PASS] DOCX/正文五号: 10.5pt
- [PASS] DOCX/正文 1.5 倍行距: 1.5
- [PASS] DOCX/正文 0 段间距: before=0, after=0
- [PASS] DOCX/正文两端对齐: JUSTIFY (3)
- [PASS] DOCX/无未替换占位符: No [[...]] markers
- [PASS] DOCX/图片替代文本: alt_count=8
- [PASS] PDF/文件存在: C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK6\report\姓名TASK6.pdf
- [PASS] PDF/页数合理: pages=15
- [PASS] PDF/全部页面 A4: pages=15
- [PASS] PDF/正式标题可检索: TASK6 智能决策者：用机器学习定制专属策略
- [PASS] PDF/核心任务内容完整: 机器学习交易策略, 自变量, 应变量, 决策树, 随机森林, Rank IC, Top 30, 回测
- [PASS] PDF/8 个图号可检索: figures=['1', '2', '3', '4', '5', '6', '7', '8']

### Required Caveats for Readers

- 当前中证 300 成分列表中等距抽取的 120 只股票被回溯使用，存在幸存者与样本选择偏差；基准是研究样本等权平均而非官方指数收益。
- 历史 ST、停牌、涨跌停和冲击成本未完整模拟，成本为情景假设。
- 测试期只有 8 个季度，结果不构成未来收益保证或投资建议。