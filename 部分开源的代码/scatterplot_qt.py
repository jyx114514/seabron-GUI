"""
scatterplot_qt — 散点图入口（薄壳）。
绘图逻辑已规格驱动化：build_scatter_page() 返回通用 PlotPage(SPECS["scatter"])。
历史实现 ScatterPage 已整体迁移至 plot_page.py（通用绘图页）。
"""
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout

from plot_page import PlotPage
from plot_spec import SPECS


def build_scatter_page():
    """构造散点图页。数据完全独立：本页自己拖文件、自己读。"""
    return PlotPage(SPECS["scatter"])


if __name__ == "__main__":
    from style import (
        apply_style, build_sidebar, build_header, WINDOW_WIDTH, WINDOW_HEIGHT,
    )

    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    app.setFont(font)
    apply_style(app)

    win = QMainWindow()
    win.setWindowTitle("散点图 - scatterplot_qt 独立预览")
    win.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
    central = QWidget()
    win.setCentralWidget(central)
    ml = QHBoxLayout(central)
    ml.setContentsMargins(0, 0, 0, 0)
    ml.setSpacing(0)
    sidebar = build_sidebar()
    ml.addWidget(sidebar)
    right = QWidget()
    rl = QVBoxLayout(right)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(0)
    rl.addWidget(build_header("散点图", "木绘图 › 绘图 › 散点图"))
    rl.addWidget(build_scatter_page())
    ml.addWidget(right)
    win.show()
    sys.exit(app.exec())
