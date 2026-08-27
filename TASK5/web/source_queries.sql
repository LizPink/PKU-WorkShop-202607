-- TASK5 核心指标查询
SELECT best_auc, best_model, logistic_auc, forest_auc, tree_auc, test_samples FROM headline;

-- TASK5 模型评价结果查询
SELECT model, model_zh, accuracy, precision, recall, specificity, f1, roc_auc, auc_ci_low, auc_ci_high, tn, fp, fn, tp, train_accuracy, train_roc_auc, auc_95_ci, sample_size, positive_class FROM metrics ORDER BY roc_auc DESC;

-- TASK5 数据划分类别查询
SELECT split, class_value, class_name, count, proportion, total_in_split, positive_class FROM split_summary ORDER BY split, class_value;

-- TASK5 ROC 曲线点查询
SELECT model, model_zh, fpr, tpr, threshold, sample_size, positive_count FROM roc_points ORDER BY model_zh, fpr, tpr;

-- TASK5 数据质量摘要查询
SELECT dataset_name, samples, features, missing_values, duplicate_feature_rows, positive_class, negative_class, train_samples, test_samples, test_size, random_state FROM data_quality;
