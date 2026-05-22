"""
R绘图工具模块
提供统一的接口调用R脚本进行绘图
"""
import os
import subprocess
import tempfile
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# R脚本路径
SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
PLOT_HEATMAP_R = SCRIPT_DIR / "plot_heatmap.R"
PLOT_BUBBLE_R = SCRIPT_DIR / "plot_bubble.R"
PLOT_NETWORK_R = SCRIPT_DIR / "plot_network.R"
PLOT_STACKED_BAR_R = SCRIPT_DIR / "plot_stacked_bar.R"
PLOT_SCATTER_NETWORK_R = SCRIPT_DIR / "plot_scatter_network.R"


def _run_rscript(script_path: Path, args: list) -> bool:
    """运行R脚本"""
    try:
        cmd = ["Rscript", str(script_path)] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=300  # 5分钟超时
        )
        logger.debug(f"R脚本执行成功: {script_path.name}")
        if result.stdout:
            logger.debug(f"R脚本输出: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else e.stdout if e.stdout else "未知错误"
        logger.error(f"R脚本执行失败 ({script_path.name}): {error_msg}")
        logger.error(f"R脚本命令: {' '.join(cmd)}")
        return False
    except FileNotFoundError:
        logger.error("Rscript未找到，请确保R已安装并在PATH中")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"R脚本执行超时: {script_path.name}")
        return False
    except Exception as e:
        logger.error(f"R脚本执行异常: {script_path.name}, 错误: {e}", exc_info=True)
        return False


def plot_heatmap(
    df: pd.DataFrame,
    output_path: str,
    title: str,
    colormap: str = "YlGnBu",
    width: float = 10.0,
    height: float = 8.0
) -> Optional[str]:
    """
    使用R脚本绘制热图
    
    Args:
        df: 数据框，索引为行名，列为列名
        output_path: 输出PNG文件路径
        title: 图表标题
        colormap: 颜色映射 (YlGnBu, RdBu_r, coolwarm, viridis)
        width: 图表宽度（英寸）
        height: 图表高度（英寸）
    
    Returns:
        输出文件路径，失败返回None
    """
    if df.empty:
        logger.warning("热图数据为空，跳过绘图")
        return None
    
    # 检查数据有效性
    if df.shape[0] == 0 or df.shape[1] == 0:
        logger.warning("热图数据维度无效，跳过绘图")
        return None
    
    # 检查数据是否全为0或全相同
    try:
        data_values = df.values.flatten()
        data_values = data_values[~pd.isna(data_values)]
        if len(data_values) == 0:
            logger.warning("热图数据全为NaN，跳过绘图")
            return None
        if len(set(data_values)) == 1:
            logger.info(f"热图数据所有值都相同 ({data_values[0] if len(data_values) > 0 else 'N/A'})，R脚本会处理此情况")
    except Exception as e:
        logger.warning(f"检查热图数据时出错: {e}，继续执行")
    
    # 创建临时CSV文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        df.to_csv(tmp.name)
        tmp_csv = tmp.name
    
    try:
        args = [
            tmp_csv,
            output_path,
            title,
            colormap,
            str(width),
            str(height)
        ]
        
        if _run_rscript(PLOT_HEATMAP_R, args):
            # 验证输出文件是否存在
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            else:
                logger.error(f"R脚本执行成功但输出文件不存在或为空: {output_path}")
                return None
        return None
    finally:
        # 清理临时文件
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)


def plot_bubble(
    df: pd.DataFrame,
    output_path: str,
    x_col: str,
    y_col: str,
    size_col: str,
    color_col: str,
    title: str,
    width: float = 8.0,
    height: float = 6.0
) -> Optional[str]:
    """
    使用R脚本绘制气泡图
    
    Args:
        df: 数据框
        output_path: 输出PNG文件路径
        x_col: X轴列名
        y_col: Y轴列名
        size_col: 气泡大小列名
        color_col: 气泡颜色列名
        title: 图表标题
        width: 图表宽度（英寸）
        height: 图表高度（英寸）
    
    Returns:
        输出文件路径，失败返回None
    """
    if df.empty:
        return None
    
    # 创建临时CSV文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        df.to_csv(tmp.name, index=False)
        tmp_csv = tmp.name
    
    try:
        args = [
            tmp_csv,
            output_path,
            x_col,
            y_col,
            size_col,
            color_col,
            title,
            str(width),
            str(height)
        ]
        
        if _run_rscript(PLOT_BUBBLE_R, args):
            return output_path
        return None
    finally:
        # 清理临时文件
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)


def plot_network(
    centroids: pd.DataFrame,
    edges: pd.DataFrame,
    output_path: str,
    title: str,
    width: float = 6.0,
    height: float = 6.0
) -> Optional[str]:
    """
    使用R脚本绘制网络图（SpaOTsc风格）
    
    Args:
        centroids: 节点数据框，包含x, y, label列
        edges: 边数据框，包含x1, y1, x2, y2, weight列
        output_path: 输出PNG文件路径
        title: 图表标题
        width: 图表宽度（英寸）
        height: 图表高度（英寸）
    
    Returns:
        输出文件路径，失败返回None
    """
    if centroids.empty or edges.empty:
        return None
    
    # 创建临时CSV文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp1:
        centroids.to_csv(tmp1.name, index=False)
        tmp_centroids = tmp1.name
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp2:
        edges.to_csv(tmp2.name, index=False)
        tmp_edges = tmp2.name
    
    try:
        args = [
            tmp_centroids,
            tmp_edges,
            output_path,
            title,
            str(width),
            str(height)
        ]
        
        if _run_rscript(PLOT_NETWORK_R, args):
            return output_path
        return None
    finally:
        # 清理临时文件
        for tmp_file in [tmp_centroids, tmp_edges]:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)


def plot_stacked_bar(
    df: pd.DataFrame,
    output_path: str,
    title: str,
    x_col: str,
    value_cols: list,
    width: float = 8.0,
    height: float = 6.0
) -> Optional[str]:
    """
    使用R脚本绘制堆叠柱状图
    
    Args:
        df: 数据框
        output_path: 输出PNG文件路径
        title: 图表标题
        x_col: X轴列名
        value_cols: 堆叠的值列名列表
        width: 图表宽度（英寸）
        height: 图表高度（英寸）
    
    Returns:
        输出文件路径，失败返回None
    """
    if df.empty:
        return None
    
    # 创建临时CSV文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        df.to_csv(tmp.name, index=False)
        tmp_csv = tmp.name
    
    try:
        value_cols_str = ",".join(value_cols)
        args = [
            tmp_csv,
            output_path,
            title,
            x_col,
            value_cols_str,
            str(width),
            str(height)
        ]
        
        if _run_rscript(PLOT_STACKED_BAR_R, args):
            return output_path
        return None
    finally:
        # 清理临时文件
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)


def plot_scatter_network(
    df: pd.DataFrame,
    output_path: str,
    x_col: str,
    y_col: str,
    size_col: str,
    color_col: str,
    title: str,
    width: float = 8.0,
    height: float = 5.0
) -> Optional[str]:
    """
    使用R脚本绘制散点网络图（Squidpy LigRec风格）
    
    Args:
        df: 数据框
        output_path: 输出PNG文件路径
        x_col: X轴列名
        y_col: Y轴列名
        size_col: 点大小列名
        color_col: 点颜色列名
        title: 图表标题
        width: 图表宽度（英寸）
        height: 图表高度（英寸）
    
    Returns:
        输出文件路径，失败返回None
    """
    if df.empty:
        return None
    
    # 创建临时CSV文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
        df.to_csv(tmp.name, index=False)
        tmp_csv = tmp.name
    
    try:
        args = [
            tmp_csv,
            output_path,
            x_col,
            y_col,
            size_col,
            color_col,
            title,
            str(width),
            str(height)
        ]
        
        if _run_rscript(PLOT_SCATTER_NETWORK_R, args):
            return output_path
        return None
    finally:
        # 清理临时文件
        if os.path.exists(tmp_csv):
            os.remove(tmp_csv)

