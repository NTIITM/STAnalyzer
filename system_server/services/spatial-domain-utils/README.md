# 空间可视化工具函数

本目录包含空间可视化相关的工具函数，特别是支持在空间可视化图片中添加切片背景的功能。

## 文件说明

### `spatial_plotting_utils.py`
提供通用的空间可视化工具函数，支持：
- 从AnnData对象中提取切片图像
- 在matplotlib图中添加切片背景
- 创建包含背景的完整空间可视化图

### `visualization.py`
空间域可视化模块，已更新支持切片背景。

## 快速使用

### 基本用法

```python
from spatial_plotting_utils import plot_spatial_with_background

fig, ax = plt.subplots(figsize=(10, 10))

# 添加切片背景
has_background = plot_spatial_with_background(
    adata, ax,
    color_key='cluster_label',  # 可选：用于着色的列
    spatial_key='spatial',
    image_key='hires',  # 或 'lowres', 'fullres'
    image_alpha=0.5,  # 背景透明度
    spot_size=10.0
)

# 继续绘制你的数据
# ...

plt.savefig('output.png', dpi=300, bbox_inches='tight')
plt.close()
```

### 完整函数用法

```python
from spatial_plotting_utils import create_spatial_plot_with_background

fig, ax, has_background = create_spatial_plot_with_background(
    adata,
    color_key='cluster_label',
    spatial_key='spatial',
    image_key='hires',
    image_alpha=0.5,
    figsize=(10, 10),
    dpi=300,
    title='My Spatial Plot',
    spot_size=10.0,
    show_legend=True
)

plt.savefig('output.png', dpi=300, bbox_inches='tight')
plt.close()
```

## 在其他服务中使用

### 方法1: 直接导入（如果服务在同一目录结构下）

```python
import sys
import os
utils_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                         'spatial-domain-utils')
if os.path.exists(utils_path):
    sys.path.insert(0, utils_path)
    from spatial_plotting_utils import plot_spatial_with_background
```

### 方法2: 使用相对导入（如果服务在system_server/services下）

```python
# 假设你的服务在 system_server/services/your-service/
import sys
from pathlib import Path
services_dir = Path(__file__).parent.parent
utils_path = services_dir / 'spatial-domain-utils'
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from spatial_plotting_utils import plot_spatial_with_background
```

## 注意事项

1. **图像可用性**: 不是所有h5ad文件都包含切片图像。函数会自动检测，如果没有图像则返回False。

2. **坐标对齐**: 工具函数会自动处理缩放因子，但可能需要根据实际情况调整extent。

3. **性能**: 对于大图像，建议使用 'lowres' 或 'hires' 而不是 'fullres'。

4. **透明度**: `image_alpha` 建议值在 0.3-0.7 之间。

## 已更新的服务

- ✅ `spatial-domain-utils/visualization.py` - `plot_spatial_domains()`
- ✅ `spatial-clustering/main.py` - `generate_clustering_plots()`

## 待更新的服务

参考 `system_server/docs/空间可视化服务总结.md` 查看完整的服务列表和更新指南。
