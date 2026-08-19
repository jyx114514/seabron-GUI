"""
本模块集中定义项目统一 GUI 样式（PySide6 + QSS），供未来所有界面复用；
末尾 StyleDemo 为样式自测用例，运行即可预览整体视觉效果。

使用方式：
    from style import apply_style, build_sidebar, build_header, build_card, build_tag
    apply_style(app)   # 全局注入样式
"""

# =============================================================================
# matplotlib 后端唯一入口
# =============================================================================
# 全项目只在 style.py 调用 matplotlib.use()：所有 GUI 模块（main_window /
# plot_page / plot_theme / seedata_qt / plot_widgets …）都直接或间接 import
# style，因此 use("QtAgg") 必然在任何 matplotlib.pyplot 导入之前执行，
# 消除分散 use() 导致的导入顺序竞争（详见核对文档）。
# 纯计算模块（seedata_core）刻意不 import style：它用 matplotlib.figure.Figure
# 直接构造，不依赖 GUI 后端，不受本入口影响。
import matplotlib
matplotlib.use("QtAgg")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget, QLabel, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QGridLayout, QAbstractItemView
)

# =============================================================================
# 一、设计规格常量（颜色 / 字体 / 尺寸）
# =============================================================================

# ---------- 配色（效果图主内容区 #CCD698 米绿背景、木棕标题、米白卡片） ----------
BODY_BG = "#e8e2d2"             # 窗口外侧底色（HTML body 背景）
CONTENT_BG = "#CCD698"          # 主内容区背景
WOOD_BROWN = "#8B5A2B"          # 右侧标题区主色 / 菜单选中态底色（暖棕）
WOOD_BROWN_DARK = "#74491F"     # 标题区渐变深色端 / 底部描边（深棕）
BEIGE = "#F4EAD8"               # 左侧菜单栏背景（暖米色）
BEIGE_SOFT = "#FBF5EA"          # 菜单项悬停背景（更浅的米色）
CARD = "#F7F3E7"                # 内容卡片背景（暖白）
INK = "#3A2E1F"                 # 主文字（暖深棕）
INK_SOFT = "#8A7B66"            # 次要文字（浅棕灰）
LINE = "#E4D9C3"                # 分隔线 / 卡片边框（浅米棕）
ACCENT = "#7C9A3B"              # 点缀绿（与背景呼应的数据标记）
GOLD = "#C8A24B"                # 金色（标签/分类标记）
TITLE_COLOR = "#FFF7EC"         # 标题区主标题文字（米白）
BREADCRUMB_COLOR = "#E7C9A6"    # 标题区面包屑文字 / 代码面板标题色（浅金棕）
CODE_BG = INK                   # 代码面板背景色（与 INK 一致，深棕）
CODE_TEXT = CARD                # 代码面板文字色（与卡片底色一致，暖白）
DROP_ZONE_BORDER = "#B9966B"    # 拖放区虚线边框色

# ---------- 字体 ----------
FONT_FAMILY = '"Segoe UI", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif'
FONT_TITLE = "24px"
FONT_TITLE_WEIGHT = "600"
FONT_BREADCRUMB = "12.5px"
FONT_MENU = "14.5px"
FONT_MENU_WEIGHT = "500"
FONT_CARD_VALUE = "28px"
FONT_CARD_VALUE_WEIGHT = "700"

# ---------- 布局尺寸 ----------
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 720
WINDOW_RADIUS = 18              # 窗口圆角（HTML .app border-radius）
SIDEBAR_WIDTH = 248
HEADER_HEIGHT = 84
CONTENT_PADDING = "30px 32px"
CARD_RADIUS = "14px"
MENU_ITEM_RADIUS = "11px"
MENU_ITEM_PADDING = "12px 14px"
ICON_SIZE = 20
BTN_RADIUS = "6px"              # 按钮圆角（HTML .btn）
BTN_PADDING = "6px 14px"        # 按钮内边距（HTML .btn）
BTN_FONT_SIZE = "12px"          # 按钮字号（HTML .btn）
CONFIG_WIDTH = 392              # 配置面板宽度（HTML .config）
CHIP_RADIUS = "12px"            # Chip 圆角（HTML .chip）

# =============================================================================
# 二、QSS 样式字符串（按组件分区组织）
# =============================================================================

# ---- 全局样式 ----
GLOBAL_QSS = f"""
QWidget {{
    font-family: {FONT_FAMILY};
    color: {INK};
}}
QMainWindow {{
    background-color: {CONTENT_BG};
}}
"""

# ---- 左侧菜单栏（SIDEBAR） ----
SIDEBAR_QSS = f"""
#sidebarContainer {{
    background-color: {BEIGE};
    border-right: 1px solid {LINE};
    min-width: {SIDEBAR_WIDTH}px;
    max-width: {SIDEBAR_WIDTH}px;
}}
"""

# ---- 菜单项三态（含选中态 :selected） ----
MENU_ITEM_QSS = f"""
QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
    padding: 6px 12px;
}}
QListWidget::item {{
    color: {INK};
    background-color: transparent;
    border-radius: {MENU_ITEM_RADIUS};
    padding: {MENU_ITEM_PADDING};
    margin: 3px 0px;
    font-size: {FONT_MENU};
}}
QListWidget::item:hover {{
    background-color: {BEIGE_SOFT};
}}
QListWidget::item:selected {{
    background-color: {WOOD_BROWN};
    color: #FFFFFF;
}}
QListWidget::item:selected:!active {{
    background-color: {WOOD_BROWN};
    color: #FFFFFF;
}}
/* 菜单滚动条（限定 QListWidget 作用域，避免污染全局 QScrollBar）：
   木色细条、圆角滑块，隐藏上下箭头；内容超出时自动出现 */
QListWidget QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}
QListWidget QScrollBar::handle:vertical {{
    background: #C9A37E;
    border-radius: 4px;
    min-height: 28px;
}}
QListWidget QScrollBar::handle:vertical:hover {{
    background: {WOOD_BROWN};
}}
QListWidget QScrollBar::add-line:vertical,
QListWidget QScrollBar::sub-line:vertical {{
    height: 0;
}}
QListWidget QScrollBar::add-page:vertical,
QListWidget QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""

# ---- 右侧木棕标题区（HEADER） ----
HEADER_QSS = f"""
#headerContainer {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                stop:0 {WOOD_BROWN}, stop:1 {WOOD_BROWN_DARK});
    border-bottom: 2px solid {WOOD_BROWN_DARK};
    min-height: {HEADER_HEIGHT}px;
    max-height: {HEADER_HEIGHT}px;
    padding: 0 28px;
}}
"""

# ---- 内容区背景 ----
CONTENT_QSS = f"""
#contentArea {{
    background-color: {CONTENT_BG};
}}
"""

# ---- 卡片 ----
CARD_QSS = f"""
#cardContainer {{
    background-color: {CARD};
    border: 1px solid {LINE};
    border-radius: {CARD_RADIUS};
    padding: 20px;
}}
"""

# ---- 面板（PANEL，通用容器） ----
PANEL_QSS = f"""
#panelContainer {{
    background-color: {CARD};
    border: 1px solid {LINE};
    border-radius: {CARD_RADIUS};
    padding: 16px;
}}
"""

# ---- 标签（TAG） ----
TAG_QSS = f"""
#tagLabel {{
    background-color: {CONTENT_BG};
    color: {WOOD_BROWN};
    border-radius: 8px;
    padding: 4px 12px;
    font-size: 12px;
    font-weight: 500;
}}
"""

# 合并所有 QSS（仅在全局注入时使用）
_ALL_QSS = GLOBAL_QSS + SIDEBAR_QSS + MENU_ITEM_QSS + HEADER_QSS + CONTENT_QSS + CARD_QSS + PANEL_QSS + TAG_QSS


# =============================================================================
# 三、统一注入函数
# =============================================================================

def apply_style(app: QApplication) -> None:
    """将全局 QSS 一次性注入 QApplication，统一样式生效。"""
    app.setStyleSheet(_ALL_QSS)


def apply_to(widget: QWidget) -> None:
    """将全局 QSS 注入到指定 widget 及其子组件。"""
    widget.setStyleSheet(_ALL_QSS)


# =============================================================================
# 四、复用辅助工厂函数
# =============================================================================

def build_sidebar() -> QWidget:
    """构建左侧菜单栏容器（含顶部品牌区 + 菜单列表），已套用 SIDEBAR_QSS。"""
    from PySide6.QtCore import QSize
    container = QWidget()
    container.setObjectName("sidebarContainer")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # ---- 顶部品牌区（木棕方块 Logo + 名称 + 英文副标题） ----
    brand_widget = QWidget()
    brand_widget.setObjectName("brandWidget")
    brand_layout = QHBoxLayout(brand_widget)
    brand_layout.setContentsMargins(16, 20, 16, 16)
    brand_layout.setSpacing(10)

    # Logo 方块：木棕背景，白色 "木" 字
    logo_label = QLabel("木")
    logo_label.setFixedSize(40, 40)
    logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    logo_label.setStyleSheet(f"""
        QLabel {{
            background-color: {WOOD_BROWN};
            color: #FFFFFF;
            font-size: 20px;
            font-weight: bold;
            border-radius: 8px;
        }}
    """)

    # 名称 + 副标题（垂直排列）
    brand_text_layout = QVBoxLayout()
    brand_text_layout.setSpacing(1)
    name_label = QLabel("木绘图")
    name_label.setStyleSheet(f"""
        QLabel {{
            color: {INK};
            font-size: 16px;
            font-weight: 600;
            background: transparent;
        }}
    """)
    sub_label = QLabel("WOODS WORKSPACE")
    sub_label.setStyleSheet(f"""
        QLabel {{
            color: {INK_SOFT};
            font-size: 10px;
            letter-spacing: 1px;
            background: transparent;
        }}
    """)

    brand_text_layout.addWidget(name_label)
    brand_text_layout.addWidget(sub_label)

    brand_layout.addWidget(logo_label)
    brand_layout.addLayout(brand_text_layout)
    brand_layout.addStretch()

    layout.addWidget(brand_widget)

    # ---- MENU 标签（HTML .menu-label） ----
    menu_label = QLabel("MENU")
    menu_label.setStyleSheet(f"""
        QLabel {{
            color: {INK_SOFT};
            font-size: 11px;
            letter-spacing: 1px;
            padding: 6px 26px;
            background: transparent;
        }}
    """)
    layout.addWidget(menu_label)

    # ---- 菜单列表（QListWidget，样式由 MENU_ITEM_QSS 控制） ----
    menu_list = QListWidget()
    menu_list.setObjectName("menuList")
    menu_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    menu_list.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
    menu_list.setFrameStyle(QFrame.Shape.NoFrame)
    # 统一 item 尺寸：QSS 的 item padding/margin 不计入 QListView 的滚动范围
    # 计算（Qt 已知行为），显式声明统一尺寸后滚动范围才正确，避免菜单子项
    # 展开后内容超高时滚动条几乎不可用（maximum 仅有几像素）。
    menu_list.setUniformItemSizes(True)
    # 像素滚动：滚动条范围按像素计算（item 步长模式下仅等于剩余项数，
    # 拖动体验差），展开 20 项菜单后可精确滚动到每一项。
    menu_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    # stretch=1：菜单列表占据品牌区之外的剩余全部高度；
    # 子项多时内容超高由垂直滚动条承接（不再被底部弹性空间挤到看不见）
    layout.addWidget(menu_list, 1)

    # 底部弹性空间
    layout.addStretch()

    return container


def build_header(title: str = "", breadcrumb: str = "") -> QWidget:
    """构建右侧木棕标题区，支持传入标题与面包屑文字。"""
    container = QWidget()
    container.setObjectName("headerContainer")

    layout = QHBoxLayout(container)
    layout.setContentsMargins(28, 0, 28, 0)

    # 左侧标题 + 面包屑
    text_layout = QVBoxLayout()
    text_layout.setSpacing(2)

    title_label = QLabel(title)
    title_label.setObjectName("headerTitle")
    title_label.setStyleSheet(f"""
        QLabel {{
            color: {TITLE_COLOR};
            font-size: {FONT_TITLE};
            font-weight: {FONT_TITLE_WEIGHT};
            letter-spacing: 1px;
            background: transparent;
        }}
    """)

    bread_label = QLabel(breadcrumb)
    bread_label.setObjectName("headerBreadcrumb")
    bread_label.setStyleSheet(f"""
        QLabel {{
            color: {BREADCRUMB_COLOR};
            font-size: {FONT_BREADCRUMB};
            background: transparent;
        }}
    """)

    text_layout.addWidget(title_label)
    text_layout.addWidget(bread_label)
    layout.addLayout(text_layout)
    layout.addStretch()

    # 存储引用以便后续更新
    container._title_label = title_label
    container._bread_label = bread_label

    return container


def set_header_text(header_widget: QWidget, title: str, breadcrumb: str) -> None:
    """更新标题区文字。"""
    if hasattr(header_widget, "_title_label"):
        header_widget._title_label.setText(title)
    if hasattr(header_widget, "_bread_label"):
        header_widget._bread_label.setText(breadcrumb)


def build_card(title: str = "", value: str = "", tag_text: str = "") -> QWidget:
    """构建统计卡片，含标题、数值、可选标签。"""
    container = QWidget()
    container.setObjectName("cardContainer")
    container.setStyleSheet(CARD_QSS)

    # 卡片投影（柔和阴影）
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 30))
    container.setGraphicsEffect(shadow)

    layout = QVBoxLayout(container)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(6)

    # 标题
    if title:
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(f"""
            QLabel {{
                color: {INK_SOFT};
                font-size: 14px;
                background: transparent;
            }}
        """)
        layout.addWidget(title_lbl)

    # 数值（大字 WOOD_BROWN）
    if value:
        value_lbl = QLabel(value)
        value_lbl.setStyleSheet(f"""
            QLabel {{
                color: {WOOD_BROWN};
                font-size: {FONT_CARD_VALUE};
                font-weight: {FONT_CARD_VALUE_WEIGHT};
                background: transparent;
            }}
        """)
        layout.addWidget(value_lbl)

    # 标签
    if tag_text:
        tag = build_tag(tag_text)
        layout.addWidget(tag)

    layout.addStretch()
    return container


def build_tag(text: str) -> QLabel:
    """构建样式化标签 QLabel。"""
    tag = QLabel(text)
    tag.setObjectName("tagLabel")
    tag.setStyleSheet(TAG_QSS)
    tag.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    return tag


def _make_icon_svg(color: str, shape: str = "circle") -> str:
    """生成内嵌 SVG 字符串作为简易图标，避免依赖外部资源文件。"""
    if shape == "circle":
        # 实心圆图标
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{ICON_SIZE}" height="{ICON_SIZE}" viewBox="0 0 20 20"><circle cx="10" cy="10" r="6" fill="{color}"/></svg>'
    elif shape == "square":
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{ICON_SIZE}" height="{ICON_SIZE}" viewBox="0 0 20 20"><rect x="4" y="4" width="12" height="12" rx="2" fill="{color}"/></svg>'
    elif shape == "diamond":
        return f'<svg xmlns="http://www.w3.org/2000/svg" width="{ICON_SIZE}" height="{ICON_SIZE}" viewBox="0 0 20 20"><polygon points="10,3 17,10 10,17 3,10" fill="{color}"/></svg>'
    return ""


def _make_icon_pixmap(svg_str: str):
    """将 SVG 字符串通过 QPixmap.loadFromData 加载为 QPixmap。"""
    from PySide6.QtGui import QPixmap
    pixmap = QPixmap()
    pixmap.loadFromData(svg_str.encode("utf-8"))
    return pixmap


def _add_menu_item(menu_list: QListWidget, text: str, icon_shape: str) -> None:
    """向菜单列表中添加带有效图标的项（内嵌 SVG -> QPixmap -> QIcon）。"""
    from PySide6.QtGui import QIcon
    svg_str = _make_icon_svg(INK, icon_shape)
    pixmap = _make_icon_pixmap(svg_str)
    icon = QIcon(pixmap)

    item = QListWidgetItem(text)
    item.setIcon(icon)
    menu_list.addItem(item)


# =============================================================================
# 五、样式自测用例（StyleDemo）
# =============================================================================

class StyleDemo(QMainWindow):
    """
    样式自测主窗口，复刻效果图交互：
    - 左侧米色菜单栏（三项菜单，可点击切换）
    - 右侧木棕渐变色标题区（随菜单联动更新文字）
    - 右侧 #CCD698 内容区（QStackedWidget 三页，内含卡片等样式展示）
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("样式自测 - StyleDemo")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        # 窗口外层投影（QMainWindow 无法直接加阴影，此处放在中央部件上）
        self._setup_ui()

    def _setup_ui(self):
        """搭建完整界面。"""
        # ---- 中央部件 ----
        central = QWidget()
        self.setCentralWidget(central)

        # 整体水平布局：左菜单 + 右内容
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---- 左侧菜单栏 ----
        self.sidebar = build_sidebar()
        self.menu_list = self.sidebar.findChild(QListWidget, "menuList")
        main_layout.addWidget(self.sidebar)

        # ---- 右侧区域（标题 + 内容） ----
        right_area = QWidget()
        right_area.setObjectName("rightArea")
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 右侧标题区
        self.header = build_header("首页 / 仪表盘", "工作台 › 概览")
        right_layout.addWidget(self.header)

        # 右侧内容区
        self.content_area = QWidget()
        self.content_area.setObjectName("contentArea")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(30, 30, 32, 32)
        content_layout.setSpacing(20)
        self.content_area.setStyleSheet(f"QWidget#contentArea{{background-color: {CONTENT_BG};}}")

        # ---- QStackedWidget 内容分页 ----
        self.stack = QStackedWidget()
        # 构造三页
        self.stack.addWidget(self._build_page_home())
        self.stack.addWidget(self._build_page_data())
        self.stack.addWidget(self._build_page_settings())

        content_layout.addWidget(self.stack)
        right_layout.addWidget(self.content_area)

        main_layout.addWidget(right_area)

        # ---- 填充菜单项 ----
        self._populate_menu()

        # ---- 连接信号 ----
        self.menu_list.currentRowChanged.connect(self._on_menu_changed)

        # ---- 默认选中第一项 ----
        self.menu_list.setCurrentRow(0)

        # ---- 窗口整体圆角 + 投影（放在中央部件上） ----
        self._apply_window_shadow()

    def _apply_window_shadow(self):
        """为中央部件添加柔和外投影（模拟窗口阴影）。"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.centralWidget().setGraphicsEffect(shadow)

    def _populate_menu(self):
        """填充菜单项数据。"""
        items = [
            ("首页 / 仪表盘", "circle"),
            ("数据管理", "square"),
            ("设置", "diamond"),
        ]
        for text, shape in items:
            _add_menu_item(self.menu_list, text, shape)

    def _on_menu_changed(self, index: int):
        """菜单切换：更新 QStackedWidget 页面和标题区文字。"""
        self.stack.setCurrentIndex(index)

        # 更新标题区
        titles = [
            ("首页 / 仪表盘", "工作台 › 概览"),
            ("数据管理", "工作台 › 数据"),
            ("设置", "工作台 › 设置"),
        ]
        if 0 <= index < len(titles):
            title, bread = titles[index]
            set_header_text(self.header, title, bread)

        # 更新菜单选中态样式
        self._update_menu_selection(index)

    def _update_menu_selection(self, index: int):
        """
        更新菜单项的字体粗细（选中项加粗）。
        背景色和文字颜色由 QSS `QListWidget::item:selected` 自动处理。
        """
        for i in range(self.menu_list.count()):
            item = self.menu_list.item(i)
            font = item.font()
            font.setBold(i == index)
            item.setFont(font)

    # ---------- 页面构建方法 ----------

    def _build_page_home(self) -> QWidget:
        """首页页面：三张统计卡片 + 动态列表示意。"""
        page = QWidget()
        page.setObjectName("pageHome")
        page.setStyleSheet(f"QWidget#pageHome{{background-color: {CONTENT_BG};}}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(20)

        # ---- 三列统计卡片（网格布局） ----
        grid = QGridLayout()
        grid.setSpacing(16)

        card1 = build_card("总用户数", "12,846", "较上月 +12%")
        card2 = build_card("今日活跃", "1,372", "较昨日 +5%")
        card3 = build_card("总收入", "¥ 86,420", "较上月 +8%")

        grid.addWidget(card1, 0, 0)
        grid.addWidget(card2, 0, 1)
        grid.addWidget(card3, 0, 2)

        layout.addLayout(grid)

        # ---- 动态列表示意 ----
        list_panel = QWidget()
        list_panel.setObjectName("panelContainer")
        list_panel.setStyleSheet(PANEL_QSS)
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.setSpacing(8)

        list_title = QLabel("最近动态")
        list_title.setStyleSheet(f"""
            QLabel {{
                color: {INK};
                font-size: 16px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        list_layout.addWidget(list_title)

        # 示意行
        for i in range(4):
            row = QLabel(f"  模拟动态条目 — 第 {i + 1} 条示例数据")
            row.setStyleSheet(f"""
                QLabel {{
                    color: {INK_SOFT};
                    font-size: 13px;
                    padding: 8px 12px;
                    background-color: {CARD};
                    border: 1px solid {LINE};
                    border-radius: 8px;
                }}
            """)
            list_layout.addWidget(row)

        layout.addWidget(list_panel)
        layout.addStretch()
        return page

    def _build_page_data(self) -> QWidget:
        """数据管理页面：表格示意行。"""
        page = QWidget()
        page.setObjectName("pageData")
        page.setStyleSheet(f"QWidget#pageData{{background-color: {CONTENT_BG};}}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 标题
        page_title = QLabel("数据管理")
        page_title.setStyleSheet(f"""
            QLabel {{
                color: {INK};
                font-size: 18px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(page_title)

        # 表头
        header_row = QWidget()
        header_row.setObjectName("panelContainer")
        header_row.setStyleSheet(PANEL_QSS)
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(16, 10, 16, 10)
        for col in ["姓名", "年龄", "城市", "状态"]:
            lbl = QLabel(col)
            lbl.setStyleSheet(f"color: {INK_SOFT}; font-weight: 600; font-size: 13px; background: transparent;")
            header_layout.addWidget(lbl)
        layout.addWidget(header_row)

        # 示意数据行
        sample_data = [
            ("张三", "28", "北京", "● 正常"),
            ("李四", "35", "上海", "● 正常"),
            ("王五", "42", "广州", "● 异常"),
            ("赵六", "31", "深圳", "● 正常"),
        ]
        for name, age, city, status in sample_data:
            row = QWidget()
            row.setStyleSheet(f"""
                .QWidget {{
                    background-color: {CARD};
                    border: 1px solid {LINE};
                    border-radius: 8px;
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 10, 16, 10)
            for val in [name, age, city, status]:
                lbl = QLabel(val)
                color = ACCENT if "异常" in val else INK
                lbl.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
                row_layout.addWidget(lbl)
            layout.addWidget(row)

        layout.addStretch()
        return page

    def _build_page_settings(self) -> QWidget:
        """设置页面：参数示意行。"""
        page = QWidget()
        page.setObjectName("pageSettings")
        page.setStyleSheet(f"QWidget#pageSettings{{background-color: {CONTENT_BG};}}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 标题
        page_title = QLabel("系统设置")
        page_title.setStyleSheet(f"""
            QLabel {{
                color: {INK};
                font-size: 18px;
                font-weight: 600;
                background: transparent;
            }}
        """)
        layout.addWidget(page_title)

        # 参数示意行
        settings = [
            ("语言", "简体中文"),
            ("主题", "暖色模式"),
            ("通知", "已开启"),
            ("自动备份", "每日 02:00"),
        ]
        for label, value in settings:
            row = QWidget()
            row.setStyleSheet(f"""
                .QWidget {{
                    background-color: {CARD};
                    border: 1px solid {LINE};
                    border-radius: 8px;
                }}
            """)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(16, 12, 16, 12)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {INK}; font-size: 14px; font-weight: 500; background: transparent;")
            row_layout.addWidget(lbl)

            row_layout.addStretch()

            val = QLabel(value)
            val.setStyleSheet(f"color: {INK_SOFT}; font-size: 14px; background: transparent;")
            row_layout.addWidget(val)

            layout.addWidget(row)

        layout.addStretch()
        return page


# =============================================================================
# 六、主入口 — 样式自测
# =============================================================================

if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    # 设置全局字体
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # 注入统一样式
    apply_style(app)

    # 运行自测窗口
    demo = StyleDemo()
    demo.show()

    sys.exit(app.exec())
