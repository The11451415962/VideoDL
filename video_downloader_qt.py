#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器 —— Windows 11 Fluent Design（PySide6）版本
====================================================
基于 yt-dlp + PySide6，界面采用 Windows 11 流畅设计：
  · 背景半透明磨砂玻璃（Windows 11 Mica / Windows 10 Acrylic）
  · 主色高饱和科技蓝，卡片为半透明白底 + 8~12px 圆角
  · 统一 20px 外边距、卡片 100% 等宽对齐
  · 下拉框/输入框/按钮全部自定义 QSS，摒弃原生灰框

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

from PySide6.QtCore import Qt, QObject, Signal, QUrl
from PySide6.QtGui import (QColor, QIcon, QPainter, QPen, QPixmap,
                           QPalette, QTextCursor, QTextCharFormat)
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QGridLayout, QLabel, QLineEdit,
                               QPushButton, QComboBox, QProgressBar, QTextEdit,
                               QFrame, QSizePolicy, QFileDialog, QMessageBox)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

import video_downloader as core  # 复用 yt-dlp 后端逻辑


# ============================================================
# 配色常量（Fluent / 科技蓝）
# ============================================================
ACCENT = "#2D7DFF"          # 高饱和科技蓝（主色）
ACCENT_HOVER = "#1E6BEF"
ACCENT_PRESSED = "#155AD6"
TEXT_MAIN = "#1B2733"       # 主文字
TEXT_MUTED = "#5A6B7B"      # 次要文字
LOG_BG = "rgba(255, 255, 255, 0.55)"   # 日志浅色半透明（对应参考图）
LOG_TEXT = "#1B2733"
CARD_BG = "rgba(255, 255, 255, 0.55)"  # 卡片半透明白
CARD_BORDER = "rgba(255, 255, 255, 0.6)"
INPUT_BG = "rgba(255, 255, 255, 0.60)"

# 日志级别 → 颜色（浅色底）
LOG_COLORS = {"info": "#6B7A8D", "ok": "#1F9D55",
              "err": "#D64545", "warn": "#C77D0A"}

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
    p.setPen(QPen(QColor(TEXT_MUTED), 2))
    p.drawLine(7, 10, 12, 15)
    p.drawLine(12, 15, 17, 10)
    p.end()
    path = os.path.join(tempfile.gettempdir(), "videodl_down_arrow.png")
    pm.save(path, "PNG")
    return path.replace("\\", "/")


def _make_link_icon() -> QIcon:
    """生成链接图标（输入框左侧 Leading 图标）。"""
    pm = QPixmap(24, 24)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(ACCENT))
    # 两个交叠圆角矩形，模拟"链环"
    p.drawRoundedRect(2, 8, 12, 8, 4, 4)
    p.drawRoundedRect(10, 8, 12, 8, 4, 4)
    p.end()
    return QIcon(pm)


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
# 下载线程 → Qt 信号桥（跨线程安全）
# ============================================================
class DownloadSignals(QObject):
    info = Signal(dict)
    progress = Signal(float)
    done = Signal(bool, str)
    log = Signal(str)
    error = Signal(dict)


# ============================================================
# 主窗口
# ============================================================
class VideoDownloaderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频下载器")
        self.setWindowIcon(_make_app_icon())
        self.setMinimumSize(860, 620)
        self.resize(920, 760)

        self.config = core.load_config()
        core.ensure_dir(self.config["save_dir"])

        self.sig = DownloadSignals(self)
        self.sig.info.connect(self._on_info)
        self.sig.progress.connect(self._on_progress)
        self.sig.done.connect(self._on_done)
        self.sig.log.connect(self._append_log)
        self.sig.error.connect(self._on_error)

        self._dl = None
        self._thread = None
        self._nam = QNetworkAccessManager(self)

        # 磨砂背景（失败时回退为浅色不透明底，保证不透明黑块）
        if not enable_frosted(self):
            pal = self.palette()
            pal.setColor(QPalette.Window, QColor("#EDF2F9"))
            self.setPalette(pal)

        self._build_ui()
        self._apply_stylesheet()

        # 启动后检查依赖
        self._startup_check()

    # ---------------- UI 构建 ----------------
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        outer.addWidget(self._build_link_card())
        outer.addWidget(self._build_config_card())
        outer.addWidget(self._build_preview_card())
        outer.addLayout(self._build_buttons())
        outer.addWidget(self._build_log_card(), 1)

    def _build_header(self):
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("视频下载器")
        title.setObjectName("appTitle")
        sub = QLabel("现代化设计 · 功能集中 · 一目了然")
        sub.setObjectName("appSubtitle")
        box.addWidget(title)
        box.addWidget(sub)
        return box

    def _build_link_card(self):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlEdit")
        self.url_edit.setPlaceholderText("粘贴视频链接，例如 https://www.bilibili.com/video/BV...")
        self.url_edit.addAction(_make_link_icon(), QLineEdit.LeadingPosition)
        self.url_edit.returnPressed.connect(self._start_download)
        row.addWidget(self.url_edit, 1)

        self.btn_paste = QPushButton("一键粘贴")
        self.btn_paste.setObjectName("secondary")
        self.btn_paste.setFixedHeight(38)
        self.btn_paste.setCursor(Qt.PointingHandCursor)
        self.btn_paste.clicked.connect(self._paste_from_clipboard)
        row.addWidget(self.btn_paste)

        lay.addLayout(row)
        return card

    def _build_config_card(self):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        # 第一行：保存路径 + 更改路径
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_label = QLabel("保存路径")
        path_label.setObjectName("fieldLabel")
        path_row.addWidget(path_label)

        self.path_edit = QLineEdit(self.config["save_dir"])
        self.path_edit.setObjectName("pathEdit")
        self.path_edit.setReadOnly(True)
        path_row.addWidget(self.path_edit, 1)

        self.btn_change_path = QPushButton("更改路径")
        self.btn_change_path.setObjectName("secondary")
        self.btn_change_path.setFixedHeight(38)
        self.btn_change_path.setCursor(Qt.PointingHandCursor)
        self.btn_change_path.clicked.connect(self._change_save_dir)
        path_row.addWidget(self.btn_change_path)
        lay.addLayout(path_row)

        # 第二行：格式 / 清晰度 / 网络代理（三等分）
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        self.cb_format = self._make_combo(
            ["mp4", "webm", "mp3"],
            self.config.get("default_format", "mp4"))
        self.cb_quality = self._make_combo(
            ["best", "1080p", "720p", "audio"],
            self.config.get("default_quality", "best"))
        self.cb_proxy = self._make_combo(
            ["auto (自动)", "direct (直连)", "proxy (代理)"],
            core.App._label_for_proxy_mode(self.config.get("proxy_mode", "auto")))

        grid.addWidget(self._make_field("格式", self.cb_format), 0, 0)
        grid.addWidget(self._make_field("清晰度", self.cb_quality), 0, 1)
        grid.addWidget(self._make_field("网络代理", self.cb_proxy), 0, 2)
        lay.addLayout(grid)

        # 选择变化即时持久化
        self.cb_format.currentTextChanged.connect(self._sync_ui_to_config)
        self.cb_quality.currentTextChanged.connect(self._sync_ui_to_config)
        self.cb_proxy.currentTextChanged.connect(self._sync_ui_to_config)
        return card

    @staticmethod
    def _make_combo(values, current):
        cb = QComboBox()
        cb.setObjectName("combo")
        cb.addItems(values)
        cb.setCurrentText(current)
        cb.setCursor(Qt.PointingHandCursor)
        return cb

    @staticmethod
    def _make_field(label, widget):
        box = QVBoxLayout()
        box.setSpacing(6)
        lbl = QLabel(label)
        lbl.setObjectName("fieldLabel")
        box.addWidget(lbl)
        box.addWidget(widget)
        wrap = QWidget()
        wrap.setObjectName("fieldWrap")
        wrap.setLayout(box)
        return wrap

    def _build_preview_card(self):
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(16)

        # 缩略图占位（16:9，圆角）
        self.thumb = QLabel("[Video Thumbnail Placeholder]")
        self.thumb.setObjectName("thumb")
        self.thumb.setAlignment(Qt.AlignCenter)
        self.thumb.setFixedSize(320, 180)
        top.addWidget(self.thumb)

        # 右侧信息：视频标题 / 时长 / 预计大小（标签 + 值）
        info = QVBoxLayout()
        info.setSpacing(8)
        self.info_title = QLabel("视频标题：等待粘贴链接...")
        self.info_title.setObjectName("infoTitle")
        self.info_title.setWordWrap(True)
        info.addWidget(self.info_title)

        self.info_meta = QLabel("时长：—")
        self.info_meta.setObjectName("infoMeta")
        info.addWidget(self.info_meta)

        self.info_size = QLabel("预计大小：—")
        self.info_size.setObjectName("infoMeta")
        info.addWidget(self.info_size)

        # 附加信息（分辨率 / 平台 / 上传者，次要灰字）
        self.info_extra = QLabel("")
        self.info_extra.setObjectName("infoMeta")
        info.addWidget(self.info_extra)
        info.addStretch(1)
        top.addLayout(info, 1)
        lay.addLayout(top)

        # 进度条 + 右侧百分比
        prog_row = QHBoxLayout()
        prog_row.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(10)
        self.progress.setTextVisible(False)
        prog_row.addWidget(self.progress, 1)
        self.percent_label = QLabel("0.0%")
        self.percent_label.setObjectName("statusText")
        prog_row.addWidget(self.percent_label)
        lay.addLayout(prog_row)

        # 状态栏（对应参考图：正在等待粘贴链接... (0 KB/s - 剩余: --:--)）
        self.status_label = QLabel("正在等待粘贴链接... (0 KB/s - 剩余: --:--)")
        self.status_label.setObjectName("statusText")
        lay.addWidget(self.status_label)
        return card

    def _build_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        self.btn_download = QPushButton("开始下载")
        self.btn_download.setObjectName("primary")
        self.btn_download.setFixedHeight(38)
        self.btn_download.setCursor(Qt.PointingHandCursor)
        self.btn_download.clicked.connect(self._start_download)
        row.addWidget(self.btn_download)

        self.btn_stop = QPushButton("停止下载")
        self.btn_stop.setObjectName("secondary")
        self.btn_stop.setFixedHeight(38)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_download)
        row.addWidget(self.btn_stop)

        self.btn_open = QPushButton("打开目录")
        self.btn_open.setObjectName("secondary")
        self.btn_open.setFixedHeight(38)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_today_folder)
        row.addWidget(self.btn_open)

        self.btn_settings = QPushButton("设置")
        self.btn_settings.setObjectName("secondary")
        self.btn_settings.setFixedHeight(38)
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self._open_settings)
        row.addWidget(self.btn_settings)

        row.addStretch(1)

        self.btn_update = QPushButton("更新核心")
        self.btn_update.setObjectName("linkBtn")
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.clicked.connect(self._update_core)
        row.addWidget(self.btn_update)
        return row

    def _build_log_card(self):
        self.log_edit = QTextEdit()
        self.log_edit.setObjectName("logEdit")
        self.log_edit.setReadOnly(True)
        return self.log_edit

    # ---------------- QSS ----------------
    def _apply_stylesheet(self):
        arrow = _make_down_arrow()
        self.setStyleSheet(f"""
            * {{ font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif; }}

            QWidget#root {{ background: transparent; }}

            QLabel {{ color: {TEXT_MAIN}; background: transparent; }}
            #appTitle {{ font-size: 22px; font-weight: 700; }}
            #appSubtitle {{ font-size: 12px; color: {TEXT_MUTED}; }}

            #card {{
                background-color: {CARD_BG};
                border: 1px solid {CARD_BORDER};
                border-radius: 12px;
            }}

            #fieldLabel {{ font-size: 12px; font-weight: 600; color: {TEXT_MUTED}; }}

            /* ---- 输入框 ---- */
            QLineEdit {{
                background-color: {INPUT_BG};
                border: 1px solid rgba(120, 140, 165, 0.35);
                border-radius: 8px;
                padding: 8px 12px;
                color: {TEXT_MAIN};
                selection-background-color: {ACCENT};
            }}
            QLineEdit:focus {{ border: 1px solid {ACCENT}; background-color: rgba(255,255,255,0.85); }}
            QLineEdit[readOnly="true"] {{ background-color: rgba(255,255,255,0.35); color: {TEXT_MUTED}; }}

            /* ---- 下拉框（自定义，摒弃原生灰框） ---- */
            QComboBox {{
                background-color: {INPUT_BG};
                border: 1px solid rgba(120, 140, 165, 0.35);
                border-radius: 8px;
                padding: 6px 12px;
                color: {TEXT_MAIN};
                min-height: 24px;
            }}
            QComboBox:hover {{ border: 1px solid {ACCENT}; }}
            QComboBox:focus {{ border: 1px solid {ACCENT}; background-color: rgba(255,255,255,0.85); }}
            QComboBox::drop-down {{ border: none; width: 28px; }}
            QComboBox::down-arrow {{ image: url({arrow}); width: 14px; height: 14px; }}
            QComboBox QAbstractItemView {{
                background-color: rgba(255, 255, 255, 0.96);
                border: 1px solid rgba(120, 140, 165, 0.3);
                border-radius: 8px;
                color: {TEXT_MAIN};
                outline: none;
                selection-background-color: {ACCENT};
                selection-color: #ffffff;
                padding: 4px;
            }}

            /* ---- 按钮 ---- */
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.45);
                color: {TEXT_MAIN};
                border: 1px solid rgba(120, 140, 165, 0.30);
                border-radius: 6px;
                padding: 0 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: rgba(255, 255, 255, 0.70); }}
            QPushButton:pressed {{ background-color: rgba(255, 255, 255, 0.50); }}
            QPushButton:disabled {{ color: rgba(27, 39, 51, 0.35); }}

            QPushButton#primary {{
                background-color: {ACCENT};
                color: #ffffff;
                border: none;
            }}
            QPushButton#primary:hover {{ background-color: {ACCENT_HOVER}; }}
            QPushButton#primary:pressed {{ background-color: {ACCENT_PRESSED}; }}
            QPushButton#primary:disabled {{ background-color: rgba(45, 125, 255, 0.4); color: rgba(255,255,255,0.8); }}

            QPushButton#secondary {{ background-color: rgba(255, 255, 255, 0.45); }}
            QPushButton#secondary:hover {{ background-color: rgba(255, 255, 255, 0.70); }}

            QPushButton#linkBtn {{
                background: transparent;
                border: none;
                color: {ACCENT};
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton#linkBtn:hover {{ color: {ACCENT_HOVER}; text-decoration: underline; }}

            /* ---- 进度条 ---- */
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.5);
                border: none;
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                                  stop:0 {ACCENT}, stop:1 #6AA6FF);
                border-radius: 5px;
            }}

            /* ---- 缩略图占位 ---- */
            #thumb {{
                background-color: rgba(255, 255, 255, 0.40);
                border: 1px solid rgba(120, 140, 165, 0.3);
                border-radius: 12px;
                color: {TEXT_MUTED};
            }}

            /* ---- 预览信息 ---- */
            #infoTitle {{ font-size: 16px; font-weight: 700; }}
            #infoMeta {{ font-size: 12px; color: {TEXT_MUTED}; }}
            #statusText {{ font-size: 12px; color: {TEXT_MUTED}; }}

            /* ---- 日志 ---- */
            #logEdit {{
                background-color: {LOG_BG};
                color: {LOG_TEXT};
                border: 1px solid rgba(120, 140, 165, 0.28);
                border-radius: 10px;
                padding: 8px;
                font-family: "Consolas", "Courier New", monospace;
                font-size: 12px;
                selection-background-color: {ACCENT};
            }}
            #logEdit:focus {{ border: 1px solid {ACCENT}; }}

            QScrollBar:vertical {{
                background: transparent; width: 10px; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(120, 140, 165, 0.45); border-radius: 5px; min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{ background: rgba(120, 140, 165, 0.65); }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
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
            speed = m.group(1) if m else "0 KB/s"
            eta = m2.group(1) if m2 else "--:--"
            self.status_label.setText(f"正在下载... ({speed} - 剩余: {eta})")

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
        url = core.App._extract_url_from_text(text) if hasattr(core.App, "_extract_url_from_text") else None
        if url:
            self.url_edit.setText(url)
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
        self.config["default_format"] = self.cb_format.currentText()
        self.config["default_quality"] = self.cb_quality.currentText()
        label = self.cb_proxy.currentText()
        self.config["proxy_mode"] = core.App._proxy_raw_from_label(label)
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
        self.status_label.setText("正在获取视频信息... (0 KB/s - 剩余: --:--)")
        self.info_title.setText("视频标题：正在获取视频信息...")
        self.info_meta.setText("时长：—")
        self.info_size.setText("预计大小：—")
        self.info_extra.setText("")

        self._dl = core.Downloader(
            url=url, output_path=output_path, config=self.config,
            ffmpeg_path=ffmpeg_path,
            info_cb=self.sig.info.emit, progress_cb=self.sig.progress.emit,
            done_cb=self.sig.done.emit, log_cb=self.sig.log.emit,
            error_cb=self.sig.error.emit,
        )
        self._thread = __import__("threading").Thread(target=self._dl.run, daemon=True)
        self._thread.start()

    # ---------------- 信息回调 ----------------
    def _on_info(self, info: dict):
        title = info.get("title", "?")
        uploader = info.get("uploader", "?")
        duration = info.get("duration", 0)
        resolution = info.get("resolution", "?")
        platform = info.get("platform", "?")
        size = info.get("filesize", 0)

        self.info_title.setText(f"视频标题：{title}")
        self.info_meta.setText(f"时长：{self._fmt_duration(duration)}")
        self.info_size.setText(f"预计大小：{self._fmt_size(size)}")
        self.info_extra.setText(
            f"分辨率：{resolution}    平台：{platform}    上传者：{uploader}")
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
            pm = pm.scaled(self.thumb.size(), Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
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
        QMessageBox.critical(self, "下载失败诊断报告",
                             f"【{category}】\n\n原因：{reason}\n\n建议：{solution}")

    # ---------------- 完成回调 ----------------
    def _on_done(self, ok: bool, msg: str):
        self._set_ui_state(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("正在等待粘贴链接... (0 KB/s - 剩余: --:--)")
        if ok:
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
            self._append_log(f"[失败] {msg}")

    # ---------------- 停止下载 ----------------
    def _stop_download(self):
        if self._dl:
            self._dl.cancel()
        self.btn_stop.setEnabled(False)

    # ---------------- 更新核心 ----------------
    def _update_core(self):
        self.btn_update.setEnabled(False)
        self.btn_update.setText("更新中…")
        t = __import__("threading").Thread(
            target=lambda: core.update_ytdlp(self._on_update_done), daemon=True)
        t.start()

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
