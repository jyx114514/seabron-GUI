"""plot_core — 纯逻辑层：规格 → kwargs / 可运行代码。

无 PySide6 依赖，全部为纯函数，可独立测试。
散点图部分的输出须与 plot_core_legacy_ref.py 的旧实现逐字节一致（plot_core_test.py
对拍基准）；折线 / 箱线 / 直方图无旧实现可比对，由规格自检与图码一致性测试覆盖。
"""

import json
import math
import re
from dataclasses import replace
from typing import Any

from plot_spec import (
    PlotSpec,
    EMIT_ALWAYS,
    EMIT_IF_TRUTHY,
    EMIT_IF_NOT_NONE,
    EMIT_CUSTOM,
)


def q(value) -> str:
    """把值安全转成 Python 双引号字符串字面量（json.dumps，ensure_ascii=False）。"""
    return json.dumps(str(value), ensure_ascii=False)


def parse_markers(raw: str) -> bool | list | dict | str:
    """解析 markers 输入：JSON 数组/字典 → 原样；单值 → 字符串；空 → False。"""
    stripped = raw.strip()
    if not stripped:
        return False

    # 尝试 JSON 解析
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, (list, dict)):
            return parsed
    except json.JSONDecodeError:
        pass

    # 退化：单值（仅字母、数字、下划线或 ^）
    m = re.match(r"""^["']?([\w^]+)["']?$""", stripped)
    if m:
        return m.group(1)

    return False


def markers_to_code(v) -> str:
    """把 markers 值转成 seaborn 代码字面量（list/dict/str；False 表示禁用）。"""
    if isinstance(v, list):
        items = ", ".join(q(x) for x in v)
        return f"[{items}]"
    if isinstance(v, dict):
        items = ", ".join(f"{q(k)}: {q(val)}" for k, val in v.items())
        return "{" + items + "}"
    if isinstance(v, str):
        return q(v)
    return "False"


def parse_num(text: str) -> tuple[bool, Any]:
    """解析 num kind 的数值输入。

    返回 (ok, value)：
    - 空串            → (True, None)     调用方回退到 spec 默认值
    - 纯整数 "20"     → (True, 20)       bins 等整数参数
    - 纯浮点 "0.75"   → (True, 0.75)     binwidth / whis / saturation 等
    - 其他 "auto"     → (True, "auto")   原样字符串（如 bins="auto"）
    - inf / nan       → (False, None)    生成代码会变成非法 Python，拦截
    """
    s = (text or "").strip()
    if not s:
        return True, None
    try:
        return True, int(s)
    except ValueError:
        pass
    try:
        v = float(s)
        if math.isfinite(v):
            return True, v
        return False, None
    except ValueError:
        pass
    return True, s


def default_literal(v) -> str:
    """默认的"值 → 代码字面量"规则。

    注意判断顺序：bool 必须在 int 之前判断（Python 中 bool 是 int 的子类）。
    bool  → "True" / "False"
    数值   → str(v)
    其他   → q(v)
    """
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return str(v)
    return q(v)


def _rule_value(rule, state: dict, eff_x=None, eff_y=None) -> Any:
    """取规则的实际值（含 x/y 兜底列注入与 value 变换）。"""
    if rule.code_key == "x":
        if eff_x is None:
            return state["x"]
        return state.get("x") or eff_x
    if rule.code_key == "y":
        if eff_y is None:
            return state["y"]
        return state.get("y") or eff_y
    if rule.value is not None:
        return rule.value(state)
    return state.get(rule.state_key if rule.state_key is not None else rule.code_key)


def _rule_triggered(rule, state: dict) -> bool:
    """判断一条规则本次是否触发（决定是否写入 kwargs / 生成代码行）。"""
    if rule.emit == EMIT_ALWAYS:
        return True
    if rule.emit == EMIT_IF_TRUTHY:
        key = rule.state_key if rule.state_key is not None else rule.code_key
        return bool(state.get(key))
    if rule.emit == EMIT_IF_NOT_NONE:
        key = rule.state_key if rule.state_key is not None else rule.code_key
        return state.get(key) is not None
    if rule.emit == EMIT_CUSTOM:
        if rule.condition is not None:
            return bool(rule.condition(state))
        return True
    return True


def _rule_literal(rule, v: Any) -> str:
    """值 → 代码字面量。raw_code 规则直接返回固定片段。"""
    if rule.raw_code is not None:
        return rule.raw_code
    if rule.literal is not None:
        return rule.literal(v)
    return default_literal(v)


def build_kwargs(spec: PlotSpec, state: dict, eff_x=None, eff_y=None) -> dict:
    """按 spec.kwargs_rules 的声明顺序组装 kwargs。

    eff_x / eff_y 为兜底列名：state["x"] 为空时用 eff_x 顶替（与绘图端一致）。
    返回的 dict 中 "data" 键为占位字符串 "df"，调用方需自行 pop 后绑定真实 DataFrame。
    """
    kwargs: dict[str, Any] = {}
    for rule in spec.kwargs_rules:
        if not _rule_triggered(rule, state):
            continue
        if rule.raw_code is not None:
            # data 占位：值为字符串 "df"，代码端输出 data=df（无引号）
            kwargs[rule.code_key] = "df"
        else:
            kwargs[rule.code_key] = _rule_value(rule, state, eff_x, eff_y)
    return kwargs


def code_keys(spec: PlotSpec, state: dict) -> set[str]:
    """返回本次会出现在生成代码中的参数名集合。

    用于"图码一致性"测试：它必须恒等于 build_kwargs(...) 的键集合。
    """
    return {
        rule.code_key
        for rule in spec.kwargs_rules
        if _rule_triggered(rule, state)
    }


def _read_func_for_path(path: str) -> str:
    """按文件扩展名选择数据读取函数（CSV/TXT → read_csv，Excel → read_excel）。"""
    if str(path).lower().endswith((".xlsx", ".xls")):
        return "pd.read_excel"
    return "pd.read_csv"


def generate_code(spec: PlotSpec, state: dict, xcol: str, ycol: str,
                  data_path: str = "") -> str:
    """生成完整可运行代码字符串。

    结构（散点图部分须与 plot_core_legacy_ref 逐字节一致）：
        import seaborn as sns
        import matplotlib.pyplot as plt
        import pandas as pd
        <空行>
        [df = pd.read_csv("...")]   ← 仅当 data_path 非空
        <空行>
        [主题行]          ← 仅当 theme != "木系"
        [空行]            ← 仅当有主题行
        sns.<func>(
            <按 kwargs_rules 顺序逐行，注意 x/y 合并为一行>
        )
        plt.title(...)
        plt.xlabel(...)
        plt.ylabel(...)
        plt.tight_layout()
        # plt.show()
    """
    eff_x = state.get("x") or xcol
    eff_y = state.get("y") or ycol
    x = state.get("xlabel") or eff_x
    y = state.get("ylabel") or eff_y
    title = state.get("title") or spec.title_fallback(eff_x, eff_y)

    lines = [
        "import seaborn as sns",
        "import matplotlib.pyplot as plt",
        "import pandas as pd",
        "",
    ]

    # 数据读取：data_path 非空时生成 df = pd.read_csv/read_excel("...")
    # （q() 用 json.dumps 转义，Windows 路径中的反斜杠会安全输出为 \\）
    if data_path:
        lines.append(f"df = {_read_func_for_path(data_path)}({q(data_path)})")
        lines.append("")

    # 主题：非「木系」时输出 sns.set_theme 行（木系 = 不输出，沿用默认主题）
    theme = state.get("theme", "木系")
    if theme != "木系":
        if theme == "默认":
            lines.append("sns.set_theme()")
        else:
            lines.append(f'sns.set_theme(style="{theme}")')
        lines.append("")

    # matrix（heatmap / clustermap）：在 sns.<func>( 前插入透视表生成代码，
    # data 规则以 raw_code="data=pivot" 输出，与绘图端 _redraw 保持一致。
    if spec.matrix:
        lines.append("pivot = df.pivot_table(")
        lines.append(f"    index={q(state.get('pivot_row'))},")
        if state.get("pivot_col"):
            lines.append(f"    columns={q(state.get('pivot_col'))},")
        lines.append(f"    values={q(state.get('pivot_val'))},")
        lines.append("    aggfunc='mean',")
        lines.append(")")
        lines.append("")

    lines.append(f"sns.{spec.sns_func}(")

    # 按 kwargs_rules 顺序逐行渲染（x/y 合并为一行）
    rules = list(spec.kwargs_rules)
    i = 0
    while i < len(rules):
        rule = rules[i]
        if not _rule_triggered(rule, state):
            i += 1
            continue

        if rule.merge_with_next:
            # x 行：与紧随其后的下一条规则（通常为 y）合并输出在同一行。
            # 若该规则未触发（如 x-only 图的 y 为空），x 单独输出一行。
            # 不再向后跳过未触发的规则寻找合并目标，避免 x-only 图把 x 与
            # alpha/legend 等错并到同一行。
            j = i + 1
            lit_x = _rule_literal(rule, _rule_value(rule, state, eff_x, eff_y))
            if j < len(rules) and _rule_triggered(rules[j], state):
                nxt = rules[j]
                lit_y = _rule_literal(nxt, _rule_value(nxt, state, eff_x, eff_y))
                lines.append(f"    {rule.code_key}={lit_x}, {nxt.code_key}={lit_y},")
                i = j + 1
                continue
            lines.append(f"    {rule.code_key}={lit_x},")
            i += 1
            continue

        if rule.raw_code is not None:
            lines.append(f"    {rule.raw_code},")
        else:
            v = _rule_value(rule, state, eff_x, eff_y)
            lit = _rule_literal(rule, v)
            lines.append(f"    {rule.code_key}={lit},")
        i += 1

    # multi_y（追加 Y 轴）：追加了额外 Y 时，主调用补 label=主 y 列名，
    # 使主图线条也出现在「列名图例」中（与额外线保持一致）。
    extra_ys = [ey for ey in (state.get("extra_ys") or []) if ey]
    if spec.multi_y and extra_ys and eff_y:
        lines.append(f"    label={q(eff_y)},")
    lines.append(")")

    # multi_y：每个追加的 Y 列额外调用一次 lineplot（共享 X，自动配色，
    # label=列名，继承 alpha）；无 hue 时手动 plt.legend() 统一展示列名图例。
    if spec.multi_y and extra_ys:
        for ey in extra_ys:
            lines.append("")
            lines.append(f"sns.{spec.sns_func}(")
            lines.append("    data=df,")
            lines.append(f"    x={q(eff_x)}, y={q(ey)},")
            lines.append(f"    alpha={round(state.get('alpha', 0.65), 2)},")
            lines.append(f"    label={q(ey)},")
            # 追加线没有 style 变量（seaborn 复数 markers 会失效），
            # 勾选标记时用 matplotlib 单数 marker="o"，与 _redraw 保持一致
            if state.get("markers") is True:
                lines.append("    marker=\"o\",")
            lines.append(")")
        if not state.get("hue"):
            lines.append("plt.legend()")

    # 结尾：figure-level 图自建 Figure 并管理轴标签，仅用 suptitle；
    # axes-level 沿用 plt.title / xlabel / ylabel / tight_layout。
    if spec.level == "figure":
        lines.append(f"plt.suptitle({q(title)})")
    else:
        lines.append(f"plt.title({q(title)})")
        if spec.matrix:
            # matrix 图（heatmap）：轴标签默认由 pivot 行列索引决定，仅用户自定义时输出
            if state.get("xlabel"):
                lines.append(f"plt.xlabel({q(state.get('xlabel'))})")
            if state.get("ylabel"):
                lines.append(f"plt.ylabel({q(state.get('ylabel'))})")
        else:
            lines.append(f"plt.xlabel({q(x)})")
            # ylabel：仅当该 spec 声明了 y 轴且 y 有效时输出（如直方图 x-only 时省略 ylabel）
            has_y_rule = any(r.code_key == "y" for r in spec.kwargs_rules)
            if has_y_rule and eff_y:
                lines.append(f"plt.ylabel({q(y)})")
        lines.append("plt.tight_layout()")

    # plt.show() 以注释形式给出：GUI 内嵌绘图无需弹窗，用户复制代码自行运行时
    # 取消注释即可显示窗口。
    lines.append("# plt.show()")

    return "\n".join(lines)
