"""
plot_widgets — 「木绘图」通用控件层（PySide6）。

从 scatterplot_qt.py 抽出的与具体图形无关的通用小部件与视觉工厂，
供所有图形页面（散点图 / 折线图 / 箱线图 / 直方图 …）复用，避免复制页面文件导致两份漂移实现：
- 视觉常量：FS / FS_GRP / FS_HEAD / FS_BTN / CARD_BG
- QSS 工厂：btn_primary_qss / btn_secondary_qss / btn_tertiary_qss /
  line_edit_qss / group_title_qss / card_shadow
- 通用控件：FlowWidget / ChipLabel / DropZoneBase（拖放区共享基类）/
  FileDropZone（通用文件拖放区，四种图形页共用）/ SlotWidget / SwatchWidget / SegButton

本模块所有色值均从 style.py 导入，不重新定义任何颜色。
SWATCH_COLORS / PALETTE_NAMES 已随 spec 迁移至 plot_spec.py（Step 4），此处不再定义。
文件末尾保留下划线别名，兼容搬运前的内部引用与导入路径。
"""

from PySide6.QtCore import Qt, Signal, QMimeData, QTimer
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QFrame,
    QFileDialog, QGraphicsDropShadowEffect,
)

# —— 复用 style.py 的样式令牌（颜色 / 圆角 / 按钮 / Chip / 拖放区）——
from style import (
    CARD, INK, INK_SOFT, LINE, ACCENT, BEIGE, BEIGE_SOFT,
    WOOD_BROWN, WOOD_BROWN_DARK, BTN_RADIUS, BTN_PADDING,
    BTN_FONT_SIZE, CHIP_RADIUS, DROP_ZONE_BORDER,
)

# —— 字号：正文较 HTML（11.5px）略放大以提升桌面端可读性；按钮复用 style.py 的 BTN_FONT_SIZE ——
FS = "13px"                 # 正文 / 标签
FS_GRP = "14px"             # 分组标题（①~⑤）
FS_HEAD = "18px"            # 配置区大标题（如「散点图配置」）
FS_BTN = BTN_FONT_SIZE      # 按钮（HTML .btn = 12px，复用 style.py）

# 所有非输入类部件统一使用卡片底色，保持视觉一致
CARD_BG = f"background:{CARD};"


def btn_primary_qss():
    return (f"QPushButton{{background:{WOOD_BROWN};color:#FFF;border:none;"
            f"border-radius:{BTN_RADIUS};padding:{BTN_PADDING};font-size:{FS_BTN};font-weight:600;}}"
            f"QPushButton:hover{{background:{WOOD_BROWN_DARK};}}")


def btn_secondary_qss():
    return (f"QPushButton{{{CARD_BG}border:1px solid {WOOD_BROWN};"
            f"border-radius:{BTN_RADIUS};padding:{BTN_PADDING};font-size:{FS_BTN};"
            f"color:{WOOD_BROWN};font-weight:600;}}"
            f"QPushButton:hover{{background:{BEIGE_SOFT};}}")


def btn_tertiary_qss():
    return (f"QPushButton{{{CARD_BG}border:1px solid {LINE};"
            f"border-radius:{BTN_RADIUS};padding:{BTN_PADDING};font-size:{FS_BTN};"
            f"color:{INK_SOFT};font-weight:600;}}"
            f"QPushButton:hover{{border-color:{INK_SOFT};}}")


def line_edit_qss():
    return (f"QLineEdit{{border:1px solid {LINE};border-radius:6px;padding:3px 8px;"
            f"font-size:{FS};background:#FFF;color:{INK};}}"
            f"QLineEdit:focus{{border-color:{WOOD_BROWN};}}")


def group_title_qss():
    return f"QLabel{{color:{WOOD_BROWN};font-size:{FS_GRP};font-weight:600;background:transparent;}}"


# ── 通用小部件 ──────────────────────────────────────────────────────────────

def card_shadow(widget, blur=12, offset=2, alpha=26):
    """给卡片添加柔和外投影，模拟 HTML box-shadow。"""
    if widget.graphicsEffect() is not None:
        return
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, offset)
    shadow.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(shadow)


class FlowWidget(QWidget):
    """极简流式布局容器：字段 chips 自动换行。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[QWidget] = []
        # 类选择器 FlowWidget 只匹配自身，不级联到后代 chips（防 QSS 级联坑）
        self.setStyleSheet("FlowWidget{background:transparent;}")

    def addWidget(self, w: QWidget) -> None:
        w.setParent(self)
        w.show()
        self._items.append(w)
        self._relayout()

    def clear_all(self) -> None:
        for w in list(self._items):
            w.setParent(None)
            w.deleteLater()
        self._items.clear()

    def _relayout(self) -> None:
        pw = self.width()
        if pw <= 0:
            QTimer.singleShot(0, self._relayout)  # 尚未布局完成，延后执行
            return
        gap = 6
        x, y, row_h = 4, 0, 0
        for w in self._items:
            ww = w.width()
            if x > 4 and x + ww > pw - 4:
                x = 4
                y += row_h + gap
                row_h = 0
            w.move(x, y)
            x += ww + gap
            row_h = max(row_h, w.height())
        self.setMinimumHeight(y + row_h + 4)
        self.update()

    def resizeEvent(self, event):
        self._relayout()
        super().resizeEvent(event)

    def showEvent(self, event):
        self._relayout()
        super().showEvent(event)


MIME_COLUMN = "application/x-column"


class ChipLabel(QLabel):
    """可拖拽字段标签（自定义 MIME，避免与其他文本拖拽冲突）。"""

    def __init__(self, col: str, parent=None):
        super().__init__(col, parent)
        self.col = col
        # CJK 字符约 2 倍拉丁字符宽，按内容估算芯片宽度
        cjk = sum(1 for ch in col if '\u4e00' <= ch <= '\u9fff')
        latin = len(col) - cjk
        w = max(54, latin * 8 + cjk * 16 + 28)
        self.setFixedSize(w, 28)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setStyleSheet(
            f"QLabel{{{CARD_BG}border:1px solid {LINE};"
            f"border-radius:{CHIP_RADIUS};color:{INK};font-size:{FS};"
            f"padding:0 10px;}}"
        )

    def mousePressEvent(self, event):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_COLUMN, self.col.encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class DropZoneBase(QWidget):
    """拖放区共享基类：文件拖入 / 点击选择的统一行为（单份实现，防漂移）。

    plot_widgets.FileDropZone 与 seedata_qt.DropZone 共用本基类：
    扩展名校验、default/valid/invalid 状态机、拖放事件、点击选文件、
    路径信号发射只在此实现一份；子类仅定制外观（边框画法、文案、高度），
    并按需覆盖 _apply_state / _show_path 钩子。
    """

    FILE_EXTENSIONS = (".csv", ".xls", ".xlsx")  # 受支持扩展名（统一小写判定）

    fileDropped = Signal(str)  # 拖入/选择文件后发射路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "default"
        self.setAcceptDrops(True)

    # ---- 外观钩子（子类覆盖） ----
    def _apply_state(self):
        """状态变化时刷新外观（default/valid/invalid）；子类实现边框与底色。"""

    def _show_path(self, path: str):
        """拖入/选择成功后展示路径（可选）；默认不展示。"""

    # ---- 共用行为 ----
    def _accept_urls(self, event) -> bool:
        """拖入的 URL 中是否存在受支持的文件（大小写不敏感）。"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(self.FILE_EXTENSIONS):
                    return True
        return False

    def _choose_file(self):
        """点击选择文件（QFileDialog）；命中后发射路径。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", "", "CSV/Excel (*.csv *.xls *.xlsx)"
        )
        if path:
            self._show_path(path)
            self.fileDropped.emit(path)

    def dragEnterEvent(self, event):
        if self._accept_urls(event):
            event.acceptProposedAction()
            self._state = "valid"
        else:
            event.ignore()
            self._state = "invalid"
        self._apply_state()

    def dragLeaveEvent(self, event):
        self._state = "default"
        self._apply_state()

    def dropEvent(self, event):
        self._state = "default"
        self._apply_state()
        if self._accept_urls(event):
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path.lower().endswith(self.FILE_EXTENSIONS):
                    self._show_path(path)
                    self.fileDropped.emit(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def mousePressEvent(self, event):
        self._choose_file()


class FileDropZone(DropZoneBase):
    """数据来源拖放区：支持文件拖入与点击选择，用 QPainter 绘制虚线边框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(56)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # 类选择器 FileDropZone 只匹配自身；裸 QWidget{} 会级联给 _t1/_t2 文字标签上背景
        self.setStyleSheet(f"FileDropZone{{background:{BEIGE_SOFT};border-radius:10px;}}")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(2)
        self._t1 = QLabel("拖入 CSV / Excel，或从「数据透视」载入")
        self._t2 = QLabel("（也可点击此处选择文件）")
        lay.addWidget(self._t1)
        lay.addWidget(self._t2)

    def paintEvent(self, event):
        """QPainter 绘制虚线边框，避免部分 Qt 样式把 dashed 降级为 solid。"""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = {"default": DROP_ZONE_BORDER, "valid": "#4CAF50", "invalid": "#F44336"}[self._state]
        pen = QPen(QColor(color))
        pen.setWidth(2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 10, 10)

    def _apply_state(self):  # "default" / "valid" / "invalid"
        bg = {"default": BEIGE_SOFT, "valid": "#E6F4EA", "invalid": "#FDECEA"}[self._state]
        self.setStyleSheet(f"FileDropZone{{background:{bg};border-radius:10px;}}")
        self.update()  # 触发 paintEvent 重画边框

    def _show_path(self, path: str):
        self._t1.setText(path)  # 文字改为文件路径


class SlotWidget(QFrame):
    """字段槽位：可接收拖入的列名，点击已填充槽位可清空。

    dashed_empty=True（默认）时空态画虚线边框（散点图等常规槽位）；
    设为 False 时空态为透明+无边框（外层已有大虚线框的追加 Y 轴槽位）。
    填充态（已选列名）始终保留 accent 实线边框+米色底，便于区分已选/未选。
    """

    field_changed = Signal(str, object)

    def __init__(self, key, placeholder, parent=None, dashed_empty=True):
        super().__init__(parent)
        self._key = key
        self._val = None
        self._dashed_empty = dashed_empty
        self.setAcceptDrops(True)
        self.setMinimumHeight(28)
        self._lbl = QLabel(placeholder, self)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._upd()

    def _upd(self):
        if self._val:
            self._lbl.setText(f"{self._val}  ✕")
            self._lbl.setStyleSheet(
                f"QLabel{{color:{INK};font-size:{FS};background:transparent;border:none;padding:0 6px;}}")
            self.setStyleSheet(
                f"SlotWidget{{background:{BEIGE};border:1px solid {ACCENT};border-radius:6px;}}")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self._lbl.setText(f"拖入字段 ({self._key})")
            self._lbl.setStyleSheet(
                f"QLabel{{color:{INK_SOFT};font-size:{FS};background:transparent;border:none;padding:0 6px;}}")
            if self._dashed_empty:
                # 默认：虚线边框 + 白底（与既有行为一致，不影响散点图等）
                self.setStyleSheet(
                    f"SlotWidget{{background:#FFF;border:1px dashed {LINE};border-radius:6px;}}")
            else:
                # dashed_empty=False：空态无边框+透明，用于外层已是大虚线框的场景
                self.setStyleSheet(
                    "SlotWidget{background:transparent;border:none;}")
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_val(self, v):
        self._val = v
        self._upd()
        self.field_changed.emit(self._key, v)

    def get_val(self):
        return self._val

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_COLUMN):
            event.acceptProposedAction()
            if self._dashed_empty:
                self.setStyleSheet(
                    f"SlotWidget{{background:{BEIGE_SOFT};border:2px solid {WOOD_BROWN};border-radius:6px;}}")
            else:
                # dashed_empty=False：拖入高亮也走无边框模式，用米色底色提示
                self.setStyleSheet(
                    f"SlotWidget{{background:{BEIGE_SOFT};border:2px solid {WOOD_BROWN};border-radius:6px;}}")
        else:
            event.ignore()

    def dragLeaveEvent(self, _):
        self._upd()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_COLUMN):
            col = bytes(event.mimeData().data(MIME_COLUMN)).decode("utf-8")
            if col:
                self.set_val(col)
                event.acceptProposedAction()

    def mousePressEvent(self, e):
        if self._val and e.button() == Qt.MouseButton.LeftButton:
            self.set_val(None)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._lbl.setGeometry(6, 0, self.width() - 12, self.height())


class SwatchWidget(QFrame):
    """色板小块：点击切换 palette，「默认」为文字块、其余为纯色块。"""

    clicked = Signal(str)

    def __init__(self, name, color, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color
        self._sel = False
        self.setFixedSize(40, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._lbl = None
        if name == "默认":
            self._lbl = QLabel("默认", self)
            self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._upd()

    def _upd(self):
        if self._name == "默认":
            bd = f"2px solid {WOOD_BROWN}" if self._sel else f"1px solid {LINE}"
            tc = WOOD_BROWN if self._sel else INK_SOFT
            self.setStyleSheet(
                f"SwatchWidget{{background:{BEIGE};border:{bd};border-radius:5px;}}")
            if self._lbl:
                self._lbl.setStyleSheet(f"color:{tc};font-size:11px;background:transparent;")
        else:
            bd = f"2px solid {WOOD_BROWN}" if self._sel else "2px solid transparent"
            self.setStyleSheet(
                f"SwatchWidget{{background:{self._color};border-radius:5px;border:{bd};}}")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._lbl:
            self._lbl.setGeometry(0, 0, self.width(), self.height())

    def set_sel(self, s):
        self._sel = s
        self._upd()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._name)


class SegButton(QPushButton):
    """分段单选按钮：用于图例（auto/brief/full/无）与主题（木系/默认/whitegrid…）等互斥选项。"""

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._on = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(26)
        self._upd()

    def _upd(self):
        if self._on:
            self.setStyleSheet(
                f"QPushButton{{background:{WOOD_BROWN};color:#FFF;border:none;"
                f"border-radius:5px;padding:3px 10px;font-size:12px;font-weight:600;}}")
        else:
            self.setStyleSheet(
                f"QPushButton{{background:{BEIGE};color:{INK};border:none;"
                f"border-radius:5px;padding:3px 10px;font-size:12px;}}")

    def set_on(self, o):
        self._on = o
        self._upd()


# ── 兼容别名：保留下划线名（内部历史引用 / 兼容导入路径） ──────────────────
_FS = FS
_FS_GRP = FS_GRP
_FS_HEAD = FS_HEAD
_FS_BTN = FS_BTN
_CARD_BG = CARD_BG
_prim = btn_primary_qss
_sec = btn_secondary_qss
_tert = btn_tertiary_qss
_inp = line_edit_qss
_grp_ttl = group_title_qss
_card_shadow = card_shadow
