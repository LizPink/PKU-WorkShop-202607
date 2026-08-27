# Validation Report

## Overall Assessment: Ready to share

### Methodology Review

校验对象为 TASK5 乳腺癌二分类实验。正类固定为恶性（1），测试集为分层抽样得到的 20% 数据。评价值从逐样本预测文件独立复算，AUC 使用正类概率而非 0/1 分类结果。

### Issues Found

未发现阻止分享或提交的计算问题。

### Calculation Spot-Checks

- [PASS] 文件存在：metrics.csv：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\metrics.csv
- [PASS] 文件存在：predictions.csv：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\predictions.csv
- [PASS] 文件存在：split_summary.csv：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\split_summary.csv
- [PASS] 文件存在：roc_curve_points.csv：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\roc_curve_points.csv
- [PASS] 文件存在：data_quality.json：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\data_quality.json
- [PASS] 文件存在：model_parameters.json：C:\Users\13377\Desktop\PKU-WorkShop-202607\TASK5\outputs\model_parameters.json
- [PASS] 测试集样本数为 114：实际 114 条
- [PASS] 数据集无缺失值：缺失值 0 个
- [PASS] 三个模型均有评价结果：logistic_regression, decision_tree, random_forest
- [PASS] 预测结果包含两个类别：类别数 2
- [PASS] 逻辑回归 accuracy 独立复算一致：保存值=0.97368421，复算值=0.97368421
- [PASS] 逻辑回归 precision 独立复算一致：保存值=0.97560976，复算值=0.97560976
- [PASS] 逻辑回归 recall 独立复算一致：保存值=0.95238095，复算值=0.95238095
- [PASS] 逻辑回归 specificity 独立复算一致：保存值=0.98611111，复算值=0.98611111
- [PASS] 逻辑回归 f1 独立复算一致：保存值=0.96385542，复算值=0.96385542
- [PASS] 逻辑回归 roc_auc 独立复算一致：保存值=0.99603175，复算值=0.99603175
- [PASS] 逻辑回归 混淆矩阵计数一致：TN=71, FP=1, FN=2, TP=40
- [PASS] 逻辑回归 概率在 [0,1] 内：min=0.000000, max=1.000000
- [PASS] 逻辑回归 AUC 区间包含点估计：95% CI=[0.9872, 1.0000]，AUC=0.9960
- [PASS] 决策树 accuracy 独立复算一致：保存值=0.91228070，复算值=0.91228070
- [PASS] 决策树 precision 独立复算一致：保存值=0.90000000，复算值=0.90000000
- [PASS] 决策树 recall 独立复算一致：保存值=0.85714286，复算值=0.85714286
- [PASS] 决策树 specificity 独立复算一致：保存值=0.94444444，复算值=0.94444444
- [PASS] 决策树 f1 独立复算一致：保存值=0.87804878，复算值=0.87804878
- [PASS] 决策树 roc_auc 独立复算一致：保存值=0.92030423，复算值=0.92030423
- [PASS] 决策树 混淆矩阵计数一致：TN=68, FP=4, FN=6, TP=36
- [PASS] 决策树 概率在 [0,1] 内：min=0.000000, max=1.000000
- [PASS] 决策树 AUC 区间包含点估计：95% CI=[0.8466, 0.9789]，AUC=0.9203
- [PASS] 随机森林 accuracy 独立复算一致：保存值=0.97368421，复算值=0.97368421
- [PASS] 随机森林 precision 独立复算一致：保存值=1.00000000，复算值=1.00000000
- [PASS] 随机森林 recall 独立复算一致：保存值=0.92857143，复算值=0.92857143
- [PASS] 随机森林 specificity 独立复算一致：保存值=1.00000000，复算值=1.00000000
- [PASS] 随机森林 f1 独立复算一致：保存值=0.96296296，复算值=0.96296296
- [PASS] 随机森林 roc_auc 独立复算一致：保存值=0.99735450，复算值=0.99735450
- [PASS] 随机森林 混淆矩阵计数一致：TN=72, FP=0, FN=3, TP=39
- [PASS] 随机森林 概率在 [0,1] 内：min=0.000000, max=1.000000
- [PASS] 随机森林 AUC 区间包含点估计：95% CI=[0.9910, 1.0000]，AUC=0.9974
- [PASS] 分层划分后类别比例差小于 1 个百分点：最大差异=0.5205%
- [PASS] 统计图可读：figure_1_class_distribution.png：1509×1030px，58243 bytes
- [PASS] 统计图可读：figure_2_logistic_regression_confusion_matrix.png：1345×1097px，71244 bytes
- [PASS] 统计图可读：figure_3_decision_tree_confusion_matrix.png：1345×1097px，73584 bytes
- [PASS] 统计图可读：figure_4_random_forest_confusion_matrix.png：1345×1097px，75096 bytes
- [PASS] 统计图可读：figure_5_roc_curves.png：1535×1226px，125563 bytes

### Visualization Review

统计图使用明确标题、坐标标签、图例和一致配色；混淆矩阵注明真实类别与预测类别方向；ROC 图包含随机分类基准线。最终视觉完整性仍需在 HTML、DOCX 和 PDF 的实际页面中复核。

### Suggested Improvements

1. 若迁移到股票收益数据，应采用按时间先后划分或滚动回测，避免随机划分带来的前视偏差。
2. 若用于真实决策，应根据假正例与假负例的成本重新选择分类阈值，并报告交易成本或诊断代价。

### Required Caveats for Stakeholders

- 这是标准教学数据上的一次固定留出集实验，样本量有限，AUC 区间反映测试样本抽样不确定性。
- 结果仅用于演示分类模型流程，不构成医学诊断或投资建议。