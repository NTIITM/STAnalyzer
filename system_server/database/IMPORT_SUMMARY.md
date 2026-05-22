# 数据导入总结

## 已完成的工作

### 1. CellPhoneDB 数据导入 ✅
- **脚本**: `import_cellphonedb.py`
- **状态**: 已完成并测试
- **导入记录数**: 1,396 条配体-受体对
- **数据源**: CellPhoneDB GitHub 仓库
- **特点**: 支持自动下载和导入

### 2. CellChat 数据导入 ✅
- **脚本**: `import_cellchat.py`
- **状态**: 已完成并测试
- **导入记录数**: 10 条示例数据（测试通过）
- **数据源**: 需要从 R 包中导出
- **特点**: 
  - 支持从 R 包导出的 CSV 文件导入
  - 自动处理受体复合物（用 `_` 或 `+` 分隔）
  - 支持 pathway、annotation、species 字段

### 3. NicheNet 数据导入 ✅
- **脚本**: `import_nichenet.py`
- **状态**: 已完成并测试
- **导入记录数**: 34 条示例数据（测试通过）
  - 25 条配体-靶基因关系
  - 9 条配体-受体关系（部分与现有数据重复）
- **数据源**: 需要从 R 包中导出
- **特点**:
  - 支持配体-靶基因矩阵导入
  - 支持配体-受体网络导入
  - 自动将靶基因关系标记为 `target_gene`

## 数据库统计

### 总记录数
- **总计**: 1,440 条配体-受体对记录
- **CellPhoneDB**: 1,396 条
- **CellChat**: 10 条
- **NicheNet**: 34 条

### 物种分布
- **human**: 10 条
- **mouse**: 0 条
- **both**: 1,430 条

### 唯一基因统计
- **唯一配体**: 620 个
- **唯一受体**: 608 个

## 使用方法

### CellPhoneDB
```bash
# 下载并导入
python -m database.import_cellphonedb --download --import --validate

# 仅导入（如果已下载）
python -m database.import_cellphonedb --import --csv-file data/cellphonedb/interaction.csv
```

### CellChat
```bash
# 1. 从 R 包导出数据（见 DATA_PREPARATION.md）
# 2. 导入 CSV 文件
python -m database.import_cellchat --import --csv-file cellchat_interactions.csv --validate
```

### NicheNet
```bash
# 1. 从 R 包导出数据（见 DATA_PREPARATION.md）
# 2. 导入数据
python -m database.import_nichenet --import \
    --ligand-target-file nichenet_ligand_target.txt \
    --ligand-receptor-file nichenet_ligand_receptor.csv \
    --data-type both \
    --validate
```

## 数据准备

详细的数据准备指南请参考 `DATA_PREPARATION.md`。

## 验证数据

```bash
# 验证所有数据源
python -m database.import_cellphonedb --validate
python -m database.import_cellchat --validate
python -m database.import_nichenet --validate

# 或使用 Python API
python -c "
from database import get_ligand_receptor_pairs
pairs = get_ligand_receptor_pairs()
print(f'总记录数: {len(pairs)}')
cellchat = get_ligand_receptor_pairs(source='cellchat')
print(f'CellChat: {len(cellchat)} 条')
nichenet = get_ligand_receptor_pairs(source='nichenet')
print(f'NicheNet: {len(nichenet)} 条')
"
```

## 内存缓存

如果数据量较小（< 5GB），可以加载到内存缓存以提高查询性能：

```bash
python -m database.import_cellphonedb --cache-memory
python -m database.import_cellchat --cache-memory
python -m database.import_nichenet --cache-memory
```

## 注意事项

1. **数据来源**: CellChat 和 NicheNet 的数据需要通过 R 包导出，无法直接下载。
2. **数据格式**: 确保导出的文件格式正确，字段名称与脚本期望的一致。
3. **重复处理**: 脚本会自动处理重复的配体-受体对（基于唯一索引）。
4. **数据量**: NicheNet 的配体-靶基因矩阵可能非常大，导入过程可能需要较长时间。

## 下一步

1. **导入完整数据**: 使用真实的 CellChat 和 NicheNet 数据文件（从 R 包导出）进行完整导入
2. **性能优化**: 根据实际数据量调整批量插入大小和缓存策略
3. **数据整合**: 考虑整合其他数据源（如 CellTalkDB、iTALK 等）
4. **数据更新**: 建立定期更新机制，保持数据最新

## 文件清单

- `import_cellphonedb.py` - CellPhoneDB 数据导入脚本
- `import_cellchat.py` - CellChat 数据导入脚本
- `import_nichenet.py` - NicheNet 数据导入脚本
- `DATA_PREPARATION.md` - 数据准备详细指南
- `IMPORT_SUMMARY.md` - 本总结文档

