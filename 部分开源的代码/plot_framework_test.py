"""plot_framework_test — 阶段 0 框架通用化专项测试。

覆盖新增能力（与散点图回归无关的纯新增行为）：
① parse_num：num kind 的输入解析（int / float / "auto" / inf·nan 拦截 / 空串）
② generate_code x-only 泛化：x 单独一行、省略 ylabel；x+y 时仍合并一行
③ build_kwargs / code_keys 图码一致性（x-only spec）
④ 高级设置折叠区：advanced 参数默认折叠、点击展开/收起、_on_num 解析与非法拦截

UI 测试依赖 PySide6（运行环境见 plot_page_test 顶部注释）。
"""
import os
from typing import Any

import pytest

from plot_core import parse_num, build_kwargs, generate_code, code_keys
from plot_spec import (
    PlotSpec, FieldSlot, ParamSpec, KwargRule, SPECS,
    EMIT_ALWAYS, EMIT_IF_TRUTHY, EMIT_CUSTOM, KIND_SLIDER, KIND_NUM, KIND_CHECKBOX,
    GROUP_AXES, GROUP_STYLE, GROUP_ADV_LINE,
)


# ── ① parse_num ──────────────────────────────────────────────

def test_parse_num_int() -> None:
    assert parse_num("20") == (True, 20)
    assert parse_num("-5") == (True, -5)


def test_parse_num_float() -> None:
    assert parse_num("0.75") == (True, 0.75)
    assert parse_num("20.5") == (True, 20.5)


def test_parse_num_str() -> None:
    assert parse_num("auto") == (True, "auto")
    assert parse_num("  auto  ") == (True, "auto")


def test_parse_num_empty() -> None:
    assert parse_num("") == (True, None)
    assert parse_num("   ") == (True, None)


def test_parse_num_invalid_inf_nan() -> None:
    assert parse_num("inf") == (False, None)
    assert parse_num("nan") == (False, None)


# ── 辅助：x-only spec（模拟直方图：仅 x 必填，y 可选）─────────

def _xonly_spec() -> PlotSpec:
    return PlotSpec(
        name="xonly", display_name="X 仅轴", config_title="测试",
        sns_func="histplot", level="axes",
        slots=(FieldSlot("x", "X 轴", 38, GROUP_AXES, required=True),),
        params=(),
        kwargs_rules=(
            KwargRule("data", emit=EMIT_ALWAYS, raw_code="data=df"),
            KwargRule("x", emit=EMIT_ALWAYS, merge_with_next=True),
            KwargRule("y", emit=EMIT_IF_TRUTHY),
        ),
        defaults={"x": None, "y": None, "theme": "木系",
                  "title": "直方图", "xlabel": "", "ylabel": ""},
        title_fallback=lambda a, b: f"{a} 直方图",
    )


def _xonly_state(x="age", y=None) -> dict:
    st = dict(_xonly_spec().defaults)
    st["x"] = x
    st["y"] = y
    return st


# ── ② generate_code x-only 泛化 ──────────────────────────────

def test_generate_code_x_only_no_y() -> None:
    spec = _xonly_spec()
    code = generate_code(spec, _xonly_state(x="age", y=None), "age", None)
    assert 'x="age",' in code, "x 应单独输出一行"
    assert 'x="age", y=' not in code, "x 不应与任何后续参数错误合并"
    assert "plt.ylabel" not in code, "x-only 图不应输出 ylabel"
    compile(code, "<generated>", "exec")  # 必须是合法 Python


def test_generate_code_x_with_y_still_merges() -> None:
    spec = _xonly_spec()
    code = generate_code(spec, _xonly_state(x="age", y="height"), "age", "height")
    assert 'x="age", y="height",' in code, "x/y 齐全时应合并为一行"
    assert 'plt.ylabel("height")' in code, "y 有效时应输出 ylabel"
    compile(code, "<generated>", "exec")


# ── ③ 图码一致性（x-only）────────────────────────────────────

def test_xonly_kwargs_keys_equals_code_keys() -> None:
    spec = _xonly_spec()
    for st in (_xonly_state(y=None), _xonly_state(y="height")):
        a = set(build_kwargs(spec, st).keys())
        b = code_keys(spec, st)
        assert a == b, f"图码不一致！state: {st!r}\nkwargs 键: {a}\ncode_keys: {b}"


def test_xonly_build_kwargs_no_y_when_empty() -> None:
    spec = _xonly_spec()
    kwargs = build_kwargs(spec, _xonly_state(y=None))
    assert "y" not in kwargs, "y 为空时 kwargs 不应含 y"
    assert kwargs["x"] == "age"


# ── ④ 高级设置折叠区 + num 输入（PySide6 UI）──────────────────

def _advanced_spec() -> PlotSpec:
    return PlotSpec(
        name="advtest", display_name="高级测试", config_title="高级测试配置",
        sns_func="scatterplot", level="axes",
        slots=(FieldSlot("x", "X 轴", 38, GROUP_AXES, required=True),
               FieldSlot("y", "Y 轴", 38, GROUP_AXES, required=True)),
        params=(
            ParamSpec("alpha", KIND_SLIDER, "透明度 alpha", 0.65, GROUP_STYLE,
                      minimum=10, maximum=100, scale=0.01),
            ParamSpec("bins", KIND_NUM, "分箱 bins", "auto", GROUP_STYLE,
                      advanced=True, note="数字或 auto"),
            ParamSpec("dashes", KIND_CHECKBOX, "虚线 dashes", True, GROUP_ADV_LINE,
                      advanced=True),
        ),
        kwargs_rules=(
            KwargRule("data", emit=EMIT_ALWAYS, raw_code="data=df"),
            KwargRule("x", emit=EMIT_ALWAYS, merge_with_next=True),
            KwargRule("y", emit=EMIT_ALWAYS),
            KwargRule("alpha", emit=EMIT_ALWAYS),
            KwargRule("bins", emit=EMIT_IF_TRUTHY),
            KwargRule("dashes", emit=EMIT_CUSTOM,
                      condition=lambda st: st.get("dashes") is False),
        ),
        defaults={"x": None, "y": None, "alpha": 0.65, "bins": "auto",
                  "dashes": True, "theme": "木系",
                  "title": "测试", "xlabel": "", "ylabel": ""},
        title_fallback=lambda a, b: f"{a} 测试",
    )


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_page(app):
    from plot_page import PlotPage
    return PlotPage(_advanced_spec())


def test_advanced_section_hidden_by_default(app) -> None:
    page = _make_page(app)
    assert page._adv_box is not None, "有 advanced 参数时应存在折叠容器"
    assert page._adv_box.isHidden(), "高级设置区默认折叠"
    assert page._adv_btn is not None
    assert "▸" in page._adv_btn.text(), "折叠时标题应显示 ▸"


def test_advanced_toggle_expand_collapse(app) -> None:
    page = _make_page(app)
    page._toggle_advanced()
    assert not page._adv_box.isHidden(), "点击后应展开"
    assert "▾" in page._adv_btn.text(), "展开时标题应显示 ▾"
    page._toggle_advanced()
    assert page._adv_box.isHidden(), "再次点击应收起"


def test_advanced_param_not_in_core_swatch(app) -> None:
    """advanced 参数（bins）应登记在 _num_inputs，且不在核心区 _param_widgets 之外
    造成重复渲染——bins 的控件容器应位于折叠区内。"""
    page = _make_page(app)
    assert "bins" in page._num_inputs, "advanced num 参数应渲染到 _num_inputs"
    # 核心参数仍照常渲染（滑块 alpha）
    assert "alpha" in page._param_widgets


def test_on_num_parses_and_keeps_on_invalid(app) -> None:
    page = _make_page(app)
    inp = page._num_inputs["bins"]

    # 合法 int：即时写入 state
    inp.setText("20")
    assert page.state["bins"] == 20, "bins 应解析为 int"

    # "auto" 字符串：原样保留
    inp.setText("auto")
    assert page.state["bins"] == "auto"

    # 空串：回退默认值
    inp.setText("")
    assert page.state["bins"] == "auto", "空输入应回退 spec 默认值"

    # inf 非法：红色警告 + 保留旧值
    page._set_status("")
    inp.setText("inf")
    assert page.state["bins"] == "auto", "inf 不应写入 state"
    assert "保留上次有效值" in page._status_lbl.text(), "非法输入应给状态提示"
    assert "#C62828" in page._status_lbl.styleSheet(), "非法输入警告应为红色"


# ── ⑤ checkbox 纯复选框 ──────────────────────────────────────

def test_checkbox_renders_and_toggles(app) -> None:
    page = _make_page(app)
    chk = page._checkboxes["dashes"]
    assert chk.isChecked(), "默认 True 应勾选"
    chk.setChecked(False)
    assert page.state["dashes"] is False, "取消勾选应写入 state"
    chk.setChecked(True)
    assert page.state["dashes"] is True, "勾选应写入 state True"


def test_checkbox_reset_restores_default(app) -> None:
    page = _make_page(app)
    page._checkboxes["dashes"].setChecked(False)
    assert page.state["dashes"] is False
    page._reset()
    assert page.state["dashes"] is True, "重置后 state 恢复默认"
    assert page._checkboxes["dashes"].isChecked(), "重置后复选框恢复勾选"


def test_checkbox_kwargs_emission(app) -> None:
    """checkbox 默认 True 不发射 dashes，取消勾选（False）才发射 dashes=False。"""
    from plot_core import build_kwargs
    page = _make_page(app)
    st = dict(page.state)
    st["x"] = "a"
    st["y"] = "b"
    assert "dashes" not in build_kwargs(page._spec, st), "默认 True 不应发射 dashes"
    st["dashes"] = False
    assert build_kwargs(page._spec, st)["dashes"] is False, "False 应发射 dashes=False"


# ── ⑥ markers 特判回归（B4：折线图画不出图的根因）────────────

def test_checkbox_markers_not_misjudged_as_no_draw(app) -> None:
    """回归：checkbox 类型 markers（折线图，默认 False）不得被散点图专用的
    「markers=False 不绘制数据点」特判拦截——特判只对 checkbox_text 三态生效。"""
    from plot_spec import SPECS
    from plot_page import PlotPage
    import pandas as pd
    page = PlotPage(SPECS["line"])
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
                       "y": [2, 3, 4, 5, 6, 3, 4, 5, 6, 7],
                       "g": ["a"] * 5 + ["b"] * 5})
    page.set_dataset(df, "t")
    page.state["x"] = "x"
    page.state["y"] = "y"
    page._redraw()
    assert page.state["markers"] is False, "折线图 markers 默认 False"
    assert len(page._ax.lines) > 0, "折线图应正常绘制线条（即使 markers=False）"
    assert "sns.lineplot(" in page._cv.toPlainText(), "折线图应生成 lineplot 代码"


def test_scatter_markers_false_still_no_draw(app) -> None:
    """回归：散点图 markers=False（checkbox_text 三态）仍走「不绘制数据点」特判。"""
    from plot_spec import SPECS
    from plot_page import PlotPage
    import pandas as pd
    page = PlotPage(SPECS["scatter"])
    df = pd.DataFrame({"x": [1, 2, 3], "y": [2, 3, 4]})
    page.set_dataset(df, "t")
    page.state["x"] = "x"
    page.state["y"] = "y"
    page.state["markers"] = False
    page._redraw()
    assert len(page._ax.collections) == 0, "散点图 markers=False 不应绘制数据点"


# ── ⑦ multi_y：追加 Y 轴（多次 lineplot，UI 层）──────────────

def test_multi_y_section_only_for_multi_y_spec(app) -> None:
    """「追加 Y 轴」区域：折线图（multi_y=True）渲染，散点图（multi_y=False）不渲染。"""
    from plot_page import PlotPage
    page = PlotPage(SPECS["line"])
    assert page._multi_y_box is not None, "折线图应渲染「追加 Y 轴」区域"
    assert page._multi_y_rows_layout is not None
    page2 = PlotPage(SPECS["scatter"])
    assert page2._multi_y_box is None, "散点图不应渲染「追加 Y 轴」区域"


def test_multi_y_add_del_reset(app) -> None:
    """加号追加 / ✕ 删除 / 重置：state['extra_ys'] 同步变化。"""
    from plot_page import PlotPage
    page = PlotPage(SPECS["line"])
    assert page.state["extra_ys"] == []
    page._add_extra_y()
    assert page.state["extra_ys"] == [None], "加号应追加一个空 Y 槽位"
    page._add_extra_y()
    assert len(page.state["extra_ys"]) == 2, "再点一次应追加第二个槽位"
    page._del_extra_y(0)
    assert len(page.state["extra_ys"]) == 1, "✕ 应删除对应槽位"
    page._reset()
    assert page.state["extra_ys"] == [], "重置后追加 Y 应清空"


def test_multi_y_redraw_multiple_lines(app) -> None:
    """追加 Y 后 _redraw：主图 + 追加线共同绘制，代码含多次 lineplot 与 plt.legend()。"""
    import pandas as pd
    from plot_page import PlotPage
    page = PlotPage(SPECS["line"])
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 1, 2, 3, 4, 5],
                       "y": [2, 3, 4, 5, 6, 3, 4, 5, 6, 7],
                       "y2": [3, 4, 5, 6, 7, 4, 5, 6, 7, 8]})
    page.set_dataset(df, "t")
    page.state["x"] = "x"
    page.state["y"] = "y"
    page._add_extra_y()
    page._on_extra_y(0, "y2")
    page._redraw()
    assert page.state["extra_ys"] == ["y2"]
    assert len(page._ax.lines) >= 2, "主图 + 追加线应 >= 2 条线"
    code = page._cv.toPlainText()
    assert code.count("sns.lineplot(") >= 2, "代码应含多次 lineplot 调用"
    assert "label=" in code, "追加模式应带列名 label"
    assert "plt.legend()" in code, "无 hue 时应输出 plt.legend()"
