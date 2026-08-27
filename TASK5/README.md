# TASK5 AI交易引擎：机器学习算法与场景应用

本项目使用 scikit-learn 内置乳腺癌二分类数据集，对逻辑回归、决策树和随机森林进行训练与测试，输出混淆矩阵、ROC、AUC、离线 HTML 成果页以及符合课程格式的 DOCX/PDF 报告。

## 一键运行

在仓库根目录执行：

```powershell
uv --cache-dir .uv-cache run python .\TASK5\scripts\run_all.py
```

主流程固定随机种子，重复运行将得到一致的数据划分、预测结果和评价指标。最终 PDF 导出需要 Windows 上安装 Microsoft Word；如果只运行数据分析、图表、HTML 和 DOCX 生成步骤，则不依赖 Word。

## 分步运行

```powershell
uv --cache-dir .uv-cache run python .\TASK5\scripts\train_and_evaluate.py
uv --cache-dir .uv-cache run python .\TASK5\scripts\validate_outputs.py
uv --cache-dir .uv-cache run python .\TASK5\scripts\build_site.py
uv --cache-dir .uv-cache run python .\TASK5\scripts\build_report.py
uv --cache-dir .uv-cache run python .\TASK5\scripts\validate_artifacts.py
```

## 主要输出

- `data/breast_cancer_binary.csv`：带重编码标签与数据集划分标记的实验数据；
- `outputs/metrics.csv`：三个模型的测试集评价结果；
- `outputs/predictions.csv`：逐样本真实标签、预测标签及正类概率；
- `outputs/figures/`：带图号和标题的统计图；
- `outputs/validation_report.md`：可复现的结果校验记录；
- `outputs/artifact_validation_report.md`：HTML、DOCX、PDF 最终交付校验记录；
- `web/index.html`：可离线打开的成果展示页；
- `report/姓名TASK5.docx`：可编辑作业文档；
- `report/姓名TASK5.pdf`：正式提交文件，确认姓名后重命名。

## 口径说明

scikit-learn 原始标签为恶性 = 0、良性 = 1。本项目为了让“正类”与风险事件一致，将标签重编码为恶性 = 1、良性 = 0。Precision、Recall、F1、ROC 和 AUC 均以恶性为正类计算。
