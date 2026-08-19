"""
seedata_qt — 「数据透视」功能页面（前端）。

完全复用 style.py 的样式系统，所有统计计算走 seedata_core 接口。
对外暴露 build_data_pivot_page() 供主窗口 QStackedWidget 接入。
"""

import sys
import os
from typing import Optional, Any

import pandas as pd
# style 必须先于任何 matplotlib 模块导入：它是全项目唯一的
# matplotlib.use("QtAgg") 入口（见 style.py 顶部注释），保证后端在
# import FigureCanvasQTAgg / matplotlib.pyplot 之前已选定。
from style import (
    apply_style,
    build_header,
    CARD, BEIGE, BEIGE_SOFT, LINE, INK, INK_SOFT, WOOD_BROWN, WOOD_BROWN_DARK,
    CARD_RADIUS,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QFileDialog,
    QGraphicsDropShadowEffect, QSizePolicy, QAbstractItemView, QMessageBox,
)
from plot_widgets import DropZoneBase
from seedata_core import (
    read_table,
    infer_column_types,
    get_preview,
    replace_custom_nulls,
    null_summary,
    describe_all,
    numeric_columns,
    make_boxplot,
    export_stats,
)


# =============================================================================
# 工具：通用 QSS 构建（避免在代码中重复写 f-string）
# =============================================================================

def _card_style() -> str:
    return f"""
        QWidget#cardContainer {{
            background-color: {CARD};
            border: 1px solid {LINE};
            border-radius: {CARD_RADIUS};
        }}
    """


def _panel_title_style() -> str:
    return f"""
        QLabel {{
            color: {INK};
            font-size: 16px;
            font-weight: 600;
            background: transparent;
        }}
    """


def _subtitle_style() -> str:
    return f"""
        QLabel {{
            color: {INK_SOFT};
            font-size: 14px;
            font-weight: 500;
            background: transparent;
        }}
    """


# =============================================================================
# 拖拽框组件
# =============================================================================

class DropZone(DropZoneBase):
    """「数据透视」拖放区：继承共享拖放行为，保留 QSS 虚线边框与按钮外观。

    拖入校验、状态机、选文件与信号发射统一由 DropZoneBase 实现
    （与 plot_widgets.FileDropZone 同源，避免两份漂移实现）；
    本类只定制外观：QSS 虚线边框（default/valid/invalid）与提示文案。
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # 自定义 QWidget 子类的 QSS 边框/背景需 WA_StyledBackground 才渲染
        #（QFrame 等内置类自动渲染）；缺失会导致虚线框与状态色不显示
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("dropZone")
        self.setMinimumHeight(100)
        self._apply_state()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._hint = QLabel("拖入 CSV / Excel 文件到此处\n支持 .csv  .xlsx  .xls")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"""
            QLabel {{
                color: {INK_SOFT};
                font-size: 14px;
                background: transparent;
            }}
        """)
        layout.addWidget(self._hint)

        open_btn = QPushButton("或点击此处选择文件")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {WOOD_BROWN};
                border-radius: 8px;
                padding: 6px 18px;
                color: {WOOD_BROWN};
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {WOOD_BROWN};
                color: #FFFFFF;
            }}
        """)
        open_btn.clicked.connect(self._choose_file)
        layout.addWidget(open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def _show_path(self, path: str) -> None:
        """拖入/选择成功后把提示文字替换为文件路径（与散点图拖放区一致）。"""
        self._hint.setText(path)

    def mousePressEvent(self, event):
        """保持本页原有交互：仅「或点击此处选择文件」按钮可打开文件选择，
        点击拖拽框其他区域（提示文字/空白）无动作。

        基类 DropZoneBase 的整区点击是散点图页（FileDropZone）的交互方式，
        本页不采用，避免点击空白误弹文件对话框。
        """

    def _apply_state(self) -> None:
        """按当前状态刷新虚线边框与底色（default/valid/invalid）。"""
        colors = {
            "default": "#B9966B",
            "valid": "#4CAF50",   # 绿：可接受
            "invalid": "#F44336",  # 红：非受支持格式
        }
        bgs = {
            "default": BEIGE,
            "valid": "#E6F4EA",
            "invalid": "#FDECEA",
        }
        # QWidget 选择器：DropZoneBase 基类为 QWidget，不再匹配 QFrame#dropZone
        self.setStyleSheet(f"""
            QWidget#dropZone {{
                border: 2px dashed {colors[self._state]};
                border-radius: 12px;
                background-color: {bgs[self._state]};
            }}
        """)


# =============================================================================
# 脏数据警示条
# =============================================================================

class DirtyWarningBar(QFrame):
    """琥珀色警示条，检测到脏数据列时显示。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("dirtyWarningBar")
        self.setStyleSheet(f"""
            QFrame#dirtyWarningBar {{
                background-color: #F7ECDA;
                border-left: 4px solid #B26A00;
                border-radius: 6px;
                padding: 10px 14px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet(f"""
            QLabel {{
                color: #B26A00;
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
        """)
        layout.addWidget(self._label)

        self.hide()

    def show_warning(self, dirty_cols: list[str]) -> None:
        cols_str = "、".join(dirty_cols)
        self._label.setText(
            f"⚠ 检测到脏数据列：{cols_str}（含混合数据类型）。"
            "建议先对数据进行清理，否则后续的空值统计与描述性统计结果可能出现错误。"
        )
        self.show()

    def hide_warning(self) -> None:
        self.hide()


# =============================================================================
# 冻结首列的描述性统计表
# =============================================================================

class DescriptiveStatsTable(QWidget):
    """描述性统计表，首列「统计项」在横向滚动时冻结固定不动。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.main = QTableWidget()
        self.main.verticalHeader().setVisible(False)
        self.main.verticalHeader().setDefaultSectionSize(40)
        self.main.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.main)

        # 冻结首列的覆盖表 — 作为 main 的子控件，自然跟随 main 的裁剪和坐标
        self.frozen = QTableWidget(self.main)
        self.frozen.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen.horizontalHeader().setVisible(False)
        self.frozen.verticalHeader().setVisible(False)
        self.frozen.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frozen.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frozen.raise_()

        self.main.horizontalScrollBar().valueChanged.connect(self._sync_geom)
        self.main.verticalScrollBar().valueChanged.connect(
            lambda v: self.frozen.verticalScrollBar().setValue(v))
        self.main.horizontalHeader().sectionResized.connect(self._sync_geom)

        self._apply_styles()

    def _apply_styles(self) -> None:
        qss = f"""
            QTableWidget {{
                background-color: {CARD};
                border: 1px solid {LINE};
                border-radius: 8px;
                gridline-color: {LINE};
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 10px;
            }}
            QHeaderView::section {{
                background-color: {BEIGE};
                border: none;
                border-bottom: 1px solid {LINE};
                padding: 6px 10px;
                font-size: 14px;
                font-weight: 600;
                color: {INK};
            }}
        """
        self.main.setStyleSheet(qss)
        # frozen 覆盖表：无边框、无圆角（靠 main 的表框裁剪）
        self.frozen.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CARD};
                border: none;
                gridline-color: {LINE};
                font-size: 14px;
            }}
            QTableWidget::item {{
                background-color: #EFE6D2;
                padding: 4px 10px;
                font-weight: 600;
            }}
        """)

    def set_data(self, stat_names: list[str], columns: list[str], matrix: list[list]) -> None:
        """填充数据：stat_names 首列值，columns 数据列名，matrix 二维值（None→—）。

        空数据（stat_names/columns 均为空）时列数彻底归零：
        连同「统计项」表头一起清除——换数据集后未点「确认统计」不残留任何表头。
        """
        n_rows, n_cols = len(stat_names), len(columns)
        self.main.setRowCount(n_rows)
        self.main.setColumnCount(1 + n_cols if n_cols else 0)
        if n_cols:
            self.main.setHorizontalHeaderLabels(["统计项"] + columns)
        self.frozen.setRowCount(n_rows)
        self.frozen.setColumnCount(1 if n_rows else 0)

        for r in range(n_rows):
            font_bold = self.main.font()
            font_bold.setBold(True)

            # 主表第 0 列
            stat_item = QTableWidgetItem(stat_names[r])
            stat_item.setFlags(stat_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            stat_item.setFont(font_bold)
            self.main.setItem(r, 0, stat_item)

            # 冻结表第 0 列
            frozen_item = QTableWidgetItem(stat_names[r])
            frozen_item.setFlags(frozen_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            frozen_item.setFont(font_bold)
            frozen_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frozen.setItem(r, 0, frozen_item)

            # 数据列
            for c in range(n_cols):
                val = matrix[r][c]
                val_str = "—" if val is None else str(val)
                item = QTableWidgetItem(val_str)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if val_str == "—":
                    item.setForeground(QColor(INK_SOFT))
                self.main.setItem(r, 1 + c, item)

        self._sync_geom()

    def _sync_geom(self, *_) -> None:
        """同步冻结表几何位置，使其始终覆盖在主表 viewport 的首列上方。"""
        if self.main.rowCount() == 0:
            return
        w = self.main.columnWidth(0)
        if w <= 0:
            return
        # frozen 是 main 的子控件 → 相对于 main 的 viewport 定位
        vp = self.main.viewport()
        self.frozen.setGeometry(vp.x(), vp.y(), w, vp.height())
        for r in range(self.main.rowCount()):
            self.frozen.setRowHeight(r, self.main.rowHeight(r))
        self.frozen.setColumnWidth(0, w)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._sync_geom()


# =============================================================================
# 数据透视主页面
# =============================================================================

class DataPivotPage(QWidget):
    """「数据透视」功能页面（可独立返回，供 QStackedWidget 接入）。

    数据完全独立：本页自持 DataFrame，不向任何页面广播（与绘图页互不感知）。
    """

    def __init__(self):
        super().__init__()
        self._df: Optional[pd.DataFrame] = None
        self._col_types: dict[str, str] = {}
        self._canvas: Optional[FigureCanvasQTAgg] = None
        # 修复（Q3）：保存「确认统计」时清理后的数据，供箱线图使用，
        # 保证统计表与箱线图的数据口径一致
        self._clean_df: Optional[pd.DataFrame] = None
        # 描述性统计结果（确认统计后填充）；与 _clean_df 一致在 __init__ 统一初始化，
        # 避免运行期靠 hasattr 兜底判断
        self._desc_df: Optional[pd.DataFrame] = None
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """构建完整页面布局。"""
        self.setStyleSheet(f"DataPivotPage{{background-color: {self._parent_bg()};}}")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # ---- 滚动内容区 ----
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea{{background-color: {self._parent_bg()};}}")

        content = QWidget()
        content.setStyleSheet(f".QWidget{{background-color: {self._parent_bg()};}}")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(32, 26, 32, 26)
        content_layout.setSpacing(22)

        # ---- 卡片 1：数据显示 ----
        card1 = self._build_card_data_preview()
        content_layout.addWidget(card1)

        # ---- 卡片 2：数据统计显示 ----
        card2 = self._build_card_stats()
        content_layout.addWidget(card2)

        content_layout.addStretch()
        scroll.setWidget(content)
        outer_layout.addWidget(scroll)

    def _parent_bg(self) -> str:
        from style import CONTENT_BG
        return CONTENT_BG

    @staticmethod
    def _make_card_container() -> QWidget:
        card = QWidget()
        card.setObjectName("cardContainer")
        card.setStyleSheet(_card_style())
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 30))
        card.setGraphicsEffect(shadow)
        return card

    @staticmethod
    def _make_placeholder(text: str) -> QLabel:
        """创建内容区窄条占位：无内容时显示 56px 虚线浅米条，有内容后隐藏展开。"""
        ph = QLabel(text)
        ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph.setFixedHeight(56)
        ph.setStyleSheet(
            f"QLabel{{background:{BEIGE_SOFT};border:1px dashed {WOOD_BROWN};"
            f"border-radius:8px;color:{INK_SOFT};font-size:13px;}}")
        return ph

    @staticmethod
    def _set_placeholder_visible(ph: QLabel, real: QWidget,
                                 subtitle: Optional[QLabel] = None,
                                 content: bool = False) -> None:
        """窄条占位 ↔ 内容切换：content=True 展开真实组件，否则显示窄条。"""
        ph.setVisible(not content)
        real.setVisible(content)
        if subtitle is not None:
            subtitle.setVisible(content)

    # ------------------------------------------------------------------
    # 卡片 1：数据显示
    # ------------------------------------------------------------------

    def _build_card_data_preview(self) -> QWidget:
        card = self._make_card_container()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 面板标题
        title = QLabel("数据显示")
        title.setStyleSheet(_panel_title_style())
        layout.addWidget(title)

        # 拖拽框
        self._drop_zone = DropZone()
        self._drop_zone.fileDropped.connect(self._on_file_loaded)
        layout.addWidget(self._drop_zone)

        # 脏数据警示条
        self._dirty_bar = DirtyWarningBar()
        layout.addWidget(self._dirty_bar)

        # 预览表格窄条占位：未加载文件时不显示空表格，仅留提示条
        self._preview_ph = self._make_placeholder("载入文件后显示数据预览")
        layout.addWidget(self._preview_ph)

        # 预览表格（列标题分两行：列名 + 类型）
        self._preview_table = QTableWidget()
        self._preview_table.setMinimumHeight(260)
        self._preview_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._preview_table.verticalHeader().setVisible(False)
        self._preview_table.verticalHeader().setDefaultSectionSize(40)
        self._preview_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {CARD};
                border: 1px solid {LINE};
                border-radius: 8px;
                gridline-color: {LINE};
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 10px;
            }}
            QHeaderView::section {{
                background-color: {BEIGE};
                border: none;
                border-bottom: 1px solid {LINE};
                padding: 6px 10px;
                font-size: 14px;
                font-weight: 600;
                color: {INK};
            }}
        """)
        layout.addWidget(self._preview_table)
        self._preview_table.hide()  # 初始窄条占位

        return card

    # ------------------------------------------------------------------
    # 卡片 2：数据统计显示
    # ------------------------------------------------------------------

    def _build_card_stats(self) -> QWidget:
        card = self._make_card_container()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 面板标题
        title = QLabel("数据统计显示")
        title.setStyleSheet(_panel_title_style())
        layout.addWidget(title)

        # ---- 空值样式输入行 ----
        null_row = QHBoxLayout()
        null_row.setSpacing(10)

        null_label = QLabel("自定义空值样式")
        null_label.setStyleSheet(_subtitle_style())
        null_row.addWidget(null_label)

        self._null_input = QLineEdit()
        self._null_input.setPlaceholderText(
            "可留空（默认 numpy/pandas）；如输入 - 或 NA，多个用逗号分隔"
        )
        self._null_input.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {LINE};
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                background-color: {CARD};
                color: {INK};
            }}
            QLineEdit:focus {{
                border-color: {WOOD_BROWN};
            }}
        """)
        null_row.addWidget(self._null_input, stretch=1)

        confirm_btn = QPushButton("确认统计")
        confirm_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {WOOD_BROWN};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 6px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {WOOD_BROWN_DARK};
            }}
            QPushButton:disabled {{
                background-color: {LINE};
                color: {INK_SOFT};
            }}
        """)
        confirm_btn.clicked.connect(self._on_confirm_stats)
        self._confirm_btn = confirm_btn
        # 初始禁用（未读文件时）
        self._confirm_btn.setEnabled(False)
        null_row.addWidget(confirm_btn)

        layout.addLayout(null_row)

        # ---- 空值统计表 ----
        self._null_subtitle = QLabel("空值统计（每列空值个数 / 空值率）")
        self._null_subtitle.setStyleSheet(_subtitle_style())
        layout.addWidget(self._null_subtitle)

        # 窄条占位：未确认统计时不显示空表格
        self._null_ph = self._make_placeholder("确认统计后显示空值统计")
        layout.addWidget(self._null_ph)

        self._null_table = QTableWidget()
        self._null_table.setMinimumHeight(250)
        self._null_table.verticalHeader().setVisible(False)
        self._null_table.verticalHeader().setDefaultSectionSize(40)
        # 列宽由 header 自动管理：前两列按内容自适应，最后一列拉伸填满剩余空间。
        # 注意不可再手动调用 resizeColumnsToContents()——它与 stretchLastSection
        # 混用会互相覆盖（实测第二次填充后最后一列被压回内容宽，表格骤缩/横向移动）
        self._null_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents)
        self._null_table.horizontalHeader().setStretchLastSection(True)
        self._null_table.setStyleSheet(self._table_style())
        layout.addWidget(self._null_table)
        self._null_subtitle.hide()
        self._null_table.hide()  # 初始窄条占位

        # ---- 描述性统计表（首列冻结） ----
        self._describe_subtitle = QLabel("描述性统计（df.describe(include='all')）")
        self._describe_subtitle.setStyleSheet(_subtitle_style())
        layout.addWidget(self._describe_subtitle)

        # 窄条占位：未确认统计时不显示空表格
        self._describe_ph = self._make_placeholder("确认统计后显示描述性统计")
        layout.addWidget(self._describe_ph)

        self._describe_stats_table = DescriptiveStatsTable()
        self._describe_stats_table.setMinimumHeight(500)
        layout.addWidget(self._describe_stats_table)
        self._describe_subtitle.hide()
        self._describe_stats_table.hide()  # 初始窄条占位

        # ---- 按钮行 ----
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        boxplot_btn = QPushButton("📊 对数值列绘制箱线图")
        boxplot_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        boxplot_btn.setStyleSheet(self._primary_btn_style())
        boxplot_btn.clicked.connect(self._on_draw_boxplot)
        self._boxplot_btn = boxplot_btn
        self._boxplot_btn.setEnabled(False)
        btn_row.addWidget(boxplot_btn)

        export_btn = QPushButton("⬇ 导出统计结果到 Excel")
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setStyleSheet(self._secondary_btn_style())
        export_btn.clicked.connect(self._on_export)
        self._export_btn = export_btn
        self._export_btn.setEnabled(False)
        btn_row.addWidget(export_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # ---- 箱线图展示区 ----
        self._boxplot_subtitle = QLabel("箱线图展示区")
        self._boxplot_subtitle.setStyleSheet(_subtitle_style())
        layout.addWidget(self._boxplot_subtitle)

        # 窄条占位：未绘制时不显示占位大框
        self._boxplot_ph = self._make_placeholder("绘制后显示箱线图")
        layout.addWidget(self._boxplot_ph)
        self._boxplot_subtitle.hide()

        self._boxplot_container = QWidget()
        self._boxplot_container.setMinimumHeight(500)
        self._boxplot_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._boxplot_container.setStyleSheet(f"""
            QWidget#boxplotContainer {{
                background-color: {CARD};
                border: 1px solid {LINE};
                border-radius: {CARD_RADIUS};
            }}
        """)
        self._boxplot_container.setObjectName("boxplotContainer")
        self._boxplot_layout = QVBoxLayout(self._boxplot_container)
        self._boxplot_layout.setContentsMargins(10, 10, 10, 10)

        placeholder = QLabel("拖入数据并确认统计后，点击上方按钮绘制箱线图")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {INK_SOFT}; font-size: 13px; background: transparent;")
        self._boxplot_layout.addWidget(placeholder)

        layout.addWidget(self._boxplot_container)
        self._boxplot_container.hide()  # 初始窄条占位

        return card

    @staticmethod
    def _table_style() -> str:
        return f"""
            QTableWidget {{
                background-color: {CARD};
                border: 1px solid {LINE};
                border-radius: 8px;
                gridline-color: {LINE};
                font-size: 14px;
            }}
            QTableWidget::item {{
                padding: 4px 10px;
            }}
            QHeaderView::section {{
                background-color: {BEIGE};
                border: none;
                border-bottom: 1px solid {LINE};
                padding: 6px 10px;
                font-size: 14px;
                font-weight: 600;
                color: {INK};
            }}
        """

    @staticmethod
    def _primary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: {WOOD_BROWN};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {WOOD_BROWN_DARK};
            }}
            QPushButton:disabled {{
                background-color: {LINE};
                color: {INK_SOFT};
            }}
        """

    @staticmethod
    def _secondary_btn_style() -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {WOOD_BROWN};
                border: 1.5px solid {WOOD_BROWN};
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {BEIGE};
            }}
            QPushButton:disabled {{
                border-color: {LINE};
                color: {INK_SOFT};
            }}
        """

    # ------------------------------------------------------------------
    # 交互：读文件
    # ------------------------------------------------------------------

    def _on_file_loaded(self, path: str) -> None:
        """拖入或选择文件后读取并显示预览。"""
        try:
            self._df = read_table(path)
        except Exception as exc:
            self._show_status(f"文件读取失败：{exc}")
            return

        # 修复（Q3）：换文件后清理数据即失效，避免箱线图用到上一个文件的清理结果
        self._clean_df = None
        self._desc_df = None
        self._col_types = infer_column_types(self._df)
        dirty_cols = [col for col, t in self._col_types.items() if t == "脏数据列"]

        # 脏数据警示条
        if dirty_cols:
            self._dirty_bar.show_warning(dirty_cols)
        else:
            self._dirty_bar.hide_warning()

        # 清空上一文件的统计展示，避免与新文件数据混淆：
        # 列数一并归零，表头随列消失——数据集加载后未点「确认统计」不显示任何表头
        #（空值统计表 3 列表头、描述性统计表「统计项」表头均彻底清除）
        self._null_table.clear()
        self._null_table.setRowCount(0)
        self._null_table.setColumnCount(0)
        self._describe_stats_table.set_data([], [], [])
        self._reset_boxplot_area()
        # 窄条占位切换：预览表展开；统计区回到窄条（新文件尚未确认统计）
        self._set_placeholder_visible(self._preview_ph, self._preview_table, content=True)
        self._set_placeholder_visible(self._null_ph, self._null_table, self._null_subtitle)
        self._set_placeholder_visible(self._describe_ph, self._describe_stats_table,
                                      self._describe_subtitle)
        self._set_placeholder_visible(self._boxplot_ph, self._boxplot_container,
                                      self._boxplot_subtitle)
        # 填充预览表
        col_names, rows = get_preview(self._df, 4)
        self._populate_preview_table(col_names, rows)

        # 激活统计按钮
        self._confirm_btn.setEnabled(True)
        self._boxplot_btn.setEnabled(False)
        self._export_btn.setEnabled(False)

    def _reset_boxplot_area(self) -> None:
        """清空箱线图展示区并恢复占位提示（换文件或重置时使用）。"""
        while self._boxplot_layout.count():
            item = self._boxplot_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        placeholder = QLabel("拖入数据并确认统计后，点击上方按钮绘制箱线图")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: {INK_SOFT}; font-size: 13px; background: transparent;")
        self._boxplot_layout.addWidget(placeholder)


    def _populate_preview_table(self, col_names: list[str], rows: list[list[Any]]) -> None:
        """填充预览表：每列显示列名 + 类型（双行表头），下方显示前 3 行。"""
        self._preview_table.clear()
        n_cols = len(col_names)
        n_rows = len(rows) + 1  # 类型行 + 数据行

        self._preview_table.setColumnCount(n_cols)
        self._preview_table.setRowCount(n_rows)

        # 第 0 行：列名
        for c, name in enumerate(col_names):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            font = item.font()
            font.setBold(True)
            item.setFont(font)

            # 脏数据列用琥珀色加粗
            col_type = self._col_types.get(name, "")
            if col_type == "脏数据列":
                item.setForeground(QColor("#B26A00"))
            self._preview_table.setItem(0, c, item)

        # 第 1 行：类型标注
        for c, name in enumerate(col_names):
            col_type = self._col_types.get(name, "")
            if col_type == "脏数据列":
                display = "（脏数据列）"
                color = "#B26A00"
                bold = True
            else:
                display = f"（{col_type}）"
                color = INK_SOFT
                bold = False

            type_item = QTableWidgetItem(display)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setForeground(QColor(color))
            font = type_item.font()
            font.setBold(bold)
            type_item.setFont(font)
            self._preview_table.setItem(1, c, type_item)

        # 数据行（从第 2 行开始）
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                val_str = str(val) if val is not None else ""
                item = QTableWidgetItem(val_str)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._preview_table.setItem(r + 2, c, item)

        # 自适应列宽
        self._preview_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # 交互：确认统计
    # ------------------------------------------------------------------

    def _on_confirm_stats(self) -> None:
        """按自定义空值样式清理后，填充空值统计表与描述性统计表。"""
        if self._df is None:
            return

        # 解析空值标记
        raw = self._null_input.text().strip()
        markers = [m.strip() for m in raw.split(",")] if raw else []

        # 清理空值（修复 Q3：保存清理结果，供箱线图复用）
        clean_df = replace_custom_nulls(self._df, markers)
        self._clean_df = clean_df

        # 空值统计
        null_data = null_summary(clean_df)
        self._populate_null_table(null_data)

        # 描述性统计
        self._desc_df = describe_all(clean_df)
        self._populate_describe_table(self._desc_df)

        # 激活绘图/导出按钮
        self._boxplot_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

        # 窄条占位切换：统计表展开
        self._set_placeholder_visible(self._null_ph, self._null_table, self._null_subtitle,
                                      content=True)
        self._set_placeholder_visible(self._describe_ph, self._describe_stats_table,
                                      self._describe_subtitle, content=True)

    def _populate_null_table(self, data: list[tuple[str, int, float]]) -> None:
        """填充空值统计表：列名 / 空值个数 / 空值率。"""
        self._null_table.clear()
        headers = ["列名", "空值个数", "空值率"]
        self._null_table.setColumnCount(3)
        self._null_table.setRowCount(len(data))
        self._null_table.setHorizontalHeaderLabels(headers)

        for r, (col_name, null_count, rate) in enumerate(data):
            # 列名
            name_item = QTableWidgetItem(col_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._null_table.setItem(r, 0, name_item)

            # 空值个数
            count_item = QTableWidgetItem(str(null_count))
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._null_table.setItem(r, 1, count_item)

            # 空值率（木棕加粗）
            rate_item = QTableWidgetItem(f"{rate:.2%}")
            rate_item.setFlags(rate_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            rate_item.setForeground(QColor(WOOD_BROWN))
            font = rate_item.font()
            font.setBold(True)
            rate_item.setFont(font)
            self._null_table.setItem(r, 2, rate_item)

        # 列宽不再手动 resizeColumnsToContents：ResizeToContents 模式 + stretchLastSection
        # 已由 header 自动管理（见 _build_card_stats 中表头配置），手动调用会与 stretch 冲突

    def _populate_describe_table(self, desc_df: pd.DataFrame) -> None:
        """填充描述性统计表（通过 DescriptiveStatsTable.set_data）。"""
        stat_names = list(desc_df.index)
        col_names = list(desc_df.columns)
        matrix = []
        for stat in stat_names:
            row = []
            for col in col_names:
                val = desc_df.loc[stat, col]
                if pd.isna(val):
                    row.append(None)
                elif isinstance(val, (int, float)):
                    row.append(str(round(val, 4)))
                else:
                    row.append(str(val))
            matrix.append(row)
        self._describe_stats_table.set_data(stat_names, col_names, matrix)

    # ------------------------------------------------------------------
    # 交互：箱线图
    # ------------------------------------------------------------------

    def _on_draw_boxplot(self) -> None:
        """对数值列绘制箱线图并嵌入展示区。

        修复（Q3）：优先使用「确认统计」时清理后的数据，与空值统计/
        描述统计保持同一数据口径；未执行过统计则回退原始数据。
        """
        source = self._clean_df if self._clean_df is not None else self._df
        if source is None:
            return

        cols = numeric_columns(source)
        if not cols:
            self._show_status("未找到数值列，无法绘制箱线图")
            return

        # 修复：原版未捕获异常，make_boxplot 出错（如 matplotlib 参数
        # 不兼容、数据列全为空）时异常会直接抛出导致应用崩溃
        try:
            fig = make_boxplot(source, cols)
        except Exception as exc:
            self._show_status(f"箱线图绘制失败：{exc}")
            return
        canvas = FigureCanvasQTAgg(fig)
        # 修复：与 plot_page.py 散点/折线图画布一致，显式设置尺寸策略，
        # 否则 canvas 按 make_boxplot 的 figsize 固定显示，不随容器拉伸
        canvas.setMinimumHeight(400)
        canvas.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))

        # 移除旧的 canvas
        self._replace_boxplot_canvas(canvas)
        # 窄条占位切换：箱线图区展开
        self._set_placeholder_visible(self._boxplot_ph, self._boxplot_container,
                                      self._boxplot_subtitle, content=True)

    def _replace_boxplot_canvas(self, new_canvas: FigureCanvasQTAgg) -> None:
        """替换箱线图展示区中的 canvas：先释放旧 Figure，再整体替换（单 canvas 复用）。

        每次绘制仅保留一个 canvas；旧 canvas 的 Figure 先 clear() 释放
        matplotlib 内部聚合/渲染缓存，再 deleteLater 销毁，避免反复绘制累积内存。
        """
        # 清空布局并释放旧 Figure 资源
        while self._boxplot_layout.count():
            item = self._boxplot_layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            if isinstance(widget, FigureCanvasQTAgg):
                fig = widget.figure
                if fig is not None:
                    fig.clear()      # 释放旧 Figure 的全部 axes/artists
            widget.deleteLater()

        # stretch=1：canvas 随容器垂直拉伸（与 plot_page.py 画布入布局一致）
        self._boxplot_layout.addWidget(new_canvas, 1)

    # ------------------------------------------------------------------
    # 交互：导出 Excel
    # ------------------------------------------------------------------

    def _on_export(self) -> None:
        """弹出保存对话框，导出描述性统计表到 Excel。"""
        if not hasattr(self, '_desc_df') or self._desc_df is None:
            self._show_status("请先确认统计再导出")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "导出描述性统计", "descriptive_statistics.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if path:
            try:
                # 修复（Q2）：改走 seedata_core.export_stats 统一导出，
                # 内含 Excel 公式注入防护；原版绕过 core 接口直接 to_excel
                # （export_stats 被 import 却从未使用），且无任何防护。
                export_stats(self._desc_df, path, index=True)
                QMessageBox.information(self, "提示", f"导出成功：{path}")
            except Exception as exc:
                self._show_status(f"导出失败：{exc}")

    # ------------------------------------------------------------------
    # 工具：状态提示
    # ------------------------------------------------------------------

    def _show_status(self, message: str) -> None:
        """弹窗警告提示用户。"""
        QMessageBox.warning(self, "提示", message)


# =============================================================================
# 对外接口
# =============================================================================

def build_data_pivot_page() -> QWidget:
    """返回「数据透视」功能页面，供主窗口 QStackedWidget 接入。"""
    return DataPivotPage()


# =============================================================================
# 独立预览（__main__）
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)

    apply_style(app)

    window = QMainWindow()
    window.setWindowTitle("数据透视 - 独立预览")
    window.resize(1100, 720)

    central = QWidget()
    window.setCentralWidget(central)
    layout = QHBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 左侧：模拟菜单栏（仅用于预览）
    from style import build_sidebar
    sidebar = build_sidebar()
    layout.addWidget(sidebar)

    # 右侧：标题区 + 数据透视页面
    right_widget = QWidget()
    right_layout = QVBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)
    right_layout.addWidget(build_header("数据透视", "木绘图 › 数据透视"))
    right_layout.addWidget(build_data_pivot_page())
    layout.addWidget(right_widget)

    window.show()
    sys.exit(app.exec())
