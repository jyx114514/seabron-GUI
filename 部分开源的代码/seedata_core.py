"""
seedata_core — 「数据透视」后端模块。

本模块封装所有 pandas/numpy 统计计算，不涉及任何 GUI 逻辑。
seedata_qt.py 严格通过本模块的接口获取数据，前端不做任何计算。
"""

from typing import Any

import pandas as pd
import numpy as np
import matplotlib
# 修复：移除 matplotlib.use("Agg") —— 纯计算模块不应在 import 时修改全局后端；
# 原实现与 scatterplot_qt 的 use("QtAgg") 相互竞争，import 顺序决定最终结果。
# 本模块直接构造 matplotlib.figure.Figure，不依赖 pyplot 后端选择。
import matplotlib.figure


# =============================================================================
# 文件读取
# =============================================================================

def read_table(path: str) -> pd.DataFrame:
    """读取 CSV / Excel 文件，返回 DataFrame。

    修复点（相对原版）：
    - 扩展名判断改为大小写不敏感；
    - 对不支持的格式显式抛错（原版会把任意后缀当 CSV 尝试读取，
      报错信息不可读）。本函数已统一为全项目唯一的数据读取入口（Q4）。
    - 编码回退链：utf-8-sig → utf-8 → gbk → gb18030，自动处理中文 GBK CSV。
    """
    lower = path.lower()
    if not lower.endswith((".csv", ".xls", ".xlsx")):
        raise ValueError(f"不支持的文件格式：{path}")
    if lower.endswith(".xlsx"):
        try:
            return pd.read_excel(path, engine="openpyxl")
        except ImportError as exc:  # openpyxl 缺失
            raise ValueError(
                "读取 .xlsx 需要 openpyxl 依赖，请安装：pip install openpyxl"
            ) from exc
    if lower.endswith(".xls"):
        try:
            return pd.read_excel(path, engine="xlrd")
        except ImportError as exc:  # xlrd 缺失
            raise ValueError(
                "读取 .xls 需要 xlrd 依赖，请安装：pip install xlrd"
            ) from exc
    # 编码回退链：按序尝试 utf-8-sig → utf-8 → gbk → gb18030，首次成功即返回。
    # 使用默认 C 引擎（比 python 引擎快 5~10 倍）；C 引擎经 iconv 同样支持
    # utf-8-sig / gbk / gb18030，遇解码错误同样抛 UnicodeDecodeError，回退语义不变。
    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_error = e
            continue
    raise ValueError(
        f"无法识别文件编码（已尝试 utf-8-sig / utf-8 / gbk / gb18030）：{last_error}"
    ) from last_error


# =============================================================================
# 类型推断
# =============================================================================

def infer_column_types(df: pd.DataFrame) -> dict[str, str]:
    """
    推断每列的数据类型。
    返回 dict[列名, str]，值为 'int64'/'float64'/'bool'/'str'/... 或 '脏数据列'。
    脏数据列判定：字符串/对象列中，除原本的空值外，还存在无法转为数值的
    文本，且列内同时存在可转数值的内容（两种格式混杂）。

    修复点（相对原版）：
    - 兼容 pandas 3.x：字符串列默认 dtype 为 StringDtype('str') 而非
      'object'，原版 `dtype == "object"` 判断在新版 pandas 下整个
      脏数据检测分支失效（警示条永不触发）；
    - 修正误判：原版 `converted.isna().sum() > 0` 把「纯数字字符串 +
      原有空值」的列也误判为脏数据，现改为只统计「转换后新增的空值」；
    - 使用 pd.api.types 的类型判断，覆盖 int32/float32 等更多数值类型。
    """
    types: dict[str, str] = {}
    for col in df.columns:
        s = df[col]
        if (pd.api.types.is_bool_dtype(s)
                or pd.api.types.is_numeric_dtype(s)
                or pd.api.types.is_datetime64_any_dtype(s)):
            types[col] = str(s.dtype)
        elif pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            # 尝试转为数值：不可转的文本会被 coerce 成 NaN
            converted = pd.to_numeric(s, errors="coerce")
            original_na = int(s.isna().sum())
            coerced_na = int(converted.isna().sum())
            if converted.notna().sum() > 0 and coerced_na > original_na:
                # 部分可转数值、部分不可转 → 脏数据
                types[col] = "脏数据列"
            else:
                types[col] = str(s.dtype)
        else:
            types[col] = str(s.dtype)
    return types


# =============================================================================
# 预览
# =============================================================================

def get_preview(df: pd.DataFrame, n: int = 3) -> tuple[list[str], list[list[Any]]]:
    """返回 (列名列表, 前 n 行数据)。"""
    return list(df.columns), df.head(n).values.tolist()


# =============================================================================
# 空值替换
# =============================================================================

def replace_custom_nulls(df: pd.DataFrame, markers: list[str]) -> pd.DataFrame:
    """
    将 markers 中指定的值替换为 NaN（遍历每列的每个元素）。
    markers 为空列表时直接返回原 df 的副本。
    """
    if not markers:
        return df.copy()
    result = df.copy()
    for marker in markers:
        # pandas 2.0 起 inplace=True 已废弃（3.0 移除），改用赋值式替换
        result = result.replace(marker, np.nan)
    return result


# =============================================================================
# 空值统计
# =============================================================================

def null_summary(df: pd.DataFrame) -> list[tuple[str, int, float]]:
    """返回 [(列名, 空值个数, 空值率 0~1), ...]。"""
    total = len(df)
    result: list[tuple[str, int, float]] = []
    for col in df.columns:
        null_count = int(df[col].isna().sum())
        rate = round(null_count / total, 4) if total > 0 else 0.0
        result.append((col, null_count, rate))
    return result


# =============================================================================
# 描述性统计
# =============================================================================

def describe_all(df: pd.DataFrame) -> pd.DataFrame:
    """返回 df.describe(include='all')，NaN 表示不适用。"""
    return df.describe(include="all")


# =============================================================================
# 数值列筛选
# =============================================================================

def numeric_columns(df: pd.DataFrame) -> list[str]:
    """返回所有数值型（int/float）列名，覆盖 int32/float32/Int64 等子类型（不含布尔列）。"""
    result: list[str] = []
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
            result.append(col)
    return result


# =============================================================================
# 箱线图
# =============================================================================

def make_boxplot(df: pd.DataFrame, cols: list[str]) -> matplotlib.figure.Figure:
    """对指定列绘制箱线图，返回 matplotlib Figure 对象。

    修复点（相对原版）：
    - `labels=` 参数已在 matplotlib 3.11 移除（直接 TypeError），
      改用 `tick_labels=`，并为旧版本保留回退；
    - 过滤全为空值的列，避免传入空数组画出空图且无提示；
    - 清理 `fig, ax = Figure(...), None` 的冗余写法。
    """
    series = [(col, df[col].dropna().values) for col in cols]
    series = [(col, values) for col, values in series if len(values) > 0]
    if not series:
        raise ValueError("所选数值列均无有效数据，无法绘制箱线图")
    labels = [col for col, _ in series]
    data = [values for _, values in series]

    fig = matplotlib.figure.Figure(figsize=(8, 4))
    ax = fig.subplots(1, 1)
    try:
        bp = ax.boxplot(data, tick_labels=labels, patch_artist=True)
    except TypeError:  # matplotlib < 3.9 无 tick_labels 参数
        bp = ax.boxplot(data, labels=labels, patch_artist=True)

    # 配色：木棕系
    wood_color = "#8B5A2B"
    for patch in bp["boxes"]:
        patch.set_facecolor("#F4EAD8")
        patch.set_edgecolor(wood_color)
        patch.set_linewidth(1.2)
    for whisker in bp["whiskers"]:
        whisker.set_color(wood_color)
    for cap in bp["caps"]:
        cap.set_color(wood_color)
    for median in bp["medians"]:
        median.set_color(wood_color)
        median.set_linewidth(2)

    ax.set_facecolor("#F7F3E7")
    ax.tick_params(colors="#3A2E1F", labelsize=10)
    for spine in ax.spines.values():
        spine.set_color("#E4D9C3")
    fig.tight_layout()
    return fig


# =============================================================================
# 导出 Excel
# =============================================================================

# Excel 公式注入防护：以这些字符开头的文本会被 Excel 当公式/命令解析
_EXCEL_DANGEROUS_PREFIXES = ("=", "+", "-", "@")


def _sanitize_excel_value(value: Any) -> Any:
    """对以 = + - @ 开头的文本加 ' 前缀，使 Excel 将其视为纯文本。

    修复（Q2）：describe 结果的 top 值来自用户原始数据，恶意构造的单元格
    （如 =cmd|'/c calc'!A1）经 openpyxl 写出后，Excel 打开会按公式解析。
    """
    if isinstance(value, str) and value[:1] in _EXCEL_DANGEROUS_PREFIXES:
        return "'" + value
    return value


def export_stats(df: pd.DataFrame, filepath: str, index: bool = False) -> None:
    """将 DataFrame 写入 .xlsx 文件（含公式注入防护）。

    index=True 时把行索引一并写出（用于 describe 结果的统计项名称）。
    """
    safe_df = df.copy()
    safe_df.columns = [_sanitize_excel_value(str(c)) for c in safe_df.columns]
    for col in safe_df.columns:
        s = safe_df[col]
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            safe_df[col] = s.map(_sanitize_excel_value)
    safe_df.to_excel(filepath, index=index, engine="openpyxl")
