"""
本模块实现「木绘图」主窗口：左侧菜单 + 右侧内容区（QStackedWidget 页面切换）。
复用 style.py 中的统一样式系统（颜色 / 字体 / 工厂函数），
不重新定义任何颜色或布局尺寸。

功能：
- 左侧菜单：「数据透视」叶子项 + 可折叠「绘图 ▸」父项（散点/折线/箱线/直方 子项）
- 右侧标题区：随菜单点击联动更新（set_header_text）
- 右侧内容区：各页面常驻 QStackedWidget，切换不销毁 → 页面状态天然持久化
"""

import sys
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QPixmap, QColor, QPainter, QRegion, QPainterPath
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QGridLayout, QListWidget, QListWidgetItem, QLabel, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QStackedWidget,
)

from style import (
    apply_style,
    build_sidebar,
    build_header,
    set_header_text,
    CONTENT_BG,
    WOOD_BROWN,
    WOOD_BROWN_DARK,
    CARD,
    INK,
    INK_SOFT,
    LINE,
    ACCENT,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_RADIUS,
    SIDEBAR_WIDTH,
    HEADER_HEIGHT,
    ICON_SIZE,
    BODY_BG,
    _make_icon_svg,
    _make_icon_pixmap,
)
from seedata_qt import build_data_pivot_page
from plot_page import PlotPage
from plot_spec import SPECS




# =============================================================================
# 一、内嵌 SVG 装饰图形
# =============================================================================

def _make_tree_pixmap(size: int = 92) -> QPixmap:
    """把树木 SVG 字符串通过 QSvgRenderer 渲染为 QPixmap（内嵌，无需图片文件）。"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 92 92">
        <circle cx="46" cy="36" r="22" fill="{ACCENT}"/>
        <circle cx="32" cy="46" r="15" fill="{WOOD_BROWN}"/>
        <circle cx="60" cy="46" r="15" fill="{WOOD_BROWN}"/>
        <circle cx="46" cy="30" r="13" fill="#9DB45A"/>
        <rect x="41" y="52" width="10" height="26" rx="3" fill="{WOOD_BROWN_DARK}"/>
        <path d="M22 82 H70" stroke="{WOOD_BROWN}" stroke-width="3" stroke-linecap="round"/>
    </svg>'''
    renderer = QSvgRenderer(bytearray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pix


def _make_leaf_pixmap(size: int = 80) -> QPixmap:
    """把叶脉装饰 SVG 通过 QSvgRenderer 渲染为 QPixmap。"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 80 80">
        <path d="M8,68 Q35,35 68,8" stroke="{ACCENT}" stroke-width="2.5" fill="none" stroke-opacity="0.35"/>
        <path d="M16,72 Q42,42 72,16" stroke="{WOOD_BROWN}" stroke-width="1.5" fill="none" stroke-opacity="0.25"/>
        <path d="M28,76 Q50,50 76,28" stroke="{ACCENT}" stroke-width="1" fill="none" stroke-opacity="0.35"/>
    </svg>'''
    renderer = QSvgRenderer(bytearray(svg.encode("utf-8")))
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pix


def _build_tree_emblem() -> QWidget:
    """构建 140×140 圆形树木徽标卡片。"""
    card = QWidget()
    card.setFixedSize(140, 140)
    card.setStyleSheet(f"""
        QWidget {{
            background-color: {CARD};
            border-radius: 70px;
        }}
    """)
    # 柔和外阴影
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(20)
    shadow.setOffset(0, 2)
    shadow.setColor(QColor(0, 0, 0, 30))
    card.setGraphicsEffect(shadow)

    layout = QVBoxLayout(card)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    lbl = QLabel()
    lbl.setPixmap(_make_tree_pixmap(92))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(lbl)
    return card


# =============================================================================
# 二、欢迎页内容构建
# =============================================================================

def _build_welcome_page() -> QWidget:
    """
    构建欢迎态页面，包含：树木徽标、分隔线、欢迎标题、欢迎语、四角叶脉装饰。
    返回一个 QWidget（背景 CONTENT_BG）。
    """
    page = QWidget()
    page.setObjectName("welcomePage")
    page.setStyleSheet(f"QWidget#welcomePage{{background-color: {CONTENT_BG};}}")

    # 使用 QGridLayout 以便在四角放置装饰图形（不遮挡中央内容）
    grid = QGridLayout(page)
    grid.setContentsMargins(30, 30, 32, 30)
    grid.setSpacing(0)

    # 列：0=装饰, 1=弹性, 2=内容, 3=弹性, 4=装饰
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 0)
    grid.setColumnStretch(3, 1)
    grid.setColumnStretch(4, 0)

    # 行：0=装饰, 1=弹性, 2=内容, 3=弹性, 4=装饰
    grid.setRowStretch(0, 0)
    grid.setRowStretch(1, 1)
    grid.setRowStretch(2, 0)
    grid.setRowStretch(3, 1)
    grid.setRowStretch(4, 0)

    # ---- 四角叶脉装饰（基于 QSvgRenderer 渲染） ----
    for row, col in [(0, 0), (0, 4), (4, 0), (4, 4)]:
        leaf_label = QLabel()
        leaf_label.setPixmap(_make_leaf_pixmap(80))
        leaf_label.setFixedSize(80, 80)
        leaf_label.setStyleSheet("QLabel{background: transparent;}")
        leaf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(leaf_label, row, col, Qt.AlignmentFlag.AlignCenter)

    # ---- 中央内容（column=2, row=2） ----
    center_widget = QWidget()
    center_widget.setStyleSheet(".QWidget{background: transparent;}")
    center_layout = QVBoxLayout(center_widget)
    center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    center_layout.setSpacing(0)

    # 1. 树木徽标（140×140 圆形卡片，由 _build_tree_emblem() 构建）
    center_layout.addWidget(_build_tree_emblem(), alignment=Qt.AlignmentFlag.AlignCenter)

    # 2. 分隔线（64px × 3px, WOOD_BROWN 底色）
    center_layout.addSpacing(20)

    divider = QFrame()
    divider.setFixedSize(64, 3)
    divider.setStyleSheet(f"""
        QFrame {{
            background-color: {WOOD_BROWN};
            border: none;
            border-radius: 2px;
        }}
    """)
    center_layout.addWidget(divider, alignment=Qt.AlignmentFlag.AlignCenter)

    # 3. 欢迎标题 "欢迎使用木绘图"
    center_layout.addSpacing(16)

    welcome_title = QLabel("欢迎使用木绘图")
    welcome_title.setStyleSheet(f"""
        QLabel {{
            color: {INK};
            font-size: 30px;
            font-weight: 700;
            letter-spacing: 1px;
            background: transparent;
        }}
    """)
    center_layout.addWidget(welcome_title, alignment=Qt.AlignmentFlag.AlignCenter)

    # 4. 欢迎语段落
    center_layout.addSpacing(12)

    welcome_desc = QLabel(
        "这是一个智能绘图平台。\n请从左侧菜单选择功能模块以开始使用"
    )
    welcome_desc.setWordWrap(True)
    welcome_desc.setMaximumWidth(440)
    welcome_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
    welcome_desc.setStyleSheet(f"""
        QLabel {{
            color: {INK_SOFT};
            font-size: 15px;
            line-height: 1.7;
            background: transparent;
        }}
    """)
    center_layout.addWidget(welcome_desc, alignment=Qt.AlignmentFlag.AlignCenter)

    # 将中央内容放入 grid 的 (2, 2) 位置
    grid.addWidget(center_widget, 2, 2, Qt.AlignmentFlag.AlignCenter)

    return page


# =============================================================================
# 三、辅助：添加菜单项（复用 style.py 的内嵌 SVG 图标方案）
# =============================================================================

from PySide6.QtGui import QIcon

def _add_menu_item(menu_list: QListWidget, text: str, icon_shape: str) -> None:
    """向菜单列表中添加带内嵌 SVG 图标的项。"""
    svg_str = _make_icon_svg(INK, icon_shape)
    pixmap = _make_icon_pixmap(svg_str)
    icon = QIcon(pixmap)

    item = QListWidgetItem(text)
    item.setIcon(icon)
    # 统一行高：QSS 的 item padding/margin 不计入 QListView 滚动范围计算，
    # 显式声明 sizeHint 后滚动条范围才正确（配合 setUniformItemSizes）。
    item.setSizeHint(QSize(0, 46))
    menu_list.addItem(item)


# =============================================================================
# 四、主窗口
# =============================================================================

class MainWindow(QMainWindow):
    """「木绘图」主窗口（欢迎态）：左菜单 + 右标题区 + 欢迎内容。"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("木绘图")
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._setup_ui()

    def _setup_ui(self):
        """搭建主窗口布局。"""
        # ---- 窗口外观 ----
        self.setStyleSheet(f"QMainWindow {{ background-color: {BODY_BG}; }}")

        # ---- 中央部件 ----
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        # 整体水平布局：左菜单 + 右内容（margin=0, spacing=0）
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

        # 右侧标题区：初始为欢迎页文案，菜单点击后由 set_header_text 联动更新
        self.header = build_header("欢迎使用", "木绘图 › 首页")
        right_layout.addWidget(self.header)

        # 右侧内容区：QStackedWidget 装载全部页面（欢迎/数据透视/绘图/占位页）
        self.content_area = QWidget()
        self.content_area.setObjectName("contentArea")
        self.content_area.setStyleSheet(f"QWidget#contentArea{{background-color: {CONTENT_BG};}}")

        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # QStackedWidget 扩展点（页面常驻，绝不销毁 → 状态天然持久化）
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"QStackedWidget{{background-color: {CONTENT_BG};}}")

        # ① 绘图页：规格驱动，来自 SPECS（散点 / 折线 / 箱线 / 直方 四图）。
        # 每页完全独立：不注入任何共享数据源，各自拖文件、各自持有一个 DataFrame。
        self._plot_pages = {
            name: PlotPage(spec)   # 页面自持数据，独立读文件
            for name, spec in SPECS.items()
        }

        # ② 数据透视页：独立模块，同样自持数据，不向任何页面广播。
        self._data_pivot_page = build_data_pivot_page()

        # ⑤ 欢迎页
        self._welcome = _build_welcome_page()

        # 角色 -> 控件（导航用 setCurrentWidget，不依赖 index）
        self._pages = {
            "welcome":    self._welcome,
            "data_pivot": self._data_pivot_page,
            "scatter":    self._plot_pages["scatter"],
            "line":       self._plot_pages["line"],
            "box":        self._plot_pages["box"],
            "hist":       self._plot_pages["hist"],
            "bar":        self._plot_pages["bar"],
            "count":      self._plot_pages["count"],
            "point":      self._plot_pages["point"],
            "violin":     self._plot_pages["violin"],
            "strip":      self._plot_pages["strip"],
            "swarm":      self._plot_pages["swarm"],
            "boxen":      self._plot_pages["boxen"],
            "kde":        self._plot_pages["kde"],
            "ecdf":       self._plot_pages["ecdf"],
            "rug":        self._plot_pages["rug"],
            "reg":        self._plot_pages["reg"],
            "resid":      self._plot_pages["resid"],
            "heat":       self._plot_pages["heat"],
            "clustermap": self._plot_pages["clustermap"],
            "rel":        self._plot_pages["rel"],
            "dis":        self._plot_pages["dis"],
            "cat":        self._plot_pages["cat"],
            "pair":       self._plot_pages["pair"],
            "joint":      self._plot_pages["joint"],
            "lm":         self._plot_pages["lm"],
        }
        for w in self._pages.values():
            self.stack.addWidget(w)
        content_layout.addWidget(self.stack)

        right_layout.addWidget(self.content_area)
        main_layout.addWidget(right_area)

        # ---- 填充菜单占位项（4项：1/2/3/4） ----
        self._populate_menu()

        # 使用 itemClicked（每次点击均触发）替代 currentRowChanged（同项不重复触发）
        self.menu_list.itemClicked.connect(self._on_menu_item_clicked)

        # ---- 窗口柔和外投影 ----
        self._apply_window_shadow()

    def _apply_window_shadow(self):
        """为中央部件添加柔和外投影（QMainWindow 无法直接加阴影）。"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.centralWidget().setGraphicsEffect(shadow)

    def resizeEvent(self, event):
        """窗口尺寸变化时重新计算圆角遮罩（匹配 HTML .app border-radius:18px）。"""
        super().resizeEvent(event)
        path = QPainterPath()
        path.addRoundedRect(self.centralWidget().rect(), WINDOW_RADIUS, WINDOW_RADIUS)
        self.centralWidget().setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _populate_menu(self):
        """填充菜单项：数据透视 + 多个可折叠分组（绘图 / 分布 / 回归）。

        每个分组独立展开/收起：父项点击切换，子项默认隐藏且不可选中。
        """
        # 角色常量，用于稳定标识每行（避免绝对行号漂移）
        R = Qt.ItemDataRole.UserRole
        self._menu_groups: dict[str, dict] = {}

        # 顶层项
        _add_menu_item(self.menu_list, "数据透视", "circle")
        item = self.menu_list.item(self.menu_list.count() - 1)
        item.setData(R, "data_pivot")

        # 分组定义：(父项 role, 父项基础文案, [(子项文本, 子项 role), ...])
        groups = [
            ("plot_parent", "📊 绘图", [
                ("散点图", "scatter"), ("折线图", "line"), ("箱线图", "box"),
                ("直方图", "hist"), ("柱状图", "bar"), ("计数图", "count"),
                ("点估计图", "point"), ("小提琴图", "violin"), ("散点条图", "strip"),
                ("蜂群图", "swarm"), ("增强箱线图", "boxen"),
            ]),
            ("dist_parent", "📊 分布", [
                ("核密度图", "kde"), ("累积分布图", "ecdf"), ("边缘地毯图", "rug"),
            ]),
            ("reg_parent", "📊 回归", [
                ("回归图", "reg"), ("残差图", "resid"),
            ]),
            ("heat_parent", "📊 热力图", [
                ("热力图", "heat"), ("聚类热图", "clustermap"),
            ]),
            ("facet_parent", "📊 分面", [
                ("联合分布图", "joint"), ("成对矩阵图", "pair"),
                ("关系分面图", "rel"), ("分布分面图", "dis"),
                ("分类分面图", "cat"), ("回归分面图", "lm"),
            ]),
        ]
        for parent_role, parent_text, children in groups:
            _add_menu_item(self.menu_list, f"{parent_text} ▸", "diamond")
            parent = self.menu_list.item(self.menu_list.count() - 1)
            parent.setData(R, parent_role)

            child_items: list[QListWidgetItem] = []
            for text, role in children:
                _add_menu_item(self.menu_list, f"    {text}", "circle")
                item = self.menu_list.item(self.menu_list.count() - 1)
                item.setData(R, role)
                item.setHidden(True)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                child_items.append(item)

            self._menu_groups[parent_role] = {
                "parent": parent,
                "base_text": parent_text,
                "children": child_items,
                "expanded": False,
            }

    def _on_menu_item_clicked(self, item: QListWidgetItem):
        """按 UserRole 处理：分组父项折叠/展开（不跳页）、子项导航到对应页面。"""
        role = item.data(Qt.ItemDataRole.UserRole)
        if role is None:
            return

        # ---- 分组父项：只做展开 / 收起，不导航 ----
        if role in self._menu_groups:
            grp = self._menu_groups[role]
            grp["expanded"] = not grp["expanded"]
            for child in grp["children"]:
                child.setHidden(not grp["expanded"])
                if grp["expanded"]:
                    child.setFlags(child.flags() | Qt.ItemFlag.ItemIsSelectable)
                else:
                    child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            arrow = "▾" if grp["expanded"] else "▸"
            grp["parent"].setText(f"{grp['base_text']} {arrow}")
            self.menu_list.setCurrentItem(item)  # 保持父项选中高亮
            return

        # ---- 叶子项：导航到对应 stack 页面（setCurrentWidget 保留状态）----
        mapping = {
            "data_pivot": self._pages["data_pivot"],
            "scatter":    self._pages["scatter"],
            "line":       self._pages["line"],
            "box":        self._pages["box"],
            "hist":       self._pages["hist"],
            "bar":        self._pages["bar"],
            "count":      self._pages["count"],
            "point":      self._pages["point"],
            "violin":     self._pages["violin"],
            "strip":      self._pages["strip"],
            "swarm":      self._pages["swarm"],
            "boxen":      self._pages["boxen"],
            "kde":        self._pages["kde"],
            "ecdf":       self._pages["ecdf"],
            "rug":        self._pages["rug"],
            "reg":        self._pages["reg"],
            "resid":      self._pages["resid"],
            "heat":       self._pages["heat"],
            "clustermap": self._pages["clustermap"],
            "rel":        self._pages["rel"],
            "dis":        self._pages["dis"],
            "cat":        self._pages["cat"],
            "pair":       self._pages["pair"],
            "joint":      self._pages["joint"],
            "lm":         self._pages["lm"],
        }
        if role in mapping:
            self.stack.setCurrentWidget(mapping[role])
            title, breadcrumb = {
                "data_pivot": ("数据透视", "木绘图 › 数据透视"),
                "scatter":    ("散点图",   "木绘图 › 绘图 › 散点图"),
                "line":       ("折线图",   "木绘图 › 绘图 › 折线图"),
                "box":        ("箱线图",   "木绘图 › 绘图 › 箱线图"),
                "hist":       ("直方图",   "木绘图 › 绘图 › 直方图"),
                "bar":        ("柱状图",   "木绘图 › 绘图 › 柱状图"),
                "count":      ("计数图",   "木绘图 › 绘图 › 计数图"),
                "point":      ("点估计图", "木绘图 › 绘图 › 点估计图"),
                "violin":     ("小提琴图", "木绘图 › 绘图 › 小提琴图"),
                "strip":      ("散点条图", "木绘图 › 绘图 › 散点条图"),
                "swarm":      ("蜂群图",   "木绘图 › 绘图 › 蜂群图"),
                "boxen":      ("增强箱线图", "木绘图 › 绘图 › 增强箱线图"),
                "kde":        ("核密度图",   "木绘图 › 绘图 › 核密度图"),
                "ecdf":       ("累积分布图", "木绘图 › 绘图 › 累积分布图"),
                "rug":        ("边缘地毯图", "木绘图 › 绘图 › 边缘地毯图"),
                "reg":        ("回归图",   "木绘图 › 绘图 › 回归图"),
                "resid":      ("残差图",   "木绘图 › 绘图 › 残差图"),
                "heat":       ("热力图",   "木绘图 › 热力图 › 热力图"),
                "clustermap": ("聚类热图", "木绘图 › 热力图 › 聚类热图"),
                "rel":        ("关系分面图", "木绘图 › 分面 › 关系分面图"),
                "dis":        ("分布分面图", "木绘图 › 分面 › 分布分面图"),
                "cat":        ("分类分面图", "木绘图 › 分面 › 分类分面图"),
                "pair":       ("成对矩阵图", "木绘图 › 分面 › 成对矩阵图"),
                "joint":      ("联合分布图", "木绘图 › 分面 › 联合分布图"),
                "lm":         ("回归分面图", "木绘图 › 分面 › 回归分面图"),
            }[role]
            set_header_text(self.header, title, breadcrumb)


# =============================================================================
# 五、主入口
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # 设置全局字体
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    # 注入统一样式（必须先于窗口实例化）
    apply_style(app)

    # 启动主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())
