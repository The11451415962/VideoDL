#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器 —— Windows 11 Fluent Design（PySide6）版本
====================================================
基于 yt-dlp + PySide6，界面按 Windows 11 设计语言实现：
  · 页面背景用系统磨砂（Mica / Acrylic），卡片是不透明的 Layer 面，
    磨砂只在留白处透出来 —— 保证文字对比度，不会糊成一片灰
  · 统一 8pt 间距栅格、8px 卡片圆角、36px 控件高度
  · 强调色只用于主按钮 / 焦点 / 进度条
  · 下拉框显示中文标签，落盘仍是 config.json 的原始值
  · 内容放在滚动容器里：窗口拉小改为滚动，不会把卡片压扁裁切
  · 日志区是主视觉之一，最小高度受保护，不再被挤成一条缝

运行：
  pip install PySide6
  python video_downloader_qt.py

后端复用 video_downloader.py 中的 yt-dlp 下载/配置/诊断逻辑。
"""

import ctypes
import os
import re
import subprocess
import sys
import tempfile
import threading
from datetime import datetime


# ============================================================
# PySide6 引导：缺失时自动安装，失败给出清晰弹窗提示
# （避免双击 .py 时因缺少依赖而"一闪而过"没有任何提示）
# ============================================================
def _msgbox(title: str, text: str, error: bool = False) -> None:
    """弹窗提示（无控制台时也能看到）。"""
    try:
        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        print(f"{title}: {text}")


def _bootstrap_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
        return
    except ImportError:
        pass

    print("首次运行：正在自动安装 PySide6（约 200MB），请耐心等待...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
    except Exception as e:
        _msgbox("依赖缺失",
                f"自动安装 PySide6 失败：\n{e}\n\n"
                "请打开命令行手动执行：\n    pip install PySide6\n\n"
                "然后重新运行本程序。", error=True)
        raise SystemExit(1)

    try:
        import PySide6  # noqa: F401
    except Exception:
        _msgbox("依赖缺失",
                "PySide6 安装完成但导入失败，请重启本程序后再试。", error=True)
        raise SystemExit(1)


_bootstrap_pyside6()

from PySide6.QtCore import Qt, QObject, QPointF, QRectF, QSize, Signal, QUrl
from PySide6.QtGui import (QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF,
                           QPalette, QTextCursor, QTextCharFormat)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QLineEdit,
                               QPushButton, QComboBox, QProgressBar, QTextEdit,
                               QFrame, QFileDialog, QMessageBox,
                               QGraphicsDropShadowEffect, QScrollArea)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

import video_downloader as core  # 复用 yt-dlp 后端逻辑


# ============================================================
# 设计令牌（Windows 11 Fluent：Mica 页面 + 不透明 Layer 卡片）
# ------------------------------------------------------------
# 关键点：只有"页面背景"透出 Mica，所有卡片/输入框都是不透明面，
#         这样文字才有足够对比度，不会变成一层灰糊糊的半透明叠加。
# ============================================================
ACCENT = "#2D7DFF"          # 强调色（主按钮 / 焦点 / 进度条）
ACCENT_HOVER = "#1E6BEF"
ACCENT_PRESSED = "#155AD6"

TEXT_MAIN = "#1B1F24"       # 标题
TEXT_BODY = "#3C4753"       # 正文
TEXT_MUTED = "#6B7684"      # 次要文字 / 字段标签
TEXT_FAINT = "#9AA4B2"      # 占位符 / 禁用

SURFACE = "#FFFFFF"         # 卡片面（Layer）
SURFACE_ALT = "#F4F6FA"     # 输入框 / 次级面板
SURFACE_HOVER = "#EBF0F7"
BORDER = "#E3E7ED"
BORDER_STRONG = "#CFD6E0"
PAGE_FALLBACK = "#EEF2F8"   # 磨砂不可用时的页面底色

LOG_BG = "#F7F9FC"          # 日志面板底
LOG_TEXT = "#3C4753"

# 日志级别 → 颜色
LOG_COLORS = {"info": "#5A6675", "ok": "#12794A",
              "err": "#C0362C", "warn": "#9A6200"}

# 下拉框选项：显示中文标签，内部仍存 config.json 里的原始值
FORMAT_ITEMS = [("MP4", "mp4"), ("WebM", "webm"), ("MP3（仅音频）", "mp3")]
QUALITY_ITEMS = [("最佳画质", "best"), ("1080P", "1080p"),
                 ("720P", "720p"), ("仅音频", "audio")]
PROXY_ITEMS = [("自动", "auto"), ("直连", "direct"), ("强制代理", "proxy")]

# yt-dlp 输出中解析下载速度 / ETA
SPEED_RE = re.compile(r"at\s+([0-9.]+[KMG]?i?B/s)")
ETA_RE = re.compile(r"ETA\s+([0-9:]+)")


# ============================================================
# 磨砂玻璃系统 API（Mica / Acrylic）
# ============================================================
def _enable_mica(hwnd) -> bool:
    """Windows 11 22621+：通过 DwmSetWindowAttribute 开启 Mica 背景。

    属性 DWMWA_SYSTEMBACKDROP_TYPE = 38；
      值 2 = DWMSBT_MAINWINDOW（Mica），值 3 = DWMSBT_TRANSIENTWINDOW（Acrylic）。
    """
    try:
        value = ctypes.c_int(2)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 38, ctypes.byref(value), ctypes.sizeof(value))
        return res == 0
    except Exception:
        return False


def _enable_acrylic(hwnd, tint=0x55FFFFFF) -> bool:
    """Win10 1803+：通过 SetWindowCompositionAttribute 开启 Acrylic 模糊。

    GradientColor 格式为 AABBGGRR（8 位 alpha + 蓝绿红）。
    此处用低 alpha 的白色，让壁纸透过模糊层显出浅色磨砂效果（对应参考图）。
    """
    try:
        class ACCENT_POLICY(ctypes.Structure):
            _fields_ = [("AccentState", ctypes.c_int),
                        ("AccentFlags", ctypes.c_int),
                        ("GradientColor", ctypes.c_uint),
                        ("AnimationId", ctypes.c_int)]

        class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
            _fields_ = [("Attrib", ctypes.c_int),
                        ("pvData", ctypes.c_void_p),
                        ("cbData", ctypes.c_size_t)]

        accent = ACCENT_POLICY()
        accent.AccentState = 4            # ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.GradientColor = tint
        data = WINDOWCOMPOSITIONATTRIBDATA()
        data.Attrib = 19                  # WCA_ACCENT_POLICY
        data.pvData = ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p)
        data.cbData = ctypes.sizeof(accent)
        res = ctypes.windll.user32.SetWindowCompositionAttribute(
            hwnd, ctypes.byref(data))
        return bool(res)
    except Exception:
        return False


def enable_frosted(window) -> bool:
    """尽力为窗口开启 Mica / Acrylic 磨砂背景；返回是否成功。

    优先 Win11 Mica，失败则回退 Acrylic。成功后让窗口内容透明，
    使系统磨砂背景透过半透明卡片呈现出来。
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        hwnd = int(window.winId())
    except Exception:
        return False
    ok = _enable_mica(hwnd) or _enable_acrylic(hwnd)
    if ok:
        window.setAttribute(Qt.WA_TranslucentBackground, True)
    return ok


# ============================================================
# 图标生成（避免依赖外部图片资源）
# ============================================================
def _make_down_arrow() -> str:
    """生成下拉箭头 PNG，返回文件路径（QSS image 引用）。"""
    pm = QPixmap(24, 24)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(TEXT_MUTED), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawLine(QPointF(8.5, 10.5), QPointF(12, 14))
    p.drawLine(QPointF(12, 14), QPointF(15.5, 10.5))
    p.end()
    path = os.path.join(tempfile.gettempdir(), "videodl_down_arrow.png")
    pm.save(path, "PNG")
    return path.replace("\\", "/")


def _make_link_icon() -> QIcon:
    """生成链接图标（输入框左侧 Leading 图标）：两个斜置链环，描边风格。"""
    pm = QPixmap(20, 20)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(TEXT_MUTED), 1.7)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.translate(10, 10)
    p.rotate(-45)
    p.drawRoundedRect(QRectF(-7.2, -3.0, 8.6, 6.0), 3.0, 3.0)
    p.drawRoundedRect(QRectF(-1.4, -3.0, 8.6, 6.0), 3.0, 3.0)
    p.end()
    return QIcon(pm)


def _make_thumb_placeholder(w: int, h: int) -> QPixmap:
    """生成封面占位图（透明的圆角播放标记 + 中文说明），替代英文占位文本。"""
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    cx, cy = w / 2.0, h / 2.0 - 8
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(138, 148, 162, 38))
    p.drawEllipse(QPointF(cx, cy), 19, 19)
    p.setBrush(QColor(TEXT_FAINT))
    p.drawPolygon(QPolygonF([QPointF(cx - 4.5, cy - 8),
                             QPointF(cx - 4.5, cy + 8),
                             QPointF(cx + 9.0, cy)]))
    f = p.font()
    f.setPointSize(9)
    p.setFont(f)
    p.setPen(QPen(QColor(TEXT_FAINT)))
    p.drawText(QRectF(0, cy + 26, w, 20), Qt.AlignHCenter | Qt.AlignTop, "等待视频信息")
    p.end()
    return pm


def _make_app_icon() -> QIcon:
    """生成应用图标（蓝色圆角块 + 白色下载箭头），用于标题栏。"""
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    p.drawRoundedRect(0, 0, 64, 64, 14, 14)
    # 白色下箭头（下载）
    pen = QPen(QColor("#ffffff"), 7)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.drawLine(32, 14, 32, 40)
    p.drawLine(20, 28, 32, 40)
    p.drawLine(44, 28, 32, 40)
    # 底部横线
    p.drawLine(20, 50, 44, 50)
    p.end()
    return QIcon(pm)


# ============================================================
# 卡片 / 按钮工厂
# ============================================================
def _add_card_shadow(widget: QWidget, blur: int = 16, alpha: int = 22) -> None:
    """给卡片压一层极淡的投影，形成 Fluent 的 Layer 层次感。"""
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, 2)
    eff.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(eff)


def _make_card() -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    _add_card_shadow(card)
    return card


def _make_button(text: str, obj: str = "secondary", height: int = 36,
                 width: int = 0, on_click=None) -> QPushButton:
    """统一高度/手型的按钮工厂，保证一行里的按钮永远对齐。"""
    btn = QPushButton(text)
    btn.setObjectName(obj)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


# ============================================================
# 日志视图：压小默认 sizeHint
# ------------------------------------------------------------
# QTextEdit 默认 sizeHint 高 192px，放进滚动容器会把内容顶高、
# 导致常规窗口尺寸下就常驻一根滚动条；这里压到 96px。
# ============================================================
class _LogView(QTextEdit):
    def sizeHint(self) -> QSize:  # noqa: N802 (Qt 命名)
        s = super().sizeHint()
        return QSize(s.width(), 96)


# ============================================================
# 下载线程 → Qt 信号桥（跨线程安全）
# ============================================================
class DownloadSignals(QObject):
    info = Signal(dict)
    progress = Signal(float)
    done = Signal(bool, str)
    log = Signal(str)
    error = Signal(dict)
    core_update = Signal(str)   # "更新核心" 在工作线程跑，结果必须回主线程更新界面


# ============================================================
# 主窗口
# ============================================================
class VideoDownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频下载器")
        self.setWindowIcon(_make_app_icon())
        self.setMinimumSize(820, 640)
        self._apply_initial_geometry()

        self.config = core.load_config()
        core.ensure_dir(self.config["save_dir"])

        self.sig = DownloadSignals(self)
        self.sig.info.connect(self._on_info)
        self.sig.progress.connect(self._on_progress)
        self.sig.done.connect(self._on_done)
        self.sig.log.connect(self._append_log)
        self.sig.error.connect(self._on_error)
        self.sig.core_update.connect(self._on_update_done)

        self._dl = None
        self._thread = None
        self._nam = QNetworkAccessManager(self)

        # 磨砂背景（失败时回退为浅色不透明底，保证不透明黑块）
        if not enable_frosted(self):
            pal = self.palette()
            pal.setColor(QPalette.Window, QColor(PAGE_FALLBACK))
            self.setPalette(pal)

        self._build_ui()
        self._apply_stylesheet()

        # 启动后检查依赖
        self._startup_check()

    def _apply_initial_geometry(self):
        """初始尺寸按屏幕可用区域自适应：1366x768 上也不顶到任务栏、不压扁日志区。"""
        w, h = 900, 760
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            w = max(820, min(w, avail.width() - 80))
            h = max(640, min(h, avail.height() - 70))
            self.resize(w, h)
            self.move(avail.center().x() - w // 2,
                      max(avail.top() + 16, avail.center().y() - h // 2))
        else:
            self.resize(w, h)

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_link_card())
        outer.addWidget(self._build_config_card())
        outer.addWidget(self._build_preview_card())
        outer.addLayout(self._build_buttons())
        outer.addWidget(self._build_log_card(), 1)

        # 放进滚动容器：窗口被拉小/屏幕矮时改为滚动，而不是把卡片压扁裁切
        area = QScrollArea()
        area.setObjectName("scrollArea")
        area.setFrameShape(QFrame.NoFrame)
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.viewport().setObjectName("pageViewport")
        area.setWidget(root)
        self.setCentralWidget(area)

    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        box = QVBoxLayout()
        box.setSpacing(1)
        title = QLabel("视频下载器")
        title.setObjectName("appTitle")
        sub = QLabel("yt-dlp 驱动 · 支持 YouTube / B站 / 抖音 等站点")
        sub.setObjectName("appSubtitle")
        box.addWidget(title)
        box.addWidget(sub)
        row.addLayout(box)
        row.addStretch(1)

        # 低频操作收到标题行右上角，把主视觉让给下载按钮
        self.btn_update = _make_button("更新核心", "ghost", 32, on_click=self._update_core)
        self.btn_settings = _make_button("设置", "ghost", 32, on_click=self._open_settings)
        row.addWidget(self.btn_update, 0, Qt.AlignBottom)
        row.addWidget(self.btn_settings, 0, Qt.AlignBottom)
        return row

    def _build_link_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlEdit")
        self.url_edit.setPlaceholderText("粘贴视频链接，例如 https://www.bilibili.com/video/BV...")
        self.url_edit.setFixedHeight(36)
        self.url_edit.addAction(_make_link_icon(), QLineEdit.LeadingPosition)
        self.url_edit.returnPressed.connect(self._start_download)
        row.addWidget(self.url_edit, 1)

        self.btn_paste = _make_button("一键粘贴", "secondary", 36, 92,
                                      self._paste_from_clipboard)
        row.addWidget(self.btn_paste)

        lay.addLayout(row)
        return card

    def _build_config_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        # 保存路径
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit(self.config["save_dir"])
        self.path_edit.setObjectName("pathEdit")
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(36)
        self.path_edit.setToolTip(self.config["save_dir"])
        path_row.addWidget(self.path_edit, 1)

        self.btn_change_path = _make_button("更改路径", "secondary", 36, 92,
                                            self._change_save_dir)
        path_row.addWidget(self.btn_change_path)
        lay.addWidget(self._make_field_row("保存路径", path_row))

        # 格式 / 清晰度 / 网络代理（三等分）
        self.cb_format = self._make_combo(FORMAT_ITEMS,
                                         self.config.get("default_format", "mp4"))
        self.cb_quality = self._make_combo(QUALITY_ITEMS,
                                           self.config.get("default_quality", "best"))
        self.cb_proxy = self._make_combo(PROXY_ITEMS,
                                         self.config.get("proxy_mode", "auto"))

        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        grid.addWidget(self._make_field("格式", self.cb_format), 0, 0)
        grid.addWidget(self._make_field("清晰度", self.cb_quality), 0, 1)
        grid.addWidget(self._make_field("网络代理", self.cb_proxy), 0, 2)
        lay.addLayout(grid)

        # 选择变化即时持久化
        self.cb_format.currentIndexChanged.connect(self._sync_ui_to_config)
        self.cb_quality.currentIndexChanged.connect(self._sync_ui_to_config)
        self.cb_proxy.currentIndexChanged.connect(self._sync_ui_to_config)
        return card

    @staticmethod
    def _make_combo(items, current):
        """items = [(显示标签, 原始值)]；显示中文，内部仍存 config.json 的原始值。"""
        cb = QComboBox()
        cb.setObjectName("combo")
        for label, value in items:
            cb.addItem(label, value)
        idx = cb.findData(current)
        cb.setCurrentIndex(idx if idx >= 0 else 0)
        cb.setFixedHeight(36)
        cb.setCursor(Qt.PointingHandCursor)
        return cb

    @staticmethod
    def _make_field(label, widget):
        box = QVBoxLayout()
        box.setSpacing(4)
        box.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        box.addWidget(lbl)
        box.addWidget(widget)
        wrap = QWidget()
        wrap.setObjectName("fieldWrap")
        wrap.setLayout(box)
        return wrap

    @classmethod
    def _make_field_row(cls, label, row_layout):
        """字段标签 + 一整行（输入框 + 按钮）的组合。"""
        holder = QWidget()
        holder.setObjectName("fieldWrap")
        holder.setLayout(row_layout)
        return cls._make_field(label, holder)

    def _build_preview_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(14)

        # 缩略图（16:9，圆角；无信息时显示占位图而不是英文占位文本）
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setFixedSize(208, 117)
        self.thumb.setPixmap(_make_thumb_placeholder(206, 115))
        top.addWidget(self.thumb)

        # 右侧信息：标题 / 时长 / 大小 / 附加信息
        info = QVBoxLayout()
        info.setSpacing(4)
        info.setContentsMargins(0, 2, 0, 2)
        self.info_title = QLabel("等待粘贴链接…")
        self.info_title.setObjectName("infoTitle")
        self.info_title.setWordWrap(True)
        info.addWidget(self.info_title)

        self.info_meta = QLabel("时长：—")
        self.info_meta.setObjectName("infoMeta")
        info.addWidget(self.info_meta)

        self.info_size = QLabel("预计大小：—")
        self.info_size.setObjectName("infoMeta")
        info.addWidget(self.info_size)

        self.info_extra = QLabel("")
        self.info_extra.setObjectName("infoMeta")
        self.info_extra.setWordWrap(True)
        info.addWidget(self.info_extra)
        info.addStretch(1)
        top.addLayout(info, 1)
        lay.addLayout(top)

        # 进度条 + 右侧百分比（固定宽度，避免数字变化时左右抖动）
        prog_row = QHBoxLayout()
        prog_row.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        prog_row.addWidget(self.progress, 1)
        self.percent_label = QLabel("0.0%")
        self.percent_label.setObjectName("percentText")
        self.percent_label.setFixedWidth(54)
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog_row.addWidget(self.percent_label)
        lay.addLayout(prog_row)

        # 状态行
        self.status_label = QLabel("就绪 · 等待链接")
        self.status_label.setObjectName("statusText")
        lay.addWidget(self.status_label)
        return card

    def _build_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_download = _make_button("开始下载", "primary", 36, 112,
                                         self._start_download)
        row.addWidget(self.btn_download)

        self.btn_stop = _make_button("停止下载", "secondary", 36, 96,
                                     self._stop_download)
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_stop)

        row.addStretch(1)

        self.btn_open = _make_button("打开目录", "secondary", 36, 92,
                                     self._open_today_folder)
        row.addWidget(self.btn_open)
        return row

    def _build_log_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        head.setContentsMargins(2, 0, 0, 0)
        head_title = QLabel("下载日志")
        head_title.setObjectName("cardTitle")
        head.addWidget(head_title)
        head.addStretch(1)
        self.btn_clear_log = _make_button("清空", "ghost", 24, 48, self._clear_log)
        head.addWidget(self.btn_clear_log)
        lay.addLayout(head)

        self.log_edit = _LogView()
        self.log_edit.setObjectName("logEdit")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(96)
        lay.addWidget(self.log_edit, 1)
        return card

    def _clear_log(self):
        self.log_edit.clear()

    # ---------------- QSS ----------------
    def _apply_stylesheet(self):
        arrow = _make_down_arrow()
        self.setStyleSheet(f"""
            * {{ font-family: "Segoe UI Variable Text", "Segoe UI",
                             "Microsoft YaHei UI", sans-serif; }}

            /* 页面背景保持透明，让系统 Mica/Acrylic 透出来；
               卡片一律不透明，避免半透明白叠半透明白糊成一片灰。 */
            QWidget#root {{ background: transparent; }}
            QScrollArea#scrollArea {{ background: transparent; border: none; }}
            QWidget#pageViewport {{ background: transparent; }}

            QLabel {{ color: {TEXT_BODY}; background: transparent; }}
            #appTitle {{ font-size: 20px; font-weight: 600; color: {TEXT_MAIN}; }}
            #appSubtitle {{ font-size: 12px; color: {TEXT_MUTED}; }}

            #card {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 8px;
            }}
            #cardTitle {{ font-size: 13px; font-weight: 600; color: {TEXT_MAIN}; }}
            #fieldLabel {{ font-size: 12px; color: {TEXT_MUTED}; }}

            QToolTip {{
                background-color: {SURFACE};
                color: {TEXT_MAIN};
                border: 1px solid {BORDER};
                padding: 4px 8px;
                border-radius: 4px;
            }}

            /* ---- 输入框 / 下拉框（同高度、同圆角） ---- */
            QLineEdit, QComboBox {{
                background-color: {SURFACE_ALT};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 0 10px;
                color: {TEXT_MAIN};
                font-size: 13px;
                selection-background-color: {ACCENT};
                selection-color: #ffffff;
            }}
            QLineEdit:hover, QComboBox:hover {{ background-color: {SURFACE_HOVER}; }}
            QLineEdit:focus, QComboBox:focus {{
                background-color: {SURFACE};
                border: 1px solid {ACCENT};
            }}
            QLineEdit[readOnly="true"] {{ background-color: {LOG_BG}; color: {TEXT_MUTED}; }}
            QLineEdit[readOnly="true"]:hover {{ background-color: {LOG_BG}; }}
            QLineEdit:disabled, QComboBox:disabled {{
                color: {TEXT_FAINT};
                background-color: {LOG_BG};
                border: 1px solid {BORDER};
            }}

            QComboBox::drop-down {{ border: none; width: 26px; }}
            QComboBox::down-arrow {{ image: url({arrow}); width: 14px; height: 14px; }}
            QComboBox QAbstractItemView {{
                background-color: {SURFACE};
                border: 1px solid {BORDER};
                border-radius: 6px;
                padding: 4px;
                color: {TEXT_MAIN};
                outline: none;
                selection-background-color: #EAF1FE;
                selection-color: {TEXT_MAIN};
            }}
            QComboBox QAbstractItemView::item {{ min-height: 28px; padding-left: 6px; }}

            /* ---- 按钮 ---- */
            QPushButton {{
                background-color: {SURFACE};
                color: {TEXT_MAIN};
                border: 1px solid {BORDER_STRONG};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background-color: {SURFACE_ALT}; }}
            QPushButton:pressed {{ background-color: {SURFACE_HOVER}; }}
            QPushButton:disabled {{
                color: {TEXT_FAINT};
                border: 1px solid {BORDER};
                background-color: {LOG_BG};
            }}

            QPushButton#primary {{
                background-color: {ACCENT};
                border: 1px solid {ACCENT};
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton#primary:hover {{ background-color: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
            QPushButton#primary:pressed {{ background-color: {ACCENT_PRESSED}; border-color: {ACCENT_PRESSED}; }}
            QPushButton#primary:disabled {{
                background-color: #BFD5FF; border-color: #BFD5FF; color: #ffffff;
            }}

            QPushButton#ghost {{
                background: transparent;
                border: 1px solid transparent;
                color: {TEXT_BODY};
                padding: 0 10px;
                font-weight: 500;
            }}
            QPushButton#ghost:hover {{ background-color: {SURFACE_HOVER}; }}
            QPushButton#ghost:pressed {{ background-color: #DDE5F0; }}
            QPushButton#ghost:disabled {{ color: {TEXT_FAINT}; background: transparent; }}

            /* ---- 进度条 ---- */
            QProgressBar {{
                background-color: #E9EDF3;
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT};
                border-radius: 3px;
            }}

            /* ---- 缩略图 ---- */
            #thumb {{
                background-color: {SURFACE_ALT};
                border: 1px solid {BORDER};
                border-radius: 6px;
            }}

            /* ---- 预览信息 ---- */
            #infoTitle {{ font-size: 15px; font-weight: 600; color: {TEXT_MAIN}; }}
            #infoMeta {{ font-size: 12px; color: {TEXT_MUTED}; }}
            #statusText {{ font-size: 12px; color: {TEXT_BODY}; }}
            #percentText {{ font-size: 13px; font-weight: 600; color: {TEXT_MAIN}; }}

            /* ---- 日志 ---- */
            #logEdit {{
                background-color: {LOG_BG};
                color: {LOG_TEXT};
                border: 1px solid #E9EDF3;
                border-radius: 6px;
                padding: 6px 8px;
                font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
                font-size: 12px;
                selection-background-color: {ACCENT};
                selection-color: #ffffff;
            }}
            #logEdit:focus {{ border: 1px solid {BORDER_STRONG}; }}

            QScrollBar:vertical {{
                background: transparent; width: 10px; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_STRONG}; border-radius: 5px; min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #AEB9C7; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QScrollBar:horizontal {{
                background: transparent; height: 10px; margin: 2px;
            }}
            QScrollBar::handle:horizontal {{
                background: {BORDER_STRONG}; border-radius: 5px; min-width: 24px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: transparent; }}
        """)

    # ---------------- 日志输出（按级别着色 + 解析速度） ----------------
    def _append_log(self, msg: str):
        if msg.startswith(("[错误", "[失败")):
            tag = "err"
        elif msg.startswith("[警告"):
            tag = "warn"
        elif msg.startswith("[完成"):
            tag = "ok"
        else:
            tag = "info"

        ts = datetime.now().strftime("%H:%M:%S")
        cur = self.log_edit.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(LOG_COLORS[tag]))
        cur.insertText(f"[{ts}] {msg}\n", fmt)
        self.log_edit.setTextCursor(cur)
        self.log_edit.ensureCursorVisible()

        m = SPEED_RE.search(msg)
        m2 = ETA_RE.search(msg)
        if m or m2:
            parts = []
            if m:
                parts.append(f"↓ {m.group(1)}")
            if m2:
                parts.append(f"剩余 {m2.group(1)}")
            self.status_label.setText("下载中 · " + " · ".join(parts))

    # ---------------- 启动检查 ----------------
    def _startup_check(self):
        err = core.check_ytdlp()
        if err:
            self._append_log(f"[警告] {err}")
        ffmpeg = core.find_ffmpeg(self.config)
        if ffmpeg:
            self._append_log(f"[信息] ffmpeg 已找到：{ffmpeg}")
        else:
            w = core.check_ffmpeg(self.config)
            if w:
                self._append_log(f"[警告] {w}")

    # ---------------- 一键粘贴 ----------------
    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        # 注意：这里必须用 core 的模块级函数；过去写成 core.App._extract_url_from_text(text)
        # 是把实例方法当静态方法调，必然抛 TypeError，"一键粘贴"直接不可用。
        url = core.extract_url_from_text(text)
        if url:
            self.url_edit.setText(url)
            self.url_edit.setFocus()
        else:
            QMessageBox.warning(self, "剪贴板", "剪贴板内容不是有效链接，也未找到 URL。")

    # ---------------- 打开今日文件夹 ----------------
    def _open_today_folder(self):
        _, folder_path = core.get_today_folder(self.config["save_dir"])
        core.ensure_dir(folder_path)
        os.startfile(folder_path)

    # ---------------- 更改保存路径 ----------------
    def _change_save_dir(self):
        new_dir = QFileDialog.getExistingDirectory(
            self, "选择视频保存目录", self.config["save_dir"])
        if not new_dir:
            return
        self.config["save_dir"] = new_dir
        self.path_edit.setText(new_dir)
        core.ensure_dir(new_dir)
        core.save_config(self.config)

    # ---------------- 设置（简版） ----------------
    def _open_settings(self):
        # 这里打开一个简单说明对话框；如需完整设置页可在此扩展。
        QMessageBox.information(
            self, "设置",
            "当前为 Fluent 精简版界面。\n\n"
            "代理模式 / Cookie / 自动打开文件夹等高级选项，\n"
            "请编辑 config.json，或参考原版 video_downloader.py 的设置对话框。")

    # ---------------- 同步 UI 到配置 ----------------
    def _sync_ui_to_config(self):
        # 下拉框显示的是中文标签，原始值放在 itemData 里
        self.config["default_format"] = self.cb_format.currentData() or "mp4"
        self.config["default_quality"] = self.cb_quality.currentData() or "best"
        self.config["proxy_mode"] = self.cb_proxy.currentData() or "auto"
        core.save_config(self.config)

    # ---------------- 开始下载 ----------------
    def _start_download(self):
        url = self.url_edit.text().strip()
        if not url:
            self._append_log("[提示] 请先粘贴视频链接。")
            return

        err = core.check_ytdlp()
        if err:
            self._append_log(f"[错误] {err}")
            QMessageBox.critical(self, "依赖缺失", err)
            return

        self._sync_ui_to_config()
        self._set_ui_state(False)

        folder_name, target_dir = core.get_today_folder(self.config["save_dir"])
        core.ensure_dir(target_dir)
        ext = core.output_ext(self.config.get("default_format", "mp4"),
                              self.config.get("default_quality", "best"))
        output_path = core.get_next_filepath(target_dir, folder_name, ext=ext)

        ffmpeg_path = core.find_ffmpeg(self.config)
        if ffmpeg_path is None:
            self._append_log("[警告] 未找到 ffmpeg，部分格式可能无法合并。")

        self.progress.setValue(0)
        self.percent_label.setText("0.0%")
        self.status_label.setText("正在获取视频信息…")
        self.info_title.setText("正在获取视频信息…")
        self.info_meta.setText("时长：—")
        self.info_size.setText("预计大小：—")
        self.info_extra.setText("")
        self.thumb.setPixmap(_make_thumb_placeholder(206, 115))

        self._dl = core.Downloader(
            url=url, output_path=output_path, config=self.config,
            ffmpeg_path=ffmpeg_path,
            info_cb=self.sig.info.emit, progress_cb=self.sig.progress.emit,
            done_cb=self.sig.done.emit, log_cb=self.sig.log.emit,
            error_cb=self.sig.error.emit,
        )
        self._thread = threading.Thread(target=self._dl.run, daemon=True)
        self._thread.start()

    # ---------------- 信息回调 ----------------
    def _on_info(self, info: dict):
        title = info.get("title", "?")
        uploader = info.get("uploader", "?")
        duration = info.get("duration", 0)
        resolution = info.get("resolution", "?")
        platform = info.get("platform", "?")
        size = info.get("filesize", 0)

        self.info_title.setText(title)
        self.info_meta.setText(
            f"时长 {self._fmt_duration(duration)}   ·   {resolution}   ·   {platform}")
        self.info_size.setText(f"预计大小 {self._fmt_size(size)}")
        self.info_extra.setText(f"上传者：{uploader}")
        if self._dl is not None:
            self._append_log(f"[信息] 文件：{os.path.basename(self._dl.output_path)}")

        thumb_url = info.get("thumbnail", "")
        if thumb_url:
            self._load_thumbnail(thumb_url)

    @staticmethod
    def _fmt_duration(seconds):
        if not seconds:
            return "—"
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @staticmethod
    def _fmt_size(n):
        if not n:
            return "未知"
        n = float(n)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"

    # ---------------- 缩略图异步加载 ----------------
    def _load_thumbnail(self, url):
        try:
            reply = self._nam.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(lambda: self._on_thumb_done(reply))
        except Exception:
            pass

    def _on_thumb_done(self, reply):
        data = reply.readAll()
        reply.deleteLater()
        pm = QPixmap()
        if pm.loadFromData(data):
            pm = pm.scaled(206, 115, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.thumb.setPixmap(pm)

    # ---------------- 进度回调 ----------------
    def _on_progress(self, pct: float):
        self.progress.setValue(int(pct))
        self.percent_label.setText(f"{pct:.1f}%")

    # ---------------- 错误诊断 ----------------
    def _on_error(self, report: dict):
        category = report.get("category", "未知错误")
        reason = report.get("reason", "")
        solution = report.get("solution", "")
        self.status_label.setText(f"已失败 · {category}")
        QMessageBox.critical(self, "下载失败诊断报告",
                             f"【{category}】\n\n原因：{reason}\n\n建议：{solution}")

    # ---------------- 完成回调 ----------------
    def _on_done(self, ok: bool, msg: str):
        self._set_ui_state(True)
        if ok:
            self.progress.setValue(100)
            self.percent_label.setText("100.0%")
            self.status_label.setText("已完成")
            self._append_log(f"[完成] {msg}")
            self.url_edit.clear()
            self.url_edit.setFocus()
            if self.config.get("auto_open_folder", True):
                _, folder_path = core.get_today_folder(self.config["save_dir"])
                try:
                    os.startfile(folder_path)
                except Exception:
                    pass
        else:
            # 用户主动停止不该标红当"失败"报
            stopped = ("停止" in msg) or ("取消" in msg)
            self.status_label.setText("已停止 · 可以重新开始" if stopped else "已失败 · 见诊断提示")
            self._append_log(f"{'[提示]' if stopped else '[失败]'} {msg}")

    # ---------------- 停止下载 ----------------
    def _stop_download(self):
        if self._dl:
            self._dl.cancel()
        self.btn_stop.setEnabled(False)

    # ---------------- 更新核心 ----------------
    def _update_core(self):
        self.btn_update.setEnabled(False)
        self.btn_update.setText("更新中…")
        # 结果经信号回到主线程：Qt 控件只能在主线程里改
        threading.Thread(
            target=lambda: core.update_ytdlp(self.sig.core_update.emit),
            daemon=True).start()

    def _on_update_done(self, msg: str):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("更新核心")
        self._append_log(f"[更新核心] {msg}")

    # ---------------- UI 状态锁 ----------------
    def _set_ui_state(self, enabled: bool):
        self.url_edit.setEnabled(enabled)
        self.btn_paste.setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
        self.btn_change_path.setEnabled(enabled)
        self.cb_format.setEnabled(enabled)
        self.cb_quality.setEnabled(enabled)
        self.cb_proxy.setEnabled(enabled)
        self.btn_settings.setEnabled(enabled)
        self.btn_update.setEnabled(enabled)
        # 下载中才让"停止下载"可点（原来它一直是灰的，等于没有这个按钮）
        self.btn_stop.setEnabled(not enabled)

    # ---------------- 关闭 ----------------
    def closeEvent(self, event):
        if self._dl is not None:
            self._dl.cancel()
        super().closeEvent(event)


# ============================================================
# 入口
# ============================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 让 QSS 完全接管控件外观
    win = VideoDownloaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        tb = traceback.format_exc()
        _msgbox("程序启动失败", f"发生错误：\n\n{tb}", error=True)
        print(tb)
        raise
