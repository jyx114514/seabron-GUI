"""plot_core_legacy_ref — 旧实现快照，仅供 Step 3 对拍测试使用。

本文件是重构前 scatterplot_test.py 中 build_scatterplot_kwargs / generate_code
的逐字副本，作为"行为不变"的事实基准。
plot_core.py 的规格驱动实现必须与本文件的输出逐字节一致（仅散点图部分；
折线 / 箱线 / 直方图由 plot_core_test 的规格自检与图码一致性测试覆盖）。
若日后散点图行为变更并经人工确认，可连同对拍测试一并删除。
不要修改本文件。
"""
import json
import re
from typing import Any


def legacy_q(value: Any) -> str:
    """把值安全转成 Python 双引号字符串字面量。

    使用 json.dumps 转义引号 / 反斜杠 / 换行等特殊字符，
    ensure_ascii=False 保留中文等非 ASCII 字符的可读性。
    修复：原版直接 f'"{v}"' 插值，值中含双引号时生成语法错误的代码。
    """
    return json.dumps(str(value), ensure_ascii=False)


def legacy_markers_to_code(v: bool | list | dict | str) -> str:
    """把 markers 值转成 seaborn 代码中的字面量。"""
    if isinstance(v, list):
        items = ", ".join(legacy_q(x) for x in v)
        return f"[{items}]"
    if isinstance(v, dict):
        items = ", ".join(f"{legacy_q(k)}: {legacy_q(val)}" for k, val in v.items())
        return "{" + items + "}"
    if isinstance(v, str):
        return legacy_q(v)
    return "False"


def legacy_build_scatterplot_kwargs(state: dict) -> dict:
    """依据 state 组装传给 sns.scatterplot(**kwargs) 的参数。"""
    kwargs: dict[str, Any] = {
        "data": "df",  # 占位，前端在调用时绑定实际 DataFrame
        "x": state["x"],
        "y": state["y"],
        "alpha": round(state["alpha"], 2),
    }

    if state.get("legend") and state["legend"] != "无":
        kwargs["legend"] = state["legend"]
    else:
        kwargs["legend"] = False

    # hue
    if state.get("hue"):
        kwargs["hue"] = state["hue"]

    # style
    if state.get("style"):
        kwargs["style"] = state["style"]

    # size
    if state.get("size"):
        kwargs["size"] = state["size"]

    # palette
    if state.get("palette") is not None:
        kwargs["palette"] = state["palette"]

    # markers 三态
    markers = state.get("markers", True)
    if markers is True:
        pass  # 省略 markers 键
    elif markers is False:
        kwargs["markers"] = False
    else:
        kwargs["markers"] = markers

    # sizes
    if state.get("size") and state.get("sizesEnabled"):
        kwargs["sizes"] = (state["sizeMin"], state["sizeMax"])

    return kwargs


def legacy_generate_code(state: dict, xcol: str, ycol: str) -> str:
    """返回完整可运行代码字符串。

    修复点（相对原版）：
    - x/y 与绘图端使用同一套回退逻辑（state 为空时用调用方传入的
      xcol/ycol 兜底），避免生成 x="None" 的不可用代码；
    - 所有插值字符串经 _q() 转义，标题/轴名/列名含双引号时
      生成的代码仍是合法 Python。
    """
    eff_x = state.get("x") or xcol
    eff_y = state.get("y") or ycol
    x = state.get("xlabel") or eff_x
    y = state.get("ylabel") or eff_y
    title = state.get("title") or f"{eff_x} 散点图"
    alpha = round(state["alpha"], 2)

    lines = [
        "import seaborn as sns",
        "import matplotlib.pyplot as plt",
        "import pandas as pd",
        "",
    ]

    # 主题
    theme = state.get("theme", "木系")
    if theme != "木系":
        if theme == "默认":
            lines.append("sns.set_theme()")
        else:
            lines.append(f'sns.set_theme(style="{theme}")')
        lines.append("")

    lines.append("sns.scatterplot(")
    lines.append(f'    data=df,')
    lines.append(f'    x={legacy_q(eff_x)}, y={legacy_q(eff_y)},')

    # alpha
    lines.append(f"    alpha={alpha},")

    # legend
    legend = state.get("legend", "auto")
    if legend == "无":
        lines.append("    legend=False,")
    else:
        lines.append(f"    legend={legacy_q(legend)},")

    # hue
    if state.get("hue"):
        lines.append(f"    hue={legacy_q(state['hue'])},")

    # style
    if state.get("style"):
        lines.append(f"    style={legacy_q(state['style'])},")

    # size
    if state.get("size"):
        lines.append(f"    size={legacy_q(state['size'])},")

    # palette
    if state.get("palette") is not None:
        lines.append(f"    palette={legacy_q(state['palette'])},")

    # markers
    markers = state.get("markers", True)
    if markers is False:
        lines.append("    markers=False,")
    elif markers is not True:
        lines.append(f"    markers={legacy_markers_to_code(markers)},")

    # sizes
    if state.get("size") and state.get("sizesEnabled"):
        lines.append(f"    sizes=({state['sizeMin']}, {state['sizeMax']}),")

    lines.append(")")
    lines.append(f"plt.title({legacy_q(title)})")
    lines.append(f"plt.xlabel({legacy_q(x)})")
    lines.append(f"plt.ylabel({legacy_q(y)})")
    lines.append("plt.tight_layout()")
    # plt.show() 以注释形式给出（与 plot_core.generate_code 保持一致）
    lines.append("# plt.show()")

    return "\n".join(lines)
