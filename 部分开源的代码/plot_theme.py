"""plot_theme — 「木绘图」主题层：6 个主题的应用与坐标区美化。

从 scatterplot_qt.py 抽出，供所有绘图页共用。
主题作用于 matplotlib 全局 rcParams，因此每次绘图前都应无条件调用
apply_theme()，不依赖任何"上一次状态"的假设（幂等）。
"""

# style 必须先于任何 matplotlib 模块导入：它是全项目唯一的
# matplotlib.use("QtAgg") 入口（见 style.py 顶部注释），保证后端在
# import matplotlib.pyplot 之前已选定，避免导入顺序竞争。
from style import CARD, LINE, INK_SOFT

import matplotlib.pyplot as plt
import seaborn as sns

# 主题名列表定义于 plot_spec.THEME_NAMES（规格层 UI 选项与主题层应用逻辑同源，
# 不在此重复定义，避免 plot_core/plot_spec 反向依赖本模块的 matplotlib 导入链）。
DEFAULT_THEME = "木系"

# 中文字体回退链；负号用 ASCII 以免显示为方块
CJK_FONTS = [
    "Microsoft YaHei", "SimHei", "PingFang SC",
    "Noto Sans CJK SC", "Source Han Sans SC", "DejaVu Sans",
]


def apply_cjk_font() -> None:
    """设置中文字体与负号显示。

    必须在每次 sns.set_theme() 之后立即调用 —— set_theme 会重置 rcParams，
    把字体设置冲掉，导致中文标题显示为方块。
    """
    plt.rcParams["font.sans-serif"] = list(CJK_FONTS)
    plt.rcParams["axes.unicode_minus"] = False


def apply_theme(theme: str) -> None:
    """应用主题到 matplotlib 全局 rcParams。

    "木系"：恢复木色 rcParams（axes/figure facecolor = CARD），使新建的
            axes 默认继承木色；
    "默认"：sns.set_theme()；
    其余：  sns.set_theme(style=theme)。
    两种 seaborn 分支之后都会重新调用 apply_cjk_font()。
    """
    if theme == "木系":
        # 恢复木色 rcParams，使重建的 axes 默认继承木色
        plt.rcParams["axes.facecolor"] = CARD
        plt.rcParams["figure.facecolor"] = CARD
        apply_cjk_font()
        return
    if theme == "默认":
        sns.set_theme()
    else:
        sns.set_theme(style=theme)
    # sns.set_theme() 会重置 rcParams，立即重设中文字体
    apply_cjk_font()


def figure_facecolor(theme: str) -> str:
    """返回该主题下 Figure 应使用的底色。

    木系返回 style.CARD；非木系返回当前 rcParams 的 figure.facecolor
    （需在 apply_theme 之后调用才准确）。
    """
    if theme == "木系":
        return CARD
    return plt.rcParams.get("figure.facecolor", CARD)


def style_axes(ax, fig, theme: str) -> None:
    """统一坐标区外观。

    木系：设置 facecolor / spines / tick 颜色 / 网格；
    非木系：交由 seaborn 主题接管，不做任何覆盖（保持现有行为）。
    """
    if theme == "木系":
        ax.set_facecolor(CARD)
        fig.patch.set_facecolor(CARD)
        for sp in ax.spines.values():
            sp.set_color(LINE)
        ax.tick_params(colors=INK_SOFT)
        ax.grid(True, alpha=0.5, color=LINE)
    # 非木系交由 seaborn 主题接管，不做覆盖
