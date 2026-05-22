# 更新日志

## 2026-01-09 更新

### 1. 移除 imputation_stats.json，合并到 statistics.txt
- **原因**: 简化输出文件结构，所有统计信息统一在文本报告中
- **更改**:
  - 从 `service_config.json` 中删除了 `imputation_stats.json` 条目
  - 更新了 `statistics.txt` 的描述，明确包含所有统计信息
  - 从 `main.py` 中移除了 `imputation_stats.json` 的生成和保存逻辑

### 2. 修复 HVG 选择失败问题
- **问题**: HVG 选择时出现 "cannot specify integer `bins` when input data contains infinity" 错误
- **原因**: 数据中包含无穷大值，即使经过 `_clean_adata` 清理，在 HVG 选择时仍可能存在问题
- **解决方案**:
  - 添加了 `_prepare_adata_for_hvg()` 函数，在 HVG 选择前进行更彻底的数据清理
  - 创建数据副本，避免修改原始数据
  - 多次验证和清理，确保没有无穷大值和 NaN 值
  - 确保所有值都是非负的（某些操作可能产生负值）
- **参考**: 借鉴了 `spage-service` 中的实现方法

### 3. 添加更多可视化选项（cell mode）
基于教程 `tutorial_tangram_with_squidpy`，添加了以下可视化：

#### 3.1 训练基因得分图 (`training_scores.png`)
- **来源**: 教程 Cell 25
- **内容**: 4个面板的可视化
  1. 训练基因相似度分数的直方图
  2. 训练分数 vs scRNA-seq 数据稀疏度
  3. 训练分数 vs 空间数据稀疏度
  4. 训练分数 vs 稀疏度差异
- **用途**: 评估训练基因的质量和映射效果

#### 3.2 AUC 验证图 (`auc_validation.png`)
- **来源**: 教程 Cell 43
- **内容**: 最重要的验证图，显示所有基因的得分 vs 空间数据稀疏度
- **用途**: 评估整体映射质量，是 Tangram 映射质量的核心指标
- **实现**: 使用 `tg.compare_spatial_geneexp()` 和 `tg.plot_auc()`

#### 3.3 映射得分分布图 (`mapping_score_distribution.png`)
- **内容**: 映射得分（每个spot的权重总和）的直方图
- **保留**: 原有的 `imputation_qc.png` 作为向后兼容的别名

### 4. 更新 service_config.json
- 添加了新可视化文件的描述
- 更新了文件描述，明确说明各文件的用途和来源

## 技术细节

### HVG 选择失败的根本原因
1. **数据预处理不完整**: 虽然 `_clean_adata` 清理了无穷大值，但在某些情况下（如 log 变换后），可能重新产生无穷大值
2. **scanpy 的 HVG 选择**: `sc.pp.highly_variable_genes()` 在计算基因均值和方差时，如果数据包含无穷大值，会导致 `pd.cut()` 失败
3. **解决方案**: 在 HVG 选择前创建数据副本，进行彻底的清理和验证

### 可视化实现
- 所有可视化都使用 `matplotlib` 的非交互式后端 (`Agg`)
- 图片保存为 PNG 格式，DPI=200
- 可视化失败时不会中断主流程，只记录警告日志

## 向后兼容性
- 保留了 `imputation_qc.png` 作为 `mapping_score_distribution.png` 的别名
- 所有原有的输出文件（h5ad, csv, txt）保持不变

## 测试建议
1. 使用包含无穷大值的数据测试 HVG 选择是否正常工作
2. 验证所有可视化文件是否正确生成（cell mode）
3. 确认 statistics.txt 包含所有必要的统计信息

