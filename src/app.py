# -*- coding: utf-8 -*-
"""
班级桌面助手 v1.2.3-Beta.1 - 学生端
功能：系统托盘、管理员界面（只读）、导入教师课表、实用工具（关机/提醒/备忘录/联网）
"""

import sys
import os
import json
import platform
import subprocess
import uuid
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from PySide6.QtCore import (
    Qt, QUrl, Signal, QMimeData, QTimer, QDateTime, QTime, QDate,
    QThread, QObject, QPropertyAnimation, QEasingCurve, QRect, QPoint
)
from PySide6.QtGui import (
    QIcon, QAction, QFont, QColor, QPalette, QPainter, QPen,
    QBrush, QLinearGradient, QPixmap, QDragEnterEvent, QDropEvent,
    QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QWidget,
    QVBoxLayout, QLabel, QPushButton, QDialog, QFormLayout,
    QLineEdit, QComboBox, QTextEdit, QMessageBox,
    QFrame, QHBoxLayout, QCheckBox, QFileDialog,
    QToolButton, QTabWidget, QGroupBox, QSlider,
    QSpacerItem, QSizePolicy,
    QListWidget, QListWidgetItem, QSpinBox, QDateTimeEdit,
    QInputDialog, QSplitter, QAbstractItemView
)
from PySide6.QtWebEngineWidgets import QWebEngineView

# ============================================================
# 路径常量（兼容 PyInstaller 打包）
# ============================================================
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    RESOURCE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    RESOURCE_DIR = APP_DIR

HTML_FILE = os.path.join(RESOURCE_DIR, "student.html")
SETTINGS_FILE = os.path.join(APP_DIR, "app_settings.json")
STUDENT_ICO = os.path.join(RESOURCE_DIR, "student.ico")

PERIODS = [
    "08:00-08:45", "08:55-09:40", "10:00-10:45", "10:55-11:40",
    "13:30-14:15", "14:25-15:10", "15:30-16:15", "16:25-17:10",
    "19:00-19:45", "19:55-20:40",
]
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ============================================================
# 设置管理
# ============================================================
def load_settings():
    defaults = {
        "minimize_to_tray": True,
        "auto_start": False,
        "schedule_locked": False,
        "admin_password": "",
        "dev_password": "",
        "memos": [],          # 备忘录列表 [{id, title, content, created_at, updated_at}]
        "reminders": [],      # 提醒列表 [{id, title, datetime, repeat, enabled, last_triggered}]
        "network": {
            "update_url": "",          # 版本检查 JSON 的 URL
            "notice_url": "",          # 公告 JSON 的 URL
            "github_token": "",        # GitHub Personal Access Token (需 gist 权限)
            "gist_id": "",             # Gist ID (首次同步时自动创建并保存)
            "auto_check_update": True, # 启动时自动检查更新
            "auto_sync": False,        # 自动云同步
            "last_sync_time": "",      # 上次同步时间
            "seen_notice_ids": [],     # 已读公告 ID
        },
    }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            defaults.update(data)
    except:
        pass
    return defaults


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 普通设置界面
# ============================================================
class SettingsDialog(QDialog):
    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.app = app
        self.setWindowTitle("⚙️ 设置")
        self.setFixedSize(460, 260)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #14142a; }
            QGroupBox {
                color: #60a5fa; font-size: 13px; font-weight: 700;
                border: 1px solid rgba(59, 130, 246, 0.15);
                border-radius: 12px; margin-top: 14px; padding: 20px 16px 14px 16px;
                background: rgba(22, 26, 48, 0.6);
            }
            QGroupBox::title {
                subcontrol-origin: margin; left: 16px; padding: 0 8px;
                color: #60a5fa;
            }
            QCheckBox { color: #dfe6e9; font-size: 13px; spacing: 8px; }
            QCheckBox::indicator {
                width: 18px; height: 18px; border-radius: 4px;
                border: 1px solid rgba(59, 130, 246, 0.3);
                background: #1e1e3a;
            }
            QCheckBox::indicator:checked {
                background: #3b82f6; border-color: #3b82f6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 16, 20, 14)

        # --- 显示设置 ---
        disp_group = QGroupBox("显示设置")
        disp_layout = QVBoxLayout(disp_group)
        disp_layout.setContentsMargins(12, 6, 12, 8)

        self.chk_tray = QCheckBox("关闭窗口时最小化到系统托盘（而不是退出）")
        self.chk_tray.setChecked(self.settings.get("minimize_to_tray", True))
        disp_layout.addWidget(self.chk_tray)

        layout.addWidget(disp_group)

        # --- 启动设置 ---
        boot_group = QGroupBox("启动设置")
        boot_layout = QVBoxLayout(boot_group)
        boot_layout.setContentsMargins(12, 6, 12, 8)

        self.chk_autostart = QCheckBox("开机自启动")
        self.chk_autostart.setChecked(self.settings.get("auto_start", False))
        boot_layout.addWidget(self.chk_autostart)

        layout.addWidget(boot_group)
        layout.addStretch()

        # --- 按钮 ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("保存")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: #fff; border: none;
                border-radius: 8px; padding: 9px 26px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #60a5fa; }
            QPushButton:pressed { background: #2563eb; }
        """)
        btn_save.clicked.connect(self._save)
        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.12); color: #93c5fd;
                border: 1px solid rgba(59, 130, 246, 0.25);
                border-radius: 8px; padding: 9px 26px; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { background: #3b82f6; color: #fff; border-color: #3b82f6; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

    def _save(self):
        self.settings["minimize_to_tray"] = self.chk_tray.isChecked()
        self.settings["auto_start"] = self.chk_autostart.isChecked()
        save_settings(self.settings)
        self.accept()


# ============================================================
# 关于对话框
# ============================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(400, 370)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #14142a; border: 1px solid rgba(59,130,246,0.12); border-radius: 12px; }
            QLabel { color: #dfe6e9; background: transparent; border: none; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(36, 32, 36, 28)

        icon_lbl = QLabel("📚")
        icon_lbl.setStyleSheet("font-size: 48px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel("班级桌面助手 - 学生端")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("font-size: 21px; font-weight: 600; color: #60a5fa; background: transparent; border: none; letter-spacing: 1px;")
        layout.addWidget(title_lbl)

        ver_lbl = QLabel("v1.2.3-Beta.1")
        ver_lbl.setAlignment(Qt.AlignCenter)
        ver_lbl.setStyleSheet("""
            font-size: 11px; color: #60a5fa;
            background: rgba(59,130,246,0.10);
            border: 1px solid rgba(59,130,246,0.15);
            border-radius: 10px; padding: 3px 16px;
        """)
        ver_wrap = QHBoxLayout()
        ver_wrap.addStretch()
        ver_wrap.addWidget(ver_lbl)
        ver_wrap.addStretch()
        layout.addLayout(ver_wrap)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: rgba(59, 130, 246, 0.12); border: none; max-height: 1px; margin: 6px 0;")
        layout.addWidget(line)

        info_lbl = QLabel(
            "一款轻量级的班级管理工具<br>"
            "作业记录 · 课程表管理 · 教师课表导入<br>"
            "关机控制 · 定时提醒 · 备忘录 · 联网功能<br><br>"
            "<span style='color:#636e72;'>技术栈</span>&nbsp;&nbsp;Python + PySide6 + QtWebEngine<br>"
            "<span style='color:#636e72;'>数据存储</span>&nbsp;&nbsp;本地 localStorage<br>"
            "<span style='color:#636e72;'>作&nbsp;&nbsp;&nbsp;者</span>&nbsp;&nbsp;CHCZ-LeonLin、FENG"
        )
        info_lbl.setStyleSheet("font-size: 12px; color: #dfe6e9; background: transparent; border: none; line-height: 2.0;")
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        layout.addStretch()

        btn_close = QPushButton("关 闭")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.10);
                color: #60a5fa;
                border: 1px solid rgba(59, 130, 246, 0.22);
                border-radius: 8px;
                padding: 9px 40px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #3b82f6;
                color: #fff;
                border-color: #3b82f6;
            }
        """)
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        layout.addLayout(btn_row)


# ============================================================
# 导入课表窗口（支持拖拽 + 浏览）
# ============================================================
IMPORT_STYLE = """
QDialog { background: #14142a; }
QLabel { color: #dfe6e9; background: transparent; border: none; }
QPushButton {
    background: rgba(59, 130, 246, 0.10); color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.22);
    border-radius: 8px; padding: 8px 18px; font-size: 12px;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QPushButton:hover { background: #3b82f6; color: #fff; border-color: #3b82f6; }
QPushButton[primary="true"] { background: #3b82f6; color: #fff; border: none; font-weight: 600; }
QPushButton[primary="true"]:hover { background: #60a5fa; }
QLineEdit {
    background: #16162e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 8px; padding: 8px 12px;
}
"""

class ImportDialog(QDialog):
    """课表导入窗口，支持拖拽 JSON 文件和浏览选择"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_path = None
        self.setWindowTitle("📥 导入教师课表")
        self.setFixedSize(480, 360)
        self.setStyleSheet(IMPORT_STYLE)
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        # 标题
        title = QLabel("📥 导入教师课表")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #60a5fa; letter-spacing: 0.5px;")
        layout.addWidget(title)

        # 拖拽区域
        self.drop_zone = QFrame()
        self.drop_zone.setAcceptDrops(True)
        self.drop_zone.setFrameShape(QFrame.NoFrame)
        self.drop_zone.setStyleSheet("""
            QFrame {
                background: rgba(22, 33, 62, 0.5);
                border: 2px dashed rgba(59, 130, 246, 0.3);
                border-radius: 12px;
            }
        """)
        self.drop_zone.setMinimumHeight(160)
        dz_layout = QVBoxLayout(self.drop_zone)
        dz_layout.setAlignment(Qt.AlignCenter)
        dz_layout.setSpacing(10)

        self.drop_icon = QLabel("📂")
        self.drop_icon.setStyleSheet("font-size: 42px; border: none; background: transparent;")
        self.drop_icon.setAlignment(Qt.AlignCenter)
        dz_layout.addWidget(self.drop_icon)

        self.drop_text = QLabel("将教师课表 JSON 文件拖拽到此处")
        self.drop_text.setStyleSheet("font-size: 14px; color: #60a5fa; border: none; background: transparent;")
        self.drop_text.setAlignment(Qt.AlignCenter)
        dz_layout.addWidget(self.drop_text)

        self.drop_hint = QLabel("或点击下方按钮浏览文件")
        self.drop_hint.setStyleSheet("font-size: 12px; color: #636e72; border: none; background: transparent;")
        self.drop_hint.setAlignment(Qt.AlignCenter)
        dz_layout.addWidget(self.drop_hint)

        layout.addWidget(self.drop_zone)

        # 文件信息
        self.file_info = QLabel("")
        self.file_info.setStyleSheet("""
            font-size: 12px; color: #06b6d4;
            background: rgba(6,182,212,0.08);
            border: 1px solid rgba(6,182,212,0.2);
            border-radius: 8px; padding: 8px 12px;
        """)
        self.file_info.setWordWrap(True)
        self.file_info.setVisible(False)
        layout.addWidget(self.file_info)

        layout.addStretch()

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_browse = QPushButton("📁 浏览文件")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.15);
                color: #60a5fa;
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 8px; padding: 9px 20px; font-size: 13px;
            }
            QPushButton:hover {
                background: #3b82f6; color: #fff; border-color: #3b82f6;
            }
        """)
        btn_browse.clicked.connect(self._browse)
        btn_row.addWidget(btn_browse)

        btn_row.addStretch()

        btn_cancel = QPushButton("取消")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.06);
                color: #636e72;
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 8px; padding: 9px 20px; font-size: 13px;
            }
            QPushButton:hover { background: rgba(255,255,255,0.1); color: #dfe6e9; }
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self.btn_import = QPushButton("✅ 开始导入")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setEnabled(False)
        self.btn_import.setStyleSheet("""
            QPushButton {
                background: #3b82f6; color: #fff; border: none;
                border-radius: 8px; padding: 9px 24px; font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:disabled {
                background: #2d2d4a; color: #636e72;
            }
        """)
        self.btn_import.clicked.connect(self._do_import)
        btn_row.addWidget(self.btn_import)

        layout.addLayout(btn_row)

    def _set_file(self, path):
        """设置选中的文件路径"""
        if not path.lower().endswith('.json'):
            self._show_error("仅支持 JSON 文件，请选择 .json 文件")
            return

        if not os.path.exists(path):
            self._show_error("文件不存在")
            return

        self.selected_path = path
        fname = os.path.basename(path)
        fsize = os.path.getsize(path)
        if fsize > 1024 * 1024:
            size_str = f"{fsize / (1024 * 1024):.1f} MB"
        elif fsize > 1024:
            size_str = f"{fsize / 1024:.1f} KB"
        else:
            size_str = f"{fsize} B"

        self.file_info.setText(f"📄 {fname}  ·  {size_str}")
        self.file_info.setVisible(True)
        self.btn_import.setEnabled(True)

        # 更新拖拽区样式
        self.drop_zone.setStyleSheet("""
            QFrame {
                background: rgba(6,182,212,0.06);
                border: 2px solid rgba(6,182,212,0.5);
                border-radius: 14px;
            }
        """)
        self.drop_icon.setText("✅")
        self.drop_text.setText("文件已选择")
        self.drop_text.setStyleSheet("font-size: 14px; color: #06b6d4; border: none; background: transparent;")

    def _show_error(self, msg):
        self.file_info.setText(f"⚠️ {msg}")
        self.file_info.setStyleSheet("""
            font-size: 12px; color: #e17055;
            background: rgba(225,112,85,0.08);
            border: 1px solid rgba(225,112,85,0.2);
            border-radius: 8px; padding: 8px 12px;
        """)
        self.file_info.setVisible(True)
        self.selected_path = None
        self.btn_import.setEnabled(False)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择教师导出的课表文件", "", "JSON Files (*.json)"
        )
        if path:
            self._set_file(path)

    def _do_import(self):
        if self.selected_path:
            self.accept()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().lower().endswith('.json'):
                event.acceptProposedAction()
                self.drop_zone.setStyleSheet("""
                    QFrame {
                        background: rgba(59,130,246,0.1);
                        border: 2px solid #3b82f6;
                        border-radius: 14px;
                    }
                """)
                self.drop_icon.setText("📥")
                self.drop_text.setText("松开以导入文件")
                self.drop_text.setStyleSheet("font-size: 14px; color: #3b82f6; border: none; background: transparent;")
            else:
                event.ignore()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._reset_drop_style()
        event.accept()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self._set_file(path)
        event.acceptProposedAction()

    def _reset_drop_style(self):
        if self.selected_path:
            self.drop_zone.setStyleSheet("""
                QFrame {
                    background: rgba(6,182,212,0.06);
                    border: 2px solid rgba(6,182,212,0.5);
                    border-radius: 14px;
                }
            """)
            self.drop_icon.setText("✅")
            self.drop_text.setText("文件已选择")
            self.drop_text.setStyleSheet("font-size: 14px; color: #06b6d4; border: none; background: transparent;")
        else:
            self.drop_zone.setStyleSheet("""
                QFrame {
                    background: #16213e;
                    border: 2px dashed rgba(59, 130, 246, 0.4);
                    border-radius: 14px;
                }
            """)
            self.drop_icon.setText("📂")
            self.drop_text.setText("将教师课表 JSON 文件拖拽到此处")
            self.drop_text.setStyleSheet("font-size: 14px; color: #60a5fa; border: none; background: transparent;")


# ============================================================
# 管理员界面（只读）
# ============================================================
class AdminDialog(QDialog):
    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        self.setWindowTitle("🔐 管理员界面")
        self.setFixedSize(480, 380)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        # --- 密码验证 ---
        pw_group = QGroupBox("管理员密码")
        pw_layout = QHBoxLayout(pw_group)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("输入管理员密码（留空表示无密码）")
        pw_layout.addWidget(self.pw_input)

        btn_pw = QPushButton("验证")
        btn_pw.setStyleSheet("background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 16px;")
        btn_pw.clicked.connect(self._verify_pw)
        pw_layout.addWidget(btn_pw)

        layout.addWidget(pw_group)

        # --- 功能区（只读） ---
        self.func_group = QGroupBox("数据查看（只读）")
        self.func_group.setEnabled(False)
        func_layout = QVBoxLayout(self.func_group)

        # 查看原始数据
        btn_view = QPushButton("📋 查看原始数据")
        btn_view.setStyleSheet(self._btn_style())
        btn_view.clicked.connect(self._view_data)
        func_layout.addWidget(btn_view)

        # 导入教师课表
        btn_import = QPushButton("📥 导入教师课表")
        btn_import.setStyleSheet(self._btn_style())
        btn_import.clicked.connect(self._import_schedule)
        func_layout.addWidget(btn_import)

        # 锁定课程表
        self.chk_lock = QCheckBox("🔒 锁定课程表（防止误改）")
        self.chk_lock.setChecked(self.settings.get("schedule_locked", False))
        func_layout.addWidget(self.chk_lock)

        layout.addWidget(self.func_group)

        # --- 修改密码 ---
        pw_change_group = QGroupBox("修改管理员密码")
        pw_change_layout = QFormLayout(pw_change_group)
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.Password)
        self.new_pw.setPlaceholderText("输入新密码（留空=无密码）")
        pw_change_layout.addRow("新密码：", self.new_pw)
        btn_change_pw = QPushButton("修改密码")
        btn_change_pw.setStyleSheet("background:#3b82f6;color:#fff;border:none;border-radius:6px;padding:6px 16px;")
        btn_change_pw.clicked.connect(self._change_pw)
        pw_change_layout.addRow(btn_change_pw)
        pw_change_group.setEnabled(False)
        self.pw_change_group = pw_change_group

        layout.addWidget(pw_change_group)
        layout.addStretch()

        # 关闭按钮
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.setStyleSheet("background:#e8e8f0;color:#636e72;border:none;border-radius:8px;padding:8px 24px;")
        btn_close.clicked.connect(self._close)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _btn_style(self):
        return """
            QPushButton {
                background: #f0f2ff; color: #3b82f6; border: 1px solid #3b82f6;
                border-radius: 6px; padding: 8px 16px; font-size: 13px;
                text-align: left;
            }
            QPushButton:hover { background: #3b82f6; color: #fff; }
        """

    def _verify_pw(self):
        stored = self.settings.get("admin_password", "")
        entered = self.pw_input.text()
        if stored == "" or entered == stored:
            self.func_group.setEnabled(True)
            self.pw_change_group.setEnabled(True)
            self.pw_input.setEnabled(False)
            QMessageBox.information(self, "验证成功", "✅ 管理员权限已开启")
        else:
            QMessageBox.warning(self, "验证失败", "❌ 密码错误")

    def _change_pw(self):
        self.settings["admin_password"] = self.new_pw.text()
        save_settings(self.settings)
        QMessageBox.information(self, "成功", "✅ 密码已修改")

    def _close(self):
        # 保存锁定状态
        self.settings["schedule_locked"] = self.chk_lock.isChecked()
        save_settings(self.settings)
        self.accept()

    def _view_data(self):
        if not self.parent_app:
            return
        self.parent_app.view_raw_data(self)

    def _import_schedule(self):
        if not self.parent_app:
            return
        dlg = ImportDialog(parent=self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.parent_app.import_schedule(dlg.selected_path, self)


# ============================================================
# 开发者界面
# ============================================================
DEV_STYLE = """
QDialog { background: #0d0d20; }
QGroupBox {
    color: #60a5fa; font-size: 12px; font-weight: 600;
    border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 12px;
    margin-top: 14px;
    padding: 20px 14px 14px 14px;
    background: rgba(22, 26, 48, 0.4);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
}
QLabel { color: #dfe6e9; font-size: 12px; background: transparent; border: none; }
QTextEdit {
    background: #14142a; color: #06b6d4; font-family: "Cascadia Code", "Consolas", "JetBrains Mono", "Courier New", monospace;
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.10);
    border-radius: 8px; padding: 10px;
}
QLineEdit {
    background: #14142a; color: #dfe6e9; font-family: "Cascadia Code", "Consolas", "JetBrains Mono", "Courier New", monospace;
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 8px; padding: 8px 12px;
}
QLineEdit:focus { border-color: #3b82f6; }
QPushButton {
    background: rgba(59, 130, 246, 0.10); color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.22);
    border-radius: 8px; padding: 8px 18px; font-size: 12px;
}
QPushButton:hover { background: #3b82f6; color: #fff; border-color: #3b82f6; }
QPushButton:pressed { background: #2563eb; }
QPushButton:disabled { background: #14142a; color: #636e72; border-color: #2d2d4a; }
QTabWidget::pane {
    border: none;
    border-top: 1px solid rgba(59, 130, 246, 0.10);
    background: transparent;
}
QTabBar::tab {
    background: transparent; color: #636e72;
    padding: 8px 20px; margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: transparent; color: #60a5fa;
    border: none;
    border-bottom: 2px solid #3b82f6;
}
QTabBar::tab:hover:!selected { color: #60a5fa; border-bottom: 2px solid rgba(59, 130, 246, 0.3); }
QCheckBox { color: #dfe6e9; font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(59, 130, 246, 0.25);
    background: #14142a;
}
QCheckBox::indicator:checked {
    background: #3b82f6; border-color: #3b82f6;
}
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(59, 130, 246, 0.25); border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: rgba(59, 130, 246, 0.4); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

class DeveloperDialog(QDialog):
    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        self.setWindowTitle("开发者工具")
        self.setFixedSize(580, 560)
        self.setStyleSheet(DEV_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QHBoxLayout()
        title = QLabel("🛠 开发者工具")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #06b6d4;")
        header.addWidget(title)
        header.addStretch()

        self.lbl_pid = QLabel(f"PID: {os.getpid()}")
        self.lbl_pid.setStyleSheet("color: #636e72; font-size: 11px;")
        header.addWidget(self.lbl_pid)
        layout.addLayout(header)

        auth = QHBoxLayout()
        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("开发者密码（留空=无密码）")
        auth.addWidget(self.pw_input)
        btn_verify = QPushButton("验证")
        btn_verify.clicked.connect(self._verify)
        auth.addWidget(btn_verify)
        layout.addLayout(auth)

        self.tabs = QTabWidget()
        self.tabs.setEnabled(False)
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._tab_env(), "环境信息")
        self.tabs.addTab(self._tab_stats(), "数据统计")
        self.tabs.addTab(self._tab_console(), "JS 控制台")
        self.tabs.addTab(self._tab_storage(), "localStorage")
        self.tabs.addTab(self._tab_devset(), "开发者设置")

        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _tab_env(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(6)

        info = (
            f"<b style='color:#60a5fa;'>Python</b>  {sys.version.split(' ')[0]}<br>"
            f"<b style='color:#60a5fa;'>PySide6</b>  {self._pyside_ver()}<br>"
            f"<b style='color:#60a5fa;'>系统</b>  {platform.system()} {platform.release()} ({platform.machine()})<br>"
            f"<b style='color:#60a5fa;'>解释器</b>  {sys.executable}<br>"
            f"<b style='color:#60a5fa;'>工作目录</b>  {APP_DIR}<br>"
            f"<b style='color:#60a5fa;'>HTML文件</b>  {HTML_FILE}<br>"
            f"<b style='color:#60a5fa;'>设置文件</b>  {SETTINGS_FILE}<br>"
            f"<b style='color:#60a5fa;'>进程PID</b>  {os.getpid()}<br>"
            f"<b style='color:#60a5fa;'>启动时间</b>  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lbl = QLabel(info)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        v.addWidget(lbl)
        v.addStretch()

        btn_reload = QPushButton("🔄 重新加载页面")
        btn_reload.clicked.connect(self._reload_page)
        v.addWidget(btn_reload)
        return w

    def _tab_stats(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        v.addWidget(self.stats_text)
        btn_refresh = QPushButton("🔄 刷新统计")
        btn_refresh.clicked.connect(self._load_stats)
        v.addWidget(btn_refresh)
        return w

    def _tab_console(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)
        hint = QLabel("输入 JavaScript 代码，点击执行：")
        v.addWidget(hint)
        self.js_input = QTextEdit()
        self.js_input.setPlaceholderText("// 例：JSON.stringify(localStorage)")
        self.js_input.setMaximumHeight(100)
        v.addWidget(self.js_input)
        btn_row = QHBoxLayout()
        btn_run = QPushButton("▶ 执行")
        btn_run.clicked.connect(self._run_js)
        btn_row.addWidget(btn_run)
        btn_clear = QPushButton("清空输出")
        btn_clear.clicked.connect(lambda: self.js_output.clear())
        btn_row.addWidget(btn_clear)
        btn_row.addStretch()
        v.addLayout(btn_row)
        self.js_output = QTextEdit()
        self.js_output.setReadOnly(True)
        self.js_output.setPlaceholderText("输出结果...")
        v.addWidget(self.js_output)
        return w

    def _tab_storage(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)
        btn_row = QHBoxLayout()
        btn_load = QPushButton("📂 读取全部 localStorage")
        btn_load.clicked.connect(self._load_storage)
        btn_row.addWidget(btn_load)
        btn_clear_ls = QPushButton("🗑 清空 localStorage")
        btn_clear_ls.setStyleSheet("color: #e17055; border-color: #e17055;")
        btn_clear_ls.clicked.connect(self._clear_storage)
        btn_row.addWidget(btn_clear_ls)
        btn_row.addStretch()
        v.addLayout(btn_row)
        self.storage_text = QTextEdit()
        self.storage_text.setReadOnly(True)
        self.storage_text.setPlaceholderText("点击「读取全部」查看 localStorage 内容...")
        v.addWidget(self.storage_text)
        return w

    def _tab_devset(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        group_pw = QGroupBox("修改开发者密码")
        fl = QFormLayout(group_pw)
        self.new_dev_pw = QLineEdit()
        self.new_dev_pw.setEchoMode(QLineEdit.Password)
        self.new_dev_pw.setPlaceholderText("输入新开发者密码（留空=无密码）")
        fl.addRow("新密码：", self.new_dev_pw)
        btn_change = QPushButton("修改")
        btn_change.clicked.connect(self._change_dev_pw)
        fl.addRow(btn_change)
        v.addWidget(group_pw)
        v.addStretch()
        return w

    def _pyside_ver(self):
        try:
            from PySide6 import __version__ as v
            return v
        except:
            return "未知"

    def _verify(self):
        stored = self.settings.get("dev_password", "")
        entered = self.pw_input.text()
        if stored == "" or entered == stored:
            self.tabs.setEnabled(True)
            self.pw_input.setEnabled(False)
            self._load_stats()
            QMessageBox.information(self, "验证成功", "✅ 开发者权限已开启")
        else:
            QMessageBox.warning(self, "验证失败", "❌ 密码错误")

    def _change_dev_pw(self):
        self.settings["dev_password"] = self.new_dev_pw.text()
        save_settings(self.settings)
        QMessageBox.information(self, "成功", "✅ 开发者密码已修改")

    def _reload_page(self):
        if self.parent_app:
            self.parent_app.main_window.browser.reload()
            QMessageBox.information(self, "已重新加载", "页面正在刷新...")

    def _load_stats(self):
        if not self.parent_app:
            return
        def on_result(result):
            if not result:
                self.stats_text.setPlainText("无法读取数据")
                return
            try:
                data = json.loads(result)
                hws = data.get("hws", [])
                schs = data.get("schs", [])
                subjs = data.get("subjs", [])
                hw_dates = {}
                for h in hws:
                    d = h.get("date", "未知")
                    hw_dates[d] = hw_dates.get(d, 0) + 1
                sch_days = {}
                for s in schs:
                    day = s.get("day", -1)
                    sch_days[day] = sch_days.get(day, 0) + 1
                lines = []
                lines.append("=" * 40)
                lines.append("  数据统计")
                lines.append("=" * 40)
                lines.append("")
                lines.append(f"作业记录总数：{len(hws)}")
                if hw_dates:
                    lines.append("  按日期：")
                    for d in sorted(hw_dates.keys()):
                        lines.append(f"    {d}: {hw_dates[d]} 条")
                lines.append("")
                lines.append(f"课程表条目总数：{len(schs)}")
                if sch_days:
                    lines.append("  按天：")
                    for d in sorted(sch_days.keys()):
                        name = WEEKDAYS[d] if 0 <= d < 7 else f"day={d}"
                        lines.append(f"    {name}: {sch_days[d]} 节")
                lines.append("")
                lines.append(f"科目总数：{len(subjs)}")
                for s in subjs:
                    lines.append(f"    {s.get('name','?')} (id={s.get('id','?')}, color={s.get('color','?')})")
                raw = result.encode('utf-8')
                lines.append("")
                lines.append(f"数据JSON大小：{len(raw)} bytes ({len(raw)/1024:.1f} KB)")
                self.stats_text.setPlainText("\n".join(lines))
            except Exception as e:
                self.stats_text.setPlainText(f"解析错误：{e}")

        self.parent_app.main_window.run_js(
            "JSON.stringify({hws: JSON.parse(localStorage.getItem('ch_hw')||'[]'), schs: JSON.parse(localStorage.getItem('ch_sch')||'[]'), subjs: JSON.parse(localStorage.getItem('ch_subj')||'[]')})",
            on_result
        )

    def _run_js(self):
        code = self.js_input.toPlainText().strip()
        if not code or not self.parent_app:
            return
        self.js_output.append(f"<span style='color:#60a5fa;'>&gt; {code}</span>")
        def on_result(result):
            if result is None:
                self.js_output.append("<span style='color:#636e72;'>(undefined / no return)</span>")
            else:
                displayed = str(result)
                if len(displayed) > 5000:
                    displayed = displayed[:5000] + "\n... (truncated)"
                self.js_output.append(f"<span style='color:#00cec9;'>{displayed}</span>")
        self.parent_app.main_window.run_js(code, on_result)

    def _load_storage(self):
        if not self.parent_app:
            return
        js = """
        (function() {
            var items = {};
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                items[key] = localStorage.getItem(key);
            }
            return JSON.stringify(items, null, 2);
        })()
        """
        def on_result(result):
            if not result:
                self.storage_text.setPlainText("localStorage 为空或读取失败")
                return
            self.storage_text.setPlainText(result)
        self.parent_app.main_window.run_js(js, on_result)

    def _clear_storage(self):
        reply = QMessageBox.question(
            self, "确认清空",
            "⚠️ 这将清空所有 localStorage 数据！\n\n确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.parent_app:
            self.parent_app.main_window.run_js("localStorage.clear(); location.reload();")
            QMessageBox.information(self, "已清空", "localStorage 已清空，页面将刷新")


# ============================================================
# 实用工具 - 关机控制 / 提醒 / 备忘录
# ============================================================
UTILITY_STYLE = """
QDialog { background: #14142a; }
QGroupBox {
    color: #60a5fa; font-size: 12px; font-weight: 600;
    border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 12px;
    margin-top: 14px;
    padding: 20px 14px 14px 14px;
    background: rgba(22, 26, 48, 0.5);
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 8px;
}
QLabel { color: #dfe6e9; font-size: 12px; background: transparent; border: none; }
QTextEdit {
    background: #16162e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.10);
    border-radius: 8px; padding: 10px;
    selection-background-color: rgba(59, 130, 246, 0.4);
}
QTextEdit:focus { border-color: rgba(59, 130, 246, 0.5); }
QLineEdit {
    background: #16162e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 8px; padding: 8px 12px;
}
QLineEdit:focus { border-color: #3b82f6; }
QSpinBox, QDateTimeEdit {
    background: #16162e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 8px; padding: 6px 10px;
}
QSpinBox:focus, QDateTimeEdit:focus { border-color: #3b82f6; }
QPushButton {
    background: rgba(59, 130, 246, 0.10); color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.22);
    border-radius: 8px; padding: 8px 18px; font-size: 12px;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QPushButton:hover { background: #3b82f6; color: #fff; border-color: #3b82f6; }
QPushButton:pressed { background: #2563eb; }
QPushButton:disabled { background: #1a1a2e; color: #636e72; border-color: #2d2d4a; }
QPushButton[danger="true"] {
    background: rgba(225, 112, 85, 0.10); color: #e17055;
    border: 1px solid rgba(225, 112, 85, 0.28);
}
QPushButton[danger="true"]:hover { background: #e17055; color: #fff; border-color: #e17055; }
QPushButton[primary="true"] {
    background: #3b82f6; color: #fff; border: none; font-weight: 600;
}
QPushButton[primary="true"]:hover { background: #60a5fa; }
QPushButton[primary="true"]:pressed { background: #2563eb; }
QTabWidget::pane {
    border: none;
    border-top: 1px solid rgba(59, 130, 246, 0.10);
    background: transparent;
}
QTabBar::tab {
    background: transparent; color: #636e72;
    padding: 10px 24px; margin-right: 4px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QTabBar::tab:selected {
    background: transparent; color: #60a5fa;
    border: none;
    border-bottom: 2px solid #3b82f6;
}
QTabBar::tab:hover:!selected { color: #60a5fa; border-bottom: 2px solid rgba(59, 130, 246, 0.3); }
QListWidget {
    background: #16162e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(59, 130, 246, 0.10);
    border-radius: 8px; padding: 6px;
    outline: none;
}
QListWidget::item { padding: 8px 10px; border-radius: 6px; }
QListWidget::item:selected { background: rgba(59, 130, 246, 0.22); color: #fff; }
QListWidget::item:hover { background: rgba(59, 130, 246, 0.10); }
QCheckBox { color: #dfe6e9; font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(59, 130, 246, 0.25);
    background: #16162e;
}
QCheckBox::indicator:checked {
    background: #3b82f6; border-color: #3b82f6;
}
QComboBox {
    background: #16162e; color: #dfe6e9;
    border: 1px solid rgba(59, 130, 246, 0.12);
    border-radius: 8px; padding: 6px 12px;
}
QComboBox:focus { border-color: #3b82f6; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: #16162e; color: #dfe6e9;
    border: 1px solid rgba(59, 130, 246, 0.2);
    border-radius: 6px; padding: 4px;
    selection-background-color: rgba(59, 130, 246, 0.35);
    outline: none;
}
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(59, 130, 246, 0.25); border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: rgba(59, 130, 246, 0.4); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMenu {
    background: #16162e; color: #dfe6e9;
    border: 1px solid rgba(59, 130, 246, 0.15);
    border-radius: 8px; padding: 6px;
    font-size: 12px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QMenu::item { padding: 6px 24px 6px 14px; border-radius: 6px; }
QMenu::item:selected { background: rgba(59, 130, 246, 0.25); color: #fff; }
QMenu::separator { height: 1px; background: rgba(59, 130, 246, 0.12); margin: 4px 8px; }
"""

REPEAT_OPTIONS = ["不重复", "每天", "每周", "工作日(周一至周五)"]


class PowerTab(QWidget):
    """关机控制 Tab：立即关机 / 定时关机 / 重启 / 取消关机"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- 立即操作 ---
        grp_now = QGroupBox("立即操作")
        gl_now = QVBoxLayout(grp_now)
        gl_now.setSpacing(8)
        hint_now = QLabel("选择下方操作将立即执行（关机/重启会在 30 秒后生效，期间可取消）")
        hint_now.setStyleSheet("color: #636e72; font-size: 11px;")
        hint_now.setWordWrap(True)
        gl_now.addWidget(hint_now)
        row_now = QHBoxLayout()
        row_now.setSpacing(10)
        btn_off = QPushButton("⏻ 立即关机")
        btn_off.setProperty("danger", True)
        btn_off.clicked.connect(lambda: self._shutdown(0))
        row_now.addWidget(btn_off)
        btn_reboot = QPushButton("🔄 立即重启")
        btn_reboot.setProperty("danger", True)
        btn_reboot.clicked.connect(lambda: self._reboot(0))
        row_now.addWidget(btn_reboot)
        btn_cancel = QPushButton("✖ 取消关机/重启")
        btn_cancel.setProperty("primary", True)
        btn_cancel.clicked.connect(self._cancel_shutdown)
        row_now.addWidget(btn_cancel)
        gl_now.addLayout(row_now)
        layout.addWidget(grp_now)

        # --- 定时关机 ---
        grp_timer = QGroupBox("定时关机")
        gl_timer = QVBoxLayout(grp_timer)
        gl_timer.setSpacing(8)

        row_delay = QHBoxLayout()
        row_delay.addWidget(QLabel("延迟："))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(1, 1440)
        self.spin_min.setValue(30)
        self.spin_min.setSuffix(" 分钟")
        row_delay.addWidget(self.spin_min, 1)
        gl_timer.addLayout(row_delay)

        row_btns = QHBoxLayout()
        btn_delay_off = QPushButton("⏲ 定时关机")
        btn_delay_off.setProperty("primary", True)
        btn_delay_off.clicked.connect(self._delayed_shutdown)
        row_btns.addWidget(btn_delay_off)
        btn_delay_reboot = QPushButton("⏲ 定时重启")
        btn_delay_reboot.clicked.connect(self._delayed_reboot)
        row_btns.addWidget(btn_delay_reboot)
        gl_timer.addLayout(row_btns)

        layout.addWidget(grp_timer)

        # --- 指定时刻关机 ---
        grp_at = QGroupBox("指定时刻关机")
        gl_at = QVBoxLayout(grp_at)
        gl_at.setSpacing(8)
        row_at = QHBoxLayout()
        row_at.addWidget(QLabel("在今天："))
        self.spin_hour = QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setSuffix(" 时")
        now_h = datetime.now().hour
        self.spin_hour.setValue((now_h + 1) % 24)
        row_at.addWidget(self.spin_hour)
        self.spin_min_at = QSpinBox()
        self.spin_min_at.setRange(0, 59)
        self.spin_min_at.setSuffix(" 分")
        self.spin_min_at.setValue(0)
        row_at.addWidget(self.spin_min_at)
        row_at.addStretch()
        gl_at.addLayout(row_at)
        btn_at_off = QPushButton("📅 设置到点关机")
        btn_at_off.setProperty("primary", True)
        btn_at_off.clicked.connect(self._at_time_shutdown)
        gl_at.addWidget(btn_at_off)

        layout.addWidget(grp_at)
        layout.addStretch()

        # --- 状态提示 ---
        self.lbl_status = QLabel("")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("""
            font-size: 12px; color: #06b6d4;
            background: rgba(6,182,212,0.08);
            border: 1px solid rgba(6,182,212,0.2);
            border-radius: 8px; padding: 8px 12px;
        """)
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

    def _set_status(self, msg, ok=True):
        if ok:
            self.lbl_status.setStyleSheet("""
                font-size: 12px; color: #06b6d4;
                background: rgba(6,182,212,0.08);
                border: 1px solid rgba(6,182,212,0.2);
                border-radius: 8px; padding: 8px 12px;
            """)
        else:
            self.lbl_status.setStyleSheet("""
                font-size: 12px; color: #e17055;
                background: rgba(225,112,85,0.08);
                border: 1px solid rgba(225,112,85,0.2);
                border-radius: 8px; padding: 8px 12px;
            """)
        self.lbl_status.setText(msg)
        self.lbl_status.setVisible(True)

    def _confirm(self, title, text):
        reply = QMessageBox.question(
            self, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return reply == QMessageBox.Yes

    def _shutdown(self, delay_seconds):
        if delay_seconds < 30 and not self._confirm(
            "确认关机",
            f"⚠️ 即将在 {max(delay_seconds,30)} 秒后关闭计算机！\n\n确定要继续吗？"
        ):
            return
        actual = max(delay_seconds, 30)
        try:
            subprocess.run(
                ["shutdown", "/s", "/t", str(actual)],
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self._set_status(f"✅ 已计划关机：{actual} 秒后执行\n可用「取消关机」撤销。")
        except Exception as e:
            self._set_status(f"❌ 关机命令执行失败：{e}", ok=False)

    def _reboot(self, delay_seconds):
        if delay_seconds < 30 and not self._confirm(
            "确认重启",
            f"⚠️ 即将在 {max(delay_seconds,30)} 秒后重启计算机！\n\n确定要继续吗？"
        ):
            return
        actual = max(delay_seconds, 30)
        try:
            subprocess.run(
                ["shutdown", "/r", "/t", str(actual)],
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self._set_status(f"✅ 已计划重启：{actual} 秒后执行\n可用「取消关机」撤销。")
        except Exception as e:
            self._set_status(f"❌ 重启命令执行失败：{e}", ok=False)

    def _cancel_shutdown(self):
        try:
            subprocess.run(
                ["shutdown", "/a"],
                creationflags=subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            )
            self._set_status("✅ 已尝试取消关机/重启计划")
        except Exception as e:
            self._set_status(f"❌ 取消命令执行失败：{e}", ok=False)

    def _delayed_shutdown(self):
        secs = self.spin_min.value() * 60
        self._shutdown(secs)

    def _delayed_reboot(self):
        secs = self.spin_min.value() * 60
        self._reboot(secs)

    def _at_time_shutdown(self):
        now = datetime.now()
        target = now.replace(
            hour=self.spin_hour.value(),
            minute=self.spin_min_at.value(),
            second=0, microsecond=0
        )
        if target <= now:
            target = target + timedelta(days=1)
        diff = int((target - now).total_seconds())
        if diff < 30:
            self._set_status("⚠️ 距离目标时间不足 30 秒，请选择更晚的时刻", ok=False)
            return
        self._shutdown(diff)


class ReminderTab(QWidget):
    """提醒 Tab：添加/删除/启用-禁用提醒"""

    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- 新增提醒 ---
        grp_add = QGroupBox("新增提醒")
        gl_add = QVBoxLayout(grp_add)
        gl_add.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("标题："))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：该交数学作业了")
        row1.addWidget(self.title_input, 2)
        gl_add.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("时间："))
        self.dt_input = QDateTimeEdit()
        self.dt_input.setDateTime(QDateTime.currentDateTime().addSecs(60 * 30))
        self.dt_input.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.dt_input.setCalendarPopup(True)
        row2.addWidget(self.dt_input, 2)
        row2.addWidget(QLabel("重复："))
        self.repeat_combo = QComboBox()
        self.repeat_combo.addItems(REPEAT_OPTIONS)
        row2.addWidget(self.repeat_combo, 1)
        gl_add.addLayout(row2)

        btn_add = QPushButton("➕ 添加提醒")
        btn_add.setProperty("primary", True)
        btn_add.clicked.connect(self._add_reminder)
        gl_add.addWidget(btn_add)

        layout.addWidget(grp_add)

        # --- 提醒列表 ---
        grp_list = QGroupBox(f"已有提醒（双击编辑标题，右键删除）")
        self.list_group = grp_list
        gl_list = QVBoxLayout(grp_list)
        gl_list.setSpacing(6)
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(False)
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.itemDoubleClicked.connect(self._edit_item)
        gl_list.addWidget(self.list_widget)

        row_btns = QHBoxLayout()
        btn_toggle = QPushButton("✔ 启用/禁用选中")
        btn_toggle.clicked.connect(self._toggle_selected)
        row_btns.addWidget(btn_toggle)
        btn_del = QPushButton("🗑 删除选中")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(self._delete_selected)
        row_btns.addWidget(btn_del)
        btn_clear_all = QPushButton("🧹 清空全部")
        btn_clear_all.clicked.connect(self._clear_all)
        row_btns.addWidget(btn_clear_all)
        layout.addLayout(row_btns)
        layout.addWidget(grp_list, 1)

        layout.addStretch()

    def _refresh_list(self):
        self.list_widget.clear()
        reminders = self.settings.get("reminders", [])
        if not reminders:
            item = QListWidgetItem("（暂无提醒，请在上方添加）")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor("#636e72"))
            self.list_widget.addItem(item)
            self.list_group.setTitle("已有提醒")
            return
        self.list_group.setTitle(f"已有提醒（共 {len(reminders)} 条）")
        for r in reminders:
            enabled = r.get("enabled", True)
            prefix = "🟢" if enabled else "⚪"
            title = r.get("title", "（无标题）")
            dt_str = r.get("datetime", "?")
            repeat = r.get("repeat", "不重复")
            try:
                dt = datetime.fromisoformat(dt_str)
                dt_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            text = f"{prefix}  {dt_str}  ·  {repeat}  ·  {title}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, r.get("id"))
            self.list_widget.addItem(item)

    def _add_reminder(self):
        title = self.title_input.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "请输入提醒标题")
            return
        dt = self.dt_input.dateTime().toPython()
        repeat = self.repeat_combo.currentText()
        reminder = {
            "id": uuid.uuid4().hex[:8],
            "title": title,
            "datetime": dt.isoformat(),
            "repeat": repeat,
            "enabled": True,
            "last_triggered": "",
        }
        self.settings.setdefault("reminders", []).append(reminder)
        save_settings(self.settings)
        self.title_input.clear()
        self._refresh_list()
        QMessageBox.information(self, "已添加", f"✅ 提醒已添加：\n{title}")

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item:
            return
        rid = item.data(Qt.UserRole)
        if not rid:
            return
        menu = QMenu(self)
        act_edit = menu.addAction("✏️ 编辑标题")
        act_toggle = menu.addAction("✔ 启用/禁用")
        menu.addSeparator()
        act_del = menu.addAction("🗑 删除")
        action = menu.exec(self.list_widget.mapToGlobal(pos))
        if action == act_edit:
            self._edit_item(item)
        elif action == act_toggle:
            self._toggle_id(rid)
        elif action == act_del:
            self._delete_id(rid)

    def _edit_item(self, item):
        rid = item.data(Qt.UserRole)
        if not rid:
            return
        reminders = self.settings.get("reminders", [])
        for r in reminders:
            if r.get("id") == rid:
                new_title, ok = QInputDialog.getText(
                    self, "编辑标题", "新的标题：", text=r.get("title", "")
                )
                if ok and new_title.strip():
                    r["title"] = new_title.strip()
                    save_settings(self.settings)
                    self._refresh_list()
                return

    def _toggle_id(self, rid):
        for r in self.settings.get("reminders", []):
            if r.get("id") == rid:
                r["enabled"] = not r.get("enabled", True)
                save_settings(self.settings)
                self._refresh_list()
                return

    def _delete_id(self, rid):
        reply = QMessageBox.question(
            self, "确认删除", "确定删除这条提醒吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.settings["reminders"] = [
            r for r in self.settings.get("reminders", []) if r.get("id") != rid
        ]
        save_settings(self.settings)
        self._refresh_list()

    def _toggle_selected(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先在列表中选择提醒")
            return
        for r in self.settings.get("reminders", []):
            if r.get("id") in ids:
                r["enabled"] = not r.get("enabled", True)
        save_settings(self.settings)
        self._refresh_list()

    def _delete_selected(self):
        ids = self._selected_ids()
        if not ids:
            QMessageBox.information(self, "提示", "请先在列表中选择要删除的提醒")
            return
        reply = QMessageBox.question(
            self, "确认删除", f"确定删除选中的 {len(ids)} 条提醒吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.settings["reminders"] = [
            r for r in self.settings.get("reminders", []) if r.get("id") not in ids
        ]
        save_settings(self.settings)
        self._refresh_list()

    def _clear_all(self):
        if not self.settings.get("reminders"):
            return
        reply = QMessageBox.question(
            self, "确认清空", "⚠️ 将删除所有提醒，确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.settings["reminders"] = []
        save_settings(self.settings)
        self._refresh_list()

    def _selected_ids(self):
        ids = []
        for item in self.list_widget.selectedItems():
            rid = item.data(Qt.UserRole)
            if rid:
                ids.append(rid)
        return ids


class MemoTab(QWidget):
    """备忘录 Tab：增删改查，本地持久化"""

    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        self.current_id = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        # 工具栏
        toolbar = QHBoxLayout()
        btn_new = QPushButton("📝 新建备忘")
        btn_new.setProperty("primary", True)
        btn_new.clicked.connect(self._new_memo)
        toolbar.addWidget(btn_new)
        btn_del = QPushButton("🗑 删除当前")
        btn_del.setProperty("danger", True)
        btn_del.clicked.connect(self._delete_current)
        toolbar.addWidget(btn_del)
        toolbar.addStretch()
        self.lbl_count = QLabel("共 0 条")
        self.lbl_count.setStyleSheet("color: #636e72; font-size: 11px;")
        toolbar.addWidget(self.lbl_count)
        layout.addLayout(toolbar)

        # 主体：左列表 + 右编辑区
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: rgba(59,130,246,0.2); }")

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(220)
        self.list_widget.itemClicked.connect(self._on_select)
        splitter.addWidget(self.list_widget)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(6)
        rl.setContentsMargins(0, 0, 0, 0)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("标题")
        self.title_input.textChanged.connect(self._on_edit_changed)
        rl.addWidget(self.title_input)
        self.content_input = QTextEdit()
        self.content_input.setPlaceholderText("在此输入备忘内容...")
        self.content_input.textChanged.connect(self._on_edit_changed)
        rl.addWidget(self.content_input, 1)
        btn_save = QPushButton("💾 保存")
        btn_save.setProperty("primary", True)
        btn_save.clicked.connect(self._save_current)
        rl.addWidget(btn_save)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #636e72; font-size: 11px;")
        layout.addWidget(self.lbl_status)

    def _refresh_list(self):
        self.list_widget.clear()
        memos = self.settings.get("memos", [])
        self.lbl_count.setText(f"共 {len(memos)} 条")
        if not memos:
            item = QListWidgetItem("（暂无备忘，点击「新建备忘」创建）")
            item.setFlags(Qt.NoItemFlags)
            item.setForeground(QColor("#636e72"))
            self.list_widget.addItem(item)
            return
        # 按更新时间倒序
        memos_sorted = sorted(memos, key=lambda m: m.get("updated_at", ""), reverse=True)
        for m in memos_sorted:
            title = m.get("title", "").strip() or "（无标题）"
            preview = m.get("content", "").strip().replace("\n", " ")[:30]
            text = f"📌 {title}"
            if preview:
                text += f"\n   {preview}{'…' if len(m.get('content','')) > 30 else ''}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, m.get("id"))
            self.list_widget.addItem(item)

    def _on_select(self, item):
        rid = item.data(Qt.UserRole)
        if not rid:
            return
        memo = self._find_memo(rid)
        if not memo:
            return
        self.current_id = rid
        self.title_input.blockSignals(True)
        self.content_input.blockSignals(True)
        self.title_input.setText(memo.get("title", ""))
        self.content_input.setPlainText(memo.get("content", ""))
        self.title_input.blockSignals(False)
        self.content_input.blockSignals(False)
        self.lbl_status.setText(f"正在编辑：{memo.get('title','（无标题）')}")

    def _on_edit_changed(self):
        if self.current_id is None:
            return
        self.lbl_status.setText("● 有未保存的修改")

    def _new_memo(self):
        # 先保存当前（如果有未保存内容则保留为草稿）
        memo = {
            "id": uuid.uuid4().hex[:8],
            "title": "新建备忘",
            "content": "",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.settings.setdefault("memos", []).append(memo)
        save_settings(self.settings)
        self._refresh_list()
        # 选中新创建的
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == memo["id"]:
                self.list_widget.setCurrentItem(item)
                self._on_select(item)
                self.title_input.setFocus()
                self.title_input.selectAll()
                break

    def _save_current(self):
        if self.current_id is None:
            QMessageBox.information(self, "提示", "请先选择或新建一条备忘")
            return
        memo = self._find_memo(self.current_id)
        if not memo:
            return
        memo["title"] = self.title_input.text().strip() or "（无标题）"
        memo["content"] = self.content_input.toPlainText()
        memo["updated_at"] = datetime.now().isoformat()
        save_settings(self.settings)
        self._refresh_list()
        # 重新选中
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.data(Qt.UserRole) == self.current_id:
                self.list_widget.setCurrentItem(item)
                break
        self.lbl_status.setText(f"✅ 已保存：{memo['title']}（{datetime.now().strftime('%H:%M:%S')}）")

    def _delete_current(self):
        if self.current_id is None:
            QMessageBox.information(self, "提示", "请先选择要删除的备忘")
            return
        reply = QMessageBox.question(
            self, "确认删除", "确定删除当前备忘吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.settings["memos"] = [
            m for m in self.settings.get("memos", []) if m.get("id") != self.current_id
        ]
        save_settings(self.settings)
        self.current_id = None
        self.title_input.clear()
        self.content_input.clear()
        self._refresh_list()
        self.lbl_status.setText("已删除")

    def _find_memo(self, rid):
        for m in self.settings.get("memos", []):
            if m.get("id") == rid:
                return m
        return None


# ============================================================
# 联网功能 - 在线更新 / 在线公告 / 云同步(GitHub Gist)
# ============================================================
APP_VERSION = "1.2.3-Beta.1"
GITHUB_API_BASE = "https://api.github.com/gists"


def _parse_version(v):
    """解析版本号 'v1.1.1-Beta.1' -> (1, 1, 1, 'Beta', 1)"""
    v = v.strip().lstrip("vV")
    # 先分离预发布标识
    tag = ""
    main = v
    for sep in ["-", "_", " "]:
        if sep in v:
            idx = v.index(sep)
            main = v[:idx]
            tag = v[idx + 1:]
            break
    parts = main.split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except Exception:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    # 预发布版本号,如 Beta.1 -> ("Beta", 1)
    pre = ""
    pre_num = 0
    if tag:
        tparts = tag.split(".")
        pre = tparts[0] if tparts else ""
        if len(tparts) > 1:
            try:
                pre_num = int(tparts[1])
            except Exception:
                pre_num = 0
    return (nums[0], nums[1], nums[2], pre, pre_num)


def _is_newer(remote, local):
    """比较版本号,remote > local 返回 True"""
    r = _parse_version(remote)
    l = _parse_version(local)
    # 主版本号比较
    if r[:3] != l[:3]:
        return r[:3] > l[:3]
    # 主版本相同,比较预发布
    # 无预发布(正式版) > 有预发布
    if not r[3] and l[3]:
        return True
    if r[3] and not l[3]:
        return False
    if r[3] and l[3]:
        if r[3] != l[3]:
            # 不同预发布类型,按字典序
            return r[3] > l[3]
        return r[4] > l[4]
    return False


def _http_request(url, method="GET", data=None, headers=None, timeout=10, retries=1):
    """
    通用 HTTP 请求封装,返回 (status_code, response_text)。
    使用 urllib 实现,不依赖 requests 库。
    网络层错误（超时/连接失败）会自动重试 retries 次；HTTP 错误码（4xx/5xx）不重试。
    """
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "ClassAssistant/1.1")
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    last_err = ""
    for attempt in range(retries + 1):
        # 注意：urllib 的 Request 对象 urlopen 后不可复用，每次重建
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            # HTTP 错误码（如 401/403/404）不重试，直接返回
            body = ""
            try:
                body = e.read().decode("utf-8")
            except Exception:
                pass
            return e.code, body
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last_err = str(getattr(e, "reason", e))
            if attempt < retries:
                import time as _time
                _time.sleep(1.0)
                continue
            return -1, last_err
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                import time as _time
                _time.sleep(1.0)
                continue
            return -2, last_err
    return -2, last_err


def _friendly_http_error(code, body=""):
    """把 GitHub API 的错误码/响应体转成对用户友好的中文提示"""
    try:
        body_low = (body or "").lower()
    except Exception:
        body_low = ""
    if code == 401:
        return "GitHub Token 无效或已过期，请检查 Token 是否正确、是否已失效"
    if code == 403:
        if "rate limit" in body_low or "ratelimit" in body_low:
            return "GitHub API 调用次数超限（速率限制），请稍后几分钟再试"
        return "无权限访问该资源，请检查 Token 是否勾选了 gist 权限"
    if code == 404:
        return "云端未找到该数据（Gist ID 可能不正确，或 Gist 已被删除）"
    if code in (500, 502, 503):
        return f"GitHub 服务暂时不可用（HTTP {code}），请稍后重试"
    if code == -1:
        return "网络连接失败，请检查网络是否正常后重试"
    if code == -2:
        return "请求异常，请稍后重试"
    return f"GitHub API 返回 {code}"


class NetworkManager(QObject):
    """
    网络功能管理器:
    - 在线更新检查
    - 在线公告拉取
    - GitHub Gist 云同步
    所有网络操作在独立 QThread 中执行,避免阻塞 UI。
    """
    # 信号:任务完成 (task_id, success, result_or_error)
    task_finished = Signal(str, bool, object)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._thread = None
        self._worker = None

    def _ensure_network(self):
        """确保 settings 中有 network 字段"""
        if "network" not in self.settings:
            self.settings["network"] = {}
        return self.settings["network"]

    # ------------------------------------------------------------
    # 在线更新
    # ------------------------------------------------------------
    def check_update_async(self):
        """异步检查更新"""
        net = self._ensure_network()
        url = net.get("update_url", "")
        if not url:
            self.task_finished.emit("update", False, "未配置更新检查 URL")
            return
        self._run_in_thread("update", self._do_check_update, url)

    def _do_check_update(self, url):
        code, body = _http_request(url, timeout=10)
        if code != 200:
            return False, f"HTTP {code}: {body[:200]}"
        try:
            info = json.loads(body)
        except Exception as e:
            return False, f"解析 JSON 失败: {e}"
        latest = info.get("latest_version", "")
        if not latest:
            return False, "未找到 latest_version 字段"
        has_update = _is_newer(latest, APP_VERSION)
        result = {
            "latest_version": latest,
            "current_version": APP_VERSION,
            "has_update": has_update,
            "download_url": info.get("download_url", ""),
            "release_notes": info.get("release_notes", ""),
        }
        return True, result

    # ------------------------------------------------------------
    # 在线公告
    # ------------------------------------------------------------
    def fetch_notices_async(self):
        """异步拉取公告"""
        net = self._ensure_network()
        url = net.get("notice_url", "")
        if not url:
            self.task_finished.emit("notice", False, "未配置公告 URL")
            return
        self._run_in_thread("notice", self._do_fetch_notices, url)

    def _do_fetch_notices(self, url):
        code, body = _http_request(url, timeout=10)
        if code != 200:
            return False, f"HTTP {code}: {body[:200]}"
        try:
            data = json.loads(body)
        except Exception as e:
            return False, f"解析 JSON 失败: {e}"
        notices = data.get("notices", [])
        return True, notices

    # ------------------------------------------------------------
    # 云同步 - GitHub Gist
    # ------------------------------------------------------------
    def sync_to_cloud_async(self, payload):
        """异步上传数据到 Gist"""
        net = self._ensure_network()
        token = net.get("github_token", "")
        if not token:
            self.task_finished.emit("upload", False, "未配置 GitHub Token")
            return
        self._run_in_thread("upload", self._do_sync_to_cloud, token, payload)

    def _do_sync_to_cloud(self, token, payload):
        net = self._ensure_network()
        gist_id = net.get("gist_id", "")
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        body_data = {
            "description": "班级桌面助手 - 云同步数据",
            "files": {
                "class_assistant_data.json": {
                    "content": content
                }
            }
        }
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        if gist_id:
            # 已有 Gist,更新它
            url = f"{GITHUB_API_BASE}/{gist_id}"
            code, body = _http_request(url, method="PATCH", data=body_data,
                                       headers=headers, timeout=20)
        else:
            # 首次使用,创建新 Gist
            body_data["public"] = False
            code, body = _http_request(GITHUB_API_BASE, method="POST",
                                       data=body_data, headers=headers, timeout=20)
        if code not in (200, 201):
            return False, _friendly_http_error(code, body)
        try:
            resp = json.loads(body)
        except Exception:
            return False, "无法解析 GitHub 响应"
        new_gist_id = resp.get("id", "")
        if not gist_id and new_gist_id:
            net["gist_id"] = new_gist_id
            save_settings(self.settings)
        return True, {
            "gist_id": net.get("gist_id", ""),
            "synced_at": datetime.now().isoformat(),
        }

    def sync_from_cloud_async(self):
        """异步从 Gist 下载数据"""
        net = self._ensure_network()
        token = net.get("github_token", "")
        gist_id = net.get("gist_id", "")
        if not token:
            self.task_finished.emit("download", False, "未配置 GitHub Token")
            return
        if not gist_id:
            self.task_finished.emit("download", False, "尚未创建云端数据,请先上传")
            return
        self._run_in_thread("download", self._do_sync_from_cloud, token, gist_id)

    def _do_sync_from_cloud(self, token, gist_id):
        url = f"{GITHUB_API_BASE}/{gist_id}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        code, body = _http_request(url, headers=headers, timeout=20)
        if code != 200:
            return False, _friendly_http_error(code, body)
        try:
            resp = json.loads(body)
        except Exception:
            return False, "无法解析 GitHub 响应"
        files = resp.get("files", {})
        # 读取学生自己的同步数据（备忘录/提醒 + localStorage 课表快照）
        result = {}
        student_file = files.get("class_assistant_data.json", {})
        if student_file.get("raw_url"):
            code2, body2 = _http_request(student_file["raw_url"], timeout=20)
            if code2 == 200:
                try:
                    result = json.loads(body2)
                except Exception as e:
                    return False, f"解析云端数据失败: {e}"
        # 读取教师端上传的课表（teacher_schedule.json）
        teacher_file = files.get("teacher_schedule.json", {})
        if teacher_file.get("raw_url"):
            code3, body3 = _http_request(teacher_file["raw_url"], timeout=20)
            if code3 == 200:
                try:
                    ts = json.loads(body3)
                    if isinstance(ts, dict) and ts.get("export_type") == "teacher_schedule":
                        result["teacher_schedule"] = {
                            "subjects": ts.get("subjects") or ts.get("subjs", []),
                            "schedule": ts.get("schedule") or ts.get("schs", []),
                        }
                except Exception:
                    pass
        if not result:
            return False, "云端数据文件不存在"
        return True, result

    # ------------------------------------------------------------
    # 线程管理
    # ------------------------------------------------------------
    def _run_in_thread(self, task_id, func, *args):
        """在独立线程中运行任务"""
        # 等待上一个线程退出，避免 QThread 析构时仍在运行导致程序崩溃
        if self._thread is not None:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(3000)
            self._thread = None
            self._worker = None
        self._thread = QThread()
        self._worker = _NetworkWorker(task_id, func, *args)
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._on_task_finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()
        # 触发任务执行
        QTimer.singleShot(0, self._worker.run)

    def _on_task_finished(self, task_id, success, result):
        self.task_finished.emit(task_id, success, result)


class _NetworkWorker(QObject):
    """网络任务工作器,在 QThread 中执行"""

    finished = Signal(str, bool, object)

    def __init__(self, task_id, func, *args):
        super().__init__()
        self.task_id = task_id
        self.func = func
        self.args = args

    def run(self):
        try:
            success, result = self.func(*self.args)
        except Exception as e:
            success, result = False, f"内部错误: {e}"
        self.finished.emit(self.task_id, success, result)


class NetworkTab(QWidget):
    """网络功能 Tab:在线更新 / 在线公告 / 云同步"""

    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        if "network" not in self.settings:
            self.settings["network"] = {}
        self.net = self.settings["network"]
        self.nm = NetworkManager(self.settings)
        self.nm.task_finished.connect(self._on_task_finished)
        self._busy = False  # 防止重复点击触发的并发上传标志
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- 在线更新 ---
        grp_update = QGroupBox("🔄 在线更新")
        gl_update = QVBoxLayout(grp_update)
        gl_update.setSpacing(8)

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("更新源："))
        self.update_url_input = QLineEdit()
        self.update_url_input.setPlaceholderText("https://.../version.json")
        self.update_url_input.setText(self.net.get("update_url", ""))
        row_url.addWidget(self.update_url_input, 2)
        gl_update.addLayout(row_url)

        self.chk_auto_update = QCheckBox("启动时自动检查更新")
        self.chk_auto_update.setChecked(self.net.get("auto_check_update", True))
        gl_update.addWidget(self.chk_auto_update)

        row_up = QHBoxLayout()
        btn_save_update = QPushButton("💾 保存设置")
        btn_save_update.clicked.connect(self._save_update_settings)
        row_up.addWidget(btn_save_update)
        btn_check = QPushButton("🔍 立即检查更新")
        btn_check.setProperty("primary", True)
        btn_check.clicked.connect(self._check_update)
        row_up.addWidget(btn_check)
        gl_update.addLayout(row_up)

        self.lbl_update = QLabel(f"当前版本：v{APP_VERSION}")
        self.lbl_update.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_update.setWordWrap(True)
        gl_update.addWidget(self.lbl_update)

        layout.addWidget(grp_update)

        # --- 在线公告 ---
        grp_notice = QGroupBox("📢 在线公告")
        gl_notice = QVBoxLayout(grp_notice)
        gl_notice.setSpacing(8)

        row_nurl = QHBoxLayout()
        row_nurl.addWidget(QLabel("公告源："))
        self.notice_url_input = QLineEdit()
        self.notice_url_input.setPlaceholderText("https://.../notice.json")
        self.notice_url_input.setText(self.net.get("notice_url", ""))
        row_nurl.addWidget(self.notice_url_input, 2)
        gl_notice.addLayout(row_nurl)

        row_n = QHBoxLayout()
        btn_save_notice = QPushButton("💾 保存设置")
        btn_save_notice.clicked.connect(self._save_notice_settings)
        row_n.addWidget(btn_save_notice)
        btn_fetch = QPushButton("📢 拉取公告")
        btn_fetch.setProperty("primary", True)
        btn_fetch.clicked.connect(self._fetch_notices)
        row_n.addWidget(btn_fetch)
        gl_notice.addLayout(row_n)

        self.lbl_notice = QLabel("（点击「拉取公告」获取最新通知）")
        self.lbl_notice.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_notice.setWordWrap(True)
        gl_notice.addWidget(self.lbl_notice)

        layout.addWidget(grp_notice)

        # --- 云同步 ---
        grp_sync = QGroupBox("☁️ 云同步（GitHub Gist）")
        gl_sync = QVBoxLayout(grp_sync)
        gl_sync.setSpacing(8)

        hint = QLabel("在 GitHub 创建 Personal Access Token(勾选 gist 权限)后填入下方。多台电脑用同一个 Token 即可同步。")
        hint.setStyleSheet("color: #636e72; font-size: 11px;")
        hint.setWordWrap(True)
        gl_sync.addWidget(hint)

        row_tok = QHBoxLayout()
        row_tok.addWidget(QLabel("Token："))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxx")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setText(self.net.get("github_token", ""))
        row_tok.addWidget(self.token_input, 2)
        # 显示/隐藏 Token 切换
        self.btn_toggle_token = QPushButton("👁")
        self.btn_toggle_token.setFixedWidth(32)
        self.btn_toggle_token.setCheckable(True)
        self.btn_toggle_token.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_token.setToolTip("按住显示 Token 明文")
        self.btn_toggle_token.pressed.connect(
            lambda: self.token_input.setEchoMode(QLineEdit.Normal))
        self.btn_toggle_token.released.connect(
            lambda: self.token_input.setEchoMode(QLineEdit.Password))
        row_tok.addWidget(self.btn_toggle_token)
        gl_sync.addLayout(row_tok)

        row_gid = QHBoxLayout()
        row_gid.addWidget(QLabel("Gist ID："))
        self.gist_id_input = QLineEdit()
        self.gist_id_input.setPlaceholderText("粘贴教师端上传后生成的 Gist ID（首次自己上传则留空自动创建）")
        self.gist_id_input.setText(self.net.get("gist_id", ""))
        row_gid.addWidget(self.gist_id_input, 2)
        gl_sync.addLayout(row_gid)

        self.chk_auto_sync = QCheckBox("自动云同步（每 30 分钟）")
        self.chk_auto_sync.setChecked(self.net.get("auto_sync", False))
        gl_sync.addWidget(self.chk_auto_sync)

        row_sync = QHBoxLayout()
        btn_save_sync = QPushButton("💾 保存设置")
        btn_save_sync.clicked.connect(self._save_sync_settings)
        row_sync.addWidget(btn_save_sync)
        self.btn_upload = QPushButton("⬆️ 上传到云端")
        self.btn_upload.setProperty("primary", True)
        self.btn_upload.clicked.connect(self._sync_to_cloud)
        row_sync.addWidget(self.btn_upload)
        self.btn_download = QPushButton("⬇️ 从云端下载")
        self.btn_download.setProperty("danger", True)
        self.btn_download.clicked.connect(self._sync_from_cloud)
        row_sync.addWidget(self.btn_download)
        gl_sync.addLayout(row_sync)

        self.lbl_sync = QLabel("（未同步）")
        self.lbl_sync.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_sync.setWordWrap(True)
        gl_sync.addWidget(self.lbl_sync)

        layout.addWidget(grp_sync)
        layout.addStretch()

    def _refresh_status(self):
        last = self.net.get("last_sync_time", "")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                self.lbl_sync.setText(f"上次同步：{dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception:
                self.lbl_sync.setText(f"上次同步：{last}")

    # --- 设置保存 ---
    def _save_update_settings(self):
        self.net["update_url"] = self.update_url_input.text().strip()
        self.net["auto_check_update"] = self.chk_auto_update.isChecked()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "更新设置已保存")

    def _save_notice_settings(self):
        self.net["notice_url"] = self.notice_url_input.text().strip()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "公告设置已保存")

    def _save_sync_settings(self):
        self.net["github_token"] = self.token_input.text().strip()
        self.net["gist_id"] = self.gist_id_input.text().strip()
        self.net["auto_sync"] = self.chk_auto_sync.isChecked()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "云同步设置已保存")

    # --- 操作触发 ---
    def _check_update(self):
        self.net["update_url"] = self.update_url_input.text().strip()
        save_settings(self.settings)
        self.lbl_update.setText("🔍 正在检查更新...")
        self.nm.check_update_async()

    def _fetch_notices(self):
        self.net["notice_url"] = self.notice_url_input.text().strip()
        save_settings(self.settings)
        self.lbl_notice.setText("📢 正在拉取公告...")
        self.nm.fetch_notices_async()

    def _set_busy(self, busy, status_text=None):
        """统一管理同步忙碌状态：标志 + 按钮禁用 + 状态文案"""
        self._busy = busy
        self.btn_upload.setEnabled(not busy)
        self.btn_download.setEnabled(not busy)
        if status_text is not None:
            self.lbl_sync.setText(status_text)

    def _sync_to_cloud(self):
        if self._busy:
            QMessageBox.information(self, "请稍候", "上次同步尚未完成，请稍后再试")
            return
        self.net["github_token"] = self.token_input.text().strip()
        self.net["gist_id"] = self.gist_id_input.text().strip()
        save_settings(self.settings)
        self._set_busy(True, "⬆️ 正在上传到云端...")
        # 收集要同步的数据
        payload = self._collect_payload()
        # 只触发一次上传：有主窗口则先异步导出 localStorage 再上传；否则立即上传
        if self.parent_app and self.parent_app.main_window:
            QTimer.singleShot(0, lambda: self._export_localstorage_async(payload))
        else:
            self.nm.sync_to_cloud_async(payload)

    def _sync_from_cloud(self):
        if self._busy:
            QMessageBox.information(self, "请稍候", "上次同步尚未完成，请稍后再试")
            return
        reply = QMessageBox.question(
            self, "确认下载",
            "⚠️ 从云端下载会覆盖本地的备忘录、提醒和课表数据。\n\n确定继续吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        self.net["github_token"] = self.token_input.text().strip()
        self.net["gist_id"] = self.gist_id_input.text().strip()
        save_settings(self.settings)
        self._set_busy(True, "⬇️ 正在从云端下载...")
        self.nm.sync_from_cloud_async()

    def _collect_payload(self):
        """收集本地数据用于上传"""
        return {
            "version": APP_VERSION,
            "uploaded_at": datetime.now().isoformat(),
            "settings": {
                "memos": self.settings.get("memos", []),
                "reminders": self.settings.get("reminders", []),
            },
            "schedule": None,  # 课表数据通过 JS 从 localStorage 导出后填充
        }

    def _export_localstorage_async(self, payload):
        """异步从 localStorage 导出课表数据，完成后只触发一次上传"""
        if not self.parent_app or not self.parent_app.main_window:
            self.nm.sync_to_cloud_async(payload)
            return
        js = "JSON.stringify(Object.keys(localStorage).reduce((o,k)=>(o[k]=localStorage.getItem(k),o),{}))"
        mw = self.parent_app.main_window
        try:
            mw.browser.page().runJavaScript(
                js, 0, lambda result: self._on_localstorage_exported(payload, result)
            )
        except Exception:
            # 导出失败，直接上传已有数据
            self.nm.sync_to_cloud_async(payload)

    def _on_localstorage_exported(self, payload, result):
        if result:
            try:
                payload["schedule"] = json.loads(result) if isinstance(result, str) else result
            except Exception:
                payload["schedule"] = str(result)
        self.nm.sync_to_cloud_async(payload)

    # --- 任务完成回调 ---
    def _on_task_finished(self, task_id, success, result):
        if task_id == "update":
            self._handle_update_result(success, result)
        elif task_id == "notice":
            self._handle_notice_result(success, result)
        elif task_id == "upload":
            self._handle_upload_result(success, result)
        elif task_id == "download":
            self._handle_download_result(success, result)

    def _handle_update_result(self, success, result):
        if not success:
            self.lbl_update.setText(f"❌ 检查失败：{result}")
            return
        info = result
        if info["has_update"]:
            msg = (
                f"🎉 发现新版本！\n\n"
                f"当前版本：v{info['current_version']}\n"
                f"最新版本：v{info['latest_version']}\n\n"
                f"更新内容：\n{info.get('release_notes','（无')}\n\n"
                f"下载地址：\n{info.get('download_url','（无')}"
            )
            self.lbl_update.setText(f"🎉 有新版本：v{info['latest_version']}")
            QMessageBox.information(self, "发现新版本", msg)
        else:
            self.lbl_update.setText(f"✅ 已是最新版本（v{info['current_version']}）")
            QMessageBox.information(self, "无需更新", "当前已是最新版本。")

    def _handle_notice_result(self, success, result):
        if not success:
            self.lbl_notice.setText(f"❌ 拉取失败：{result}")
            return
        notices = result or []
        if not notices:
            self.lbl_notice.setText("（暂无公告）")
            QMessageBox.information(self, "公告", "暂无公告")
            return
        self.lbl_notice.setText(f"📢 获取到 {len(notices)} 条公告")
        # 显示公告详情
        seen = self.net.get("seen_notice_ids", [])
        new_count = sum(1 for n in notices if n.get("id") not in seen)
        text_parts = []
        for n in notices:
            nid = n.get("id", "")
            title = n.get("title", "（无标题）")
            content = n.get("content", "")
            pub = n.get("published_at", "")
            level = n.get("level", "info")
            icon = {"info": "ℹ️", "warning": "⚠️", "important": "❗"}.get(level, "ℹ️")
            text_parts.append(f"{icon} 【{title}】（{pub}）\n{content}")
        full_text = "\n\n".join(text_parts)
        QMessageBox.information(self, f"📢 在线公告（共 {len(notices)} 条，新 {new_count} 条）", full_text)
        # 标记为已读
        all_ids = [n.get("id", "") for n in notices if n.get("id")]
        self.net["seen_notice_ids"] = all_ids
        save_settings(self.settings)

    def _handle_upload_result(self, success, result):
        self._set_busy(False)
        if not success:
            self.lbl_sync.setText(f"❌ 上传失败：{result}")
            QMessageBox.warning(self, "上传失败", str(result))
            return
        self.net["last_sync_time"] = datetime.now().isoformat()
        if "gist_id" in result:
            self.net["gist_id"] = result["gist_id"]
            self.gist_id_input.setText(result["gist_id"])
        save_settings(self.settings)
        self._refresh_status()
        QMessageBox.information(self, "上传成功", "✅ 数据已同步到云端")

    def _handle_download_result(self, success, result):
        self._set_busy(False)
        if not success:
            self.lbl_sync.setText(f"❌ 下载失败：{result}")
            QMessageBox.warning(self, "下载失败", str(result))
            return
        # 应用云端数据
        if not isinstance(result, dict):
            QMessageBox.warning(self, "下载失败", "云端数据格式无效")
            return
        cloud_settings = result.get("settings", {})
        if "memos" in cloud_settings:
            self.settings["memos"] = cloud_settings["memos"]
        if "reminders" in cloud_settings:
            self.settings["reminders"] = cloud_settings["reminders"]
        save_settings(self.settings)
        self.net["last_sync_time"] = datetime.now().isoformat()
        save_settings(self.settings)
        self._refresh_status()
        # 优先应用教师端上传的课表（写入 ch_subj / ch_sch）
        teacher_sched = result.get("teacher_schedule")
        applied_teacher = False
        if teacher_sched and self.parent_app and self.parent_app.main_window:
            applied_teacher = self._restore_teacher_schedule(
                teacher_sched.get("subjects", []), teacher_sched.get("schedule", []))
        # 否则恢复学生自己上传的 localStorage 快照（含课表等所有键）
        if not applied_teacher:
            schedule = result.get("schedule")
            if schedule and self.parent_app and self.parent_app.main_window:
                self._restore_localstorage(schedule)
        msg = "✅ 已从云端恢复数据\n\n"
        if applied_teacher:
            msg += "📚 已接收教师端新课表（科目/课程已更新）\n\n"
        msg += "（备忘录和提醒已更新,课表数据将在页面刷新后生效）"
        QMessageBox.information(self, "下载成功", msg)

    def _restore_localstorage(self, schedule_data):
        """恢复 localStorage 数据"""
        if not self.parent_app or not self.parent_app.main_window:
            return
        if isinstance(schedule_data, str):
            try:
                schedule_data = json.loads(schedule_data)
            except Exception:
                return
        if not isinstance(schedule_data, dict):
            return
        # 清空并恢复 localStorage
        js_lines = ["localStorage.clear();"]
        for k, v in schedule_data.items():
            v_escaped = json.dumps(str(v), ensure_ascii=False)
            js_lines.append(f"localStorage.setItem({json.dumps(k, ensure_ascii=False)}, {v_escaped});")
        js_lines.append("location.reload();")
        js = "\n".join(js_lines)
        try:
            self.parent_app.main_window.browser.page().runJavaScript(js)
        except Exception as e:
            print(f"恢复 localStorage 失败: {e}")

    def _restore_teacher_schedule(self, subjects, schedule):
        """应用教师端上传的课表：写入 localStorage 的 ch_subj / ch_sch 后刷新页面"""
        if not self.parent_app or not self.parent_app.main_window:
            return False
        if not subjects and not schedule:
            return False
        # 与「导入教师课表」功能保持一致：科目写 ch_subj，课程写 ch_sch
        subjs_js = json.dumps(subjects if subjects else [], ensure_ascii=False)
        schs_js = json.dumps(schedule if schedule else [], ensure_ascii=False)
        js = (
            "localStorage.setItem('ch_subj', JSON.stringify(" + subjs_js + "));"
            "localStorage.setItem('ch_sch', JSON.stringify(" + schs_js + "));"
            "location.reload();"
        )
        try:
            self.parent_app.main_window.browser.page().runJavaScript(js)
            return True
        except Exception as e:
            print(f"恢复教师课表失败: {e}")
            return False


class UtilityDialog(QDialog):
    """实用工具容器：关机控制 / 提醒 / 备忘录 / 网络"""

    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        self.setWindowTitle("🧰 实用工具")
        self.setFixedSize(640, 620)
        self.setStyleSheet(UTILITY_STYLE)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🧰 实用工具")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #60a5fa;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(PowerTab(), "⏻ 关机控制")
        self.tabs.addTab(ReminderTab(self.settings, app=self.parent_app), "⏰ 提醒")
        self.tabs.addTab(MemoTab(self.settings, app=self.parent_app), "📝 备忘录")
        self.tabs.addTab(NetworkTab(self.settings, app=self.parent_app), "🌐 网络")
        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


# ============================================================
# 主窗口（嵌入 HTML）
# ============================================================
class MainWindow(QMainWindow):
    close_requested = Signal()
    settings_requested = Signal()
    admin_requested = Signal()
    dev_requested = Signal()
    about_requested = Signal()
    import_requested = Signal()
    utility_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("班级桌面助手 v1.2.3-Beta.1 - 学生端")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        if os.path.exists(STUDENT_ICO):
            self.setWindowIcon(QIcon(STUDENT_ICO))

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl.fromLocalFile(HTML_FILE))
        self.setCentralWidget(self.browser)

        self._page_loaded = False
        self.browser.loadFinished.connect(self._on_load)

        self._build_menubar()

    def _build_menubar(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)
        menubar.setStyleSheet("""
            QMenuBar {
                background: #14142a;
                color: #60a5fa;
                padding: 0px; margin: 0px; spacing: 2px;
                font-size: 13px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
                border-bottom: 1px solid rgba(59, 130, 246, 0.10);
            }
            QMenuBar::item {
                background: transparent; color: #60a5fa;
                padding: 8px 18px; border-radius: 0px; margin: 0px;
            }
            QMenuBar::item:selected { background: rgba(59, 130, 246, 0.15); color: #fff; }
            QMenuBar::item:pressed { background: rgba(59, 130, 246, 0.28); color: #fff; }
            QMenu {
                background: #16162e;
                border: 1px solid rgba(59, 130, 246, 0.18);
                border-radius: 10px; padding: 6px;
                font-size: 13px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
            }
            QMenu::item { padding: 8px 28px 8px 16px; border-radius: 6px; color: #dfe6e9; }
            QMenu::item:selected { background: rgba(59, 130, 246, 0.22); color: #fff; }
            QMenu::separator { height: 1px; background: rgba(59, 130, 246, 0.12); margin: 4px 8px; }
        """)

        # --- 课表菜单 ---
        menu_sch = menubar.addMenu("课表")
        act_import = QAction("📥 导入教师课表", self)
        act_import.triggered.connect(self.import_requested.emit)
        menu_sch.addAction(act_import)

        # --- 设置菜单 ---
        menu_set = menubar.addMenu("设置")
        act_settings = QAction("⚙️ 普通设置", self)
        act_settings.triggered.connect(self.settings_requested.emit)
        menu_set.addAction(act_settings)

        act_admin = QAction("🔐 管理员", self)
        act_admin.triggered.connect(self.admin_requested.emit)
        menu_set.addAction(act_admin)

        act_dev = QAction("🛠 开发者工具", self)
        act_dev.triggered.connect(self.dev_requested.emit)
        menu_set.addAction(act_dev)

        # --- 实用工具菜单 ---
        menu_util = menubar.addMenu("实用工具")
        act_util = QAction("🧰 关机 / 提醒 / 备忘录", self)
        act_util.triggered.connect(self.utility_requested.emit)
        menu_util.addAction(act_util)

        # --- 关于菜单 ---
        menu_about = menubar.addMenu("关于")
        act_about = QAction("ℹ️ 关于班级桌面助手", self)
        act_about.triggered.connect(self.about_requested.emit)
        menu_about.addAction(act_about)

    def _on_load(self, ok):
        self._page_loaded = ok

    def run_js(self, code, callback=None):
        if self._page_loaded:
            if callback:
                self.browser.page().runJavaScript(code, callback)
            else:
                self.browser.page().runJavaScript(code)
        elif callback:
            callback(None)

    def closeEvent(self, e):
        self.close_requested.emit()
        e.ignore()


# ============================================================
# 启动动画（Splash）
# ============================================================
class SplashWidget(QWidget):
    """深色主题启动动画：渐变背景 + 旋转加载环 + 淡入淡出"""

    def __init__(self, app_name="班级桌面助手", version="v1.2.3-Beta.1",
                 subtitle="正在加载...", parent=None):
        super().__init__(parent)
        self._app_name = app_name
        self._version = version
        self._subtitle = subtitle
        self._angle = 0
        self._dot_offset = 0
        self._step = 0

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(420, 260)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._on_tick)
        self._anim_timer.start(30)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setDuration(280)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.OutCubic)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setDuration(260)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out.finished.connect(self.close)

    def show_splash(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2
            )
        self._fade_in.stop()
        self.setWindowOpacity(0.0)
        self.show()
        self._fade_in.start()

    def close_splash(self):
        self._anim_timer.stop()
        self._fade_in.stop()
        self._fade_out.stop()
        if self.windowOpacity() < 0.1:
            self.close()
        else:
            self._fade_out.start()

    def set_subtitle(self, text):
        self._subtitle = text
        self.update()

    def _on_tick(self):
        self._angle = (self._angle + 8) % 360
        self._dot_offset = (self._dot_offset + 1) % 40
        self._step = (self._step + 1) % 100
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)

        # 外圆角卡片
        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = 20
        path = self._rounded_rect_path(rect, radius)

        # 背景渐变
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor("#1a1a3a"))
        grad.setColorAt(0.5, QColor("#16162e"))
        grad.setColorAt(1.0, QColor("#0f0f25"))
        p.fillPath(path, QBrush(grad))

        # 边框
        pen = QPen(QColor(59, 130, 246, 60), 1.2)
        p.setPen(pen)
        p.drawPath(path)

        # 光晕（顶部）
        glow = QLinearGradient(rect.topLeft(), QPoint(rect.width(), 0))
        glow.setColorAt(0.0, QColor(96, 165, 250, 0))
        glow.setColorAt(0.5, QColor(96, 165, 250, 25))
        glow.setColorAt(1.0, QColor(96, 165, 250, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRect(rect.adjusted(0, 0, 0, -(rect.height() - 3)))

        # 旋转加载环
        cx, cy = rect.width() // 2, 120
        outer_r = 38
        inner_r = 28

        # 外环底圈
        pen_bg = QPen(QColor(59, 130, 246, 25), 4)
        p.setPen(pen_bg)
        p.drawEllipse(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)

        # 旋转弧
        pen_fg = QPen(QColor(96, 165, 250, 230), 4, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen_fg)
        span = 30 * 16
        start = (self._angle * 16) % 360 * 16
        p.drawArc(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2, -start, span)

        # 内层反向小环
        pen_inner = QPen(QColor(129, 140, 248, 140), 2)
        p.setPen(pen_inner)
        span2 = 20 * 16
        start2 = ((360 - self._angle * 1.5) * 16) % 360 * 16
        p.drawArc(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2, -start2, span2)

        # 中心圆点脉动
        pulse = 4 + (self._step % 20) * 0.25
        dot_alpha = 200 - (self._step % 20) * 8
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(96, 165, 250, max(30, dot_alpha))))
        p.drawEllipse(cx - pulse / 2, cy - pulse / 2, pulse, pulse)

        # 标题
        p.setPen(QPen(QColor("#e2e8f0")))
        title_font = QFont("Microsoft YaHei UI", 15, QFont.Bold)
        p.setFont(title_font)
        p.drawText(QRect(0, 175, rect.width(), 28), Qt.AlignCenter, self._app_name)

        # 版本
        p.setPen(QPen(QColor(96, 165, 250, 180)))
        ver_font = QFont("Microsoft YaHei UI", 8)
        p.setFont(ver_font)
        p.drawText(QRect(0, 205, rect.width(), 16), Qt.AlignCenter, self._version)

        # 副标题（加载进度文字）
        p.setPen(QPen(QColor(148, 163, 186, 200)))
        sub_font = QFont("Microsoft YaHei UI", 9)
        p.setFont(sub_font)
        dots = "." * ((self._dot_offset // 10) + 1)
        p.drawText(
            QRect(0, 230, rect.width(), 20),
            Qt.AlignCenter,
            self._subtitle + dots
        )

    def _rounded_rect_path(self, rect, radius):
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        return path


# ============================================================
# 主应用
# ============================================================
class ClassAssistantApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # 全局默认字体
        font = QFont("Microsoft YaHei UI", 9)
        font.setStyleHint(QFont.SansSerif)
        self.app.setFont(font)

        self.settings = load_settings()

        # 显示启动动画
        self.splash = SplashWidget("班级桌面助手", "v1.2.3-Beta.1", "正在初始化...")
        self.splash.show_splash()
        QApplication.processEvents()

        # 分步更新加载文案
        self.splash.set_subtitle("正在加载界面...")
        QApplication.processEvents()

        self.main_window = MainWindow()
        self.main_window.close_requested.connect(self._on_main_close)
        self.main_window.settings_requested.connect(self._open_settings)
        self.main_window.admin_requested.connect(self._open_admin)
        self.main_window.dev_requested.connect(self._open_dev)
        self.main_window.about_requested.connect(self._open_about)
        self.main_window.import_requested.connect(self._import_from_menu)
        self.main_window.utility_requested.connect(self._open_utility)

        self.splash.set_subtitle("正在启动核心服务...")
        QApplication.processEvents()

        self._setup_tray()
        self._setup_reminder_timer()
        self._setup_network()

        self.splash.set_subtitle("即将就绪...")
        QApplication.processEvents()

    def _setup_tray(self):
        if os.path.exists(STUDENT_ICO):
            icon = QIcon(STUDENT_ICO)
        else:
            # Fallback: 程序化绘制图标
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            grad = QLinearGradient(0, 0, 64, 64)
            grad.setColorAt(0, QColor("#3b82f6"))
            grad.setColorAt(1, QColor("#60a5fa"))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(4, 4, 56, 56, 16, 16)
            painter.setPen(QColor("#fff"))
            font = QFont("Microsoft YaHei", 18, QFont.Bold)
            painter.setFont(font)
            painter.drawText(pixmap.rect(), Qt.AlignCenter, "班")
            painter.end()
            icon = QIcon(pixmap)

        self.tray = QSystemTrayIcon(icon)
        self.tray.setToolTip("班级桌面助手 - 学生端")

        menu = QMenu()
        act_show = QAction("🏠 打开主界面", menu)
        act_show.triggered.connect(self.show_main)
        menu.addAction(act_show)

        menu.addSeparator()

        act_import = QAction("📥 导入教师课表", menu)
        act_import.triggered.connect(self._import_from_menu)
        menu.addAction(act_import)

        act_settings = QAction("⚙️ 设置", menu)
        act_settings.triggered.connect(self._open_settings)
        menu.addAction(act_settings)

        act_admin = QAction("🔐 管理员", menu)
        act_admin.triggered.connect(self._open_admin)
        menu.addAction(act_admin)

        act_util = QAction("🧰 实用工具", menu)
        act_util.triggered.connect(self._open_utility)
        menu.addAction(act_util)

        menu.addSeparator()

        act_quit = QAction("❌ 退出", menu)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show_main()

    def show_main(self):
        self.main_window.show()
        self.main_window.raise_()
        self.main_window.activateWindow()

    def _on_main_close(self):
        if self.settings.get("minimize_to_tray", True):
            self.main_window.hide()
            self.tray.showMessage(
                "班级桌面助手",
                "已最小化到系统托盘 📌",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            self._quit()

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, app=self, parent=self.main_window)
        dlg.exec()

    def _open_admin(self):
        dlg = AdminDialog(self.settings, app=self, parent=self.main_window)
        dlg.exec()

    def _open_dev(self):
        dlg = DeveloperDialog(self.settings, app=self, parent=self.main_window)
        dlg.exec()

    def _open_about(self):
        dlg = AboutDialog(parent=self.main_window)
        dlg.exec()

    def _open_utility(self):
        """打开实用工具对话框（关机控制 / 提醒 / 备忘录）"""
        dlg = UtilityDialog(self.settings, app=self, parent=self.main_window)
        dlg.exec()

    def _setup_reminder_timer(self):
        """启动定时器，每 30 秒检查一次到期提醒"""
        self.reminder_timer = QTimer(self.app)
        self.reminder_timer.timeout.connect(self._check_reminders)
        self.reminder_timer.start(30 * 1000)
        # 启动后 2 秒做一次初始检查，避免漏掉刚好到点的
        QTimer.singleShot(2000, self._check_reminders)

    def _setup_network(self):
        """初始化联网功能:自动检查更新 + 自动云同步"""
        # 创建后台 NetworkManager (不依赖 UI)
        self.network_mgr = NetworkManager(self.settings)
        self.network_mgr.task_finished.connect(self._on_network_task_finished)

        # 启动后自动任务错开执行，避免集中在同一时间窗口造成卡顿
        net = self.settings.get("network", {})
        # 启动后 5 秒检查更新（如果启用）
        if net.get("auto_check_update", True):
            QTimer.singleShot(5000, self._auto_check_update)

        # 启动后 15 秒拉取公告（与检查更新错开，避免并发请求扎堆）
        if net.get("notice_url"):
            QTimer.singleShot(15000, self._auto_fetch_notices)

        # 自动云同步（每 30 分钟）
        self.sync_timer = QTimer(self.app)
        self.sync_timer.timeout.connect(self._auto_sync)
        if net.get("auto_sync", False):
            self.sync_timer.start(30 * 60 * 1000)
            # 启动后 25 秒做一次初始同步（放在更新/公告之后，避免抢占）
            QTimer.singleShot(25000, self._auto_sync)

    def _auto_check_update(self):
        """启动时自动检查更新（静默）"""
        net = self.settings.get("network", {})
        if not net.get("update_url"):
            return
        self.network_mgr.check_update_async()

    def _auto_fetch_notices(self):
        """启动时自动拉取公告（静默）"""
        net = self.settings.get("network", {})
        if not net.get("notice_url"):
            return
        self.network_mgr.fetch_notices_async()

    def _auto_sync(self):
        """自动云同步：上传本地数据到云端"""
        net = self.settings.get("network", {})
        if not net.get("github_token") or not net.get("auto_sync", False):
            return
        # 收集数据并上传（简化版：不含 localStorage 课表，只同步备忘录/提醒）
        payload = {
            "version": APP_VERSION,
            "uploaded_at": datetime.now().isoformat(),
            "settings": {
                "memos": self.settings.get("memos", []),
                "reminders": self.settings.get("reminders", []),
            },
            "schedule": None,
        }
        # 异步导出 localStorage 中的课表
        if self.main_window:
            js = "JSON.stringify(Object.keys(localStorage).reduce((o,k)=>(o[k]=localStorage.getItem(k),o),{}))"
            try:
                self.main_window.browser.page().runJavaScript(
                    js, 0, lambda r: self._on_auto_localstorage(payload, r)
                )
            except Exception:
                self.network_mgr.sync_to_cloud_async(payload)
        else:
            self.network_mgr.sync_to_cloud_async(payload)

    def _on_auto_localstorage(self, payload, result):
        """自动同步时 localStorage 导出回调"""
        if result:
            try:
                payload["schedule"] = json.loads(result) if isinstance(result, str) else result
            except Exception:
                payload["schedule"] = str(result)
        self.network_mgr.sync_to_cloud_async(payload)

    def _on_network_task_finished(self, task_id, success, result):
        """后台网络任务完成回调（启动时的自动检查）"""
        if task_id == "update" and success and isinstance(result, dict):
            if result.get("has_update"):
                # 发现新版本，托盘通知 + 弹窗
                try:
                    self.tray.showMessage(
                        "🎉 发现新版本",
                        f"最新版本 v{result.get('latest_version','')} 已发布,请前往「实用工具 → 网络」查看详情",
                        QSystemTrayIcon.Information, 8000
                    )
                except Exception:
                    pass
        elif task_id == "notice" and success and isinstance(result, list):
            # 有新公告时通知
            net = self.settings.get("network", {})
            seen = net.get("seen_notice_ids", [])
            new_notices = [n for n in result if n.get("id") not in seen]
            if new_notices:
                try:
                    self.tray.showMessage(
                        "📢 新公告",
                        f"收到 {len(new_notices)} 条新公告,请前往「实用工具 → 网络」查看",
                        QSystemTrayIcon.Information, 5000
                    )
                except Exception:
                    pass
                # 标记为已读
                net["seen_notice_ids"] = [n.get("id", "") for n in result if n.get("id")]
                save_settings(self.settings)
        elif task_id == "upload" and success:
            # 自动上传成功
            net = self.settings.get("network", {})
            net["last_sync_time"] = datetime.now().isoformat()
            if isinstance(result, dict) and "gist_id" in result:
                net["gist_id"] = result["gist_id"]
            save_settings(self.settings)
            try:
                self.tray.showMessage(
                    "☁️ 云同步完成",
                    "数据已自动同步到云端",
                    QSystemTrayIcon.Information, 3000
                )
            except Exception:
                pass
        elif task_id == "upload" and not success:
            # 自动上传失败，托盘提醒（不弹窗打扰，仅在托盘提示）
            try:
                self.tray.showMessage(
                    "⚠️ 自动云同步失败",
                    f"{result}\n可在「实用工具 → 网络」中手动重试",
                    QSystemTrayIcon.Warning, 6000
                )
            except Exception:
                pass

    def _check_reminders(self):
        """检查所有启用的提醒，到达时间则弹窗 + 托盘通知"""
        reminders = self.settings.get("reminders", [])
        if not reminders:
            return
        now = datetime.now()
        changed = False
        for r in reminders:
            if not r.get("enabled", True):
                continue
            try:
                dt = datetime.fromisoformat(r["datetime"])
            except Exception:
                continue
            # 还没到触发时刻
            if dt > now:
                continue
            last = r.get("last_triggered", "")
            last_dt = None
            if last:
                try:
                    last_dt = datetime.fromisoformat(last)
                except Exception:
                    last_dt = None

            repeat = r.get("repeat", "不重复")
            # 找到「最近一次应触发且 <= now」的时刻
            last_due = self._last_due_time(dt, now, repeat)
            if last_due is None:
                continue
            # 若上次触发时间早于该应触发时刻 → 触发本次
            if last_dt is not None and last_dt >= last_due:
                continue

            title = r.get("title", "提醒")
            try:
                self.tray.showMessage(
                    "⏰ 提醒",
                    title,
                    QSystemTrayIcon.Information,
                    5000
                )
            except Exception:
                pass
            # 异步弹窗，避免阻塞定时器
            QTimer.singleShot(100, lambda t=title: self._show_reminder_box(t))

            r["last_triggered"] = now.isoformat()
            # 对"不重复"，触发后自动禁用；否则推进到下一次触发时刻
            if repeat == "不重复":
                r["enabled"] = False
            else:
                next_dt = self._last_due_time(dt, now, repeat, advance_to_next=True)
                if next_dt:
                    r["datetime"] = next_dt.isoformat()
            changed = True

        if changed:
            save_settings(self.settings)

    @staticmethod
    def _last_due_time(dt, now, repeat, advance_to_next=False):
        """
        根据原始触发时刻 dt 和当前 now，计算：
        - 默认（advance_to_next=False）：最近一次「应触发且 <= now」的时刻
        - advance_to_next=True：下一次「应触发且 > now」的时刻
        返回 datetime 或 None（表示不适用，如工作日模式当天还没到工作日）。
        """
        if repeat == "不重复":
            return dt if not advance_to_next else None

        if repeat == "每天":
            cur = dt
            if advance_to_next:
                while cur <= now:
                    cur = cur + timedelta(days=1)
                return cur
            else:
                while cur <= now:
                    cur = cur + timedelta(days=1)
                # cur 是下一次应触发时刻，上一次就是 cur - 1 day
                return cur - timedelta(days=1)

        if repeat == "每周":
            cur = dt
            if advance_to_next:
                while cur <= now:
                    cur = cur + timedelta(weeks=1)
                return cur
            else:
                while cur <= now:
                    cur = cur + timedelta(weeks=1)
                return cur - timedelta(weeks=1)

        if repeat == "工作日(周一至周五)":
            # 工作日跳过周六(5)、周日(6)
            def next_workday(d):
                d = d + timedelta(days=1)
                while d.weekday() >= 5:
                    d = d + timedelta(days=1)
                return d

            cur = dt
            # 推进到首个 <= now 的工作日触发时刻
            while cur <= now:
                cur = next_workday(cur)
            # cur 是「下一个 > now 的工作日触发时刻」
            if advance_to_next:
                return cur
            # 上一次 = cur 的前一工作日触发时刻
            prev = cur - timedelta(days=1)
            while prev.weekday() >= 5:
                prev = prev - timedelta(days=1)
            return prev

        return None

    def _show_reminder_box(self, title):
        """弹出提醒对话框（同时唤起主窗口以引起注意）"""
        self.show_main()
        QMessageBox.information(
            self.main_window,
            "⏰ 提醒",
            f"现在是该做这件事的时间了：\n\n   {title}"
        )

    def _import_from_menu(self):
        """从菜单栏导入教师课表"""
        dlg = ImportDialog(parent=self.main_window)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self.import_schedule(dlg.selected_path, self.main_window)

    def import_schedule(self, path, parent_widget):
        """导入教师导出的课表 JSON 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 验证文件格式
            if "subjects" not in data and "subjs" not in data:
                QMessageBox.warning(parent_widget, "格式错误",
                    "❌ 这不是有效的教师课表文件！\n请确认文件由教师端导出。")
                return

            subjects = data.get("subjects") or data.get("subjs", [])
            schedule = data.get("schedule") or data.get("schs", [])

            # 确认覆盖
            reply = QMessageBox.question(
                parent_widget, "确认导入",
                f"即将导入：\n"
                f"  📚 科目 {len(subjects)} 个\n"
                f"  📅 课程 {len(schedule)} 节\n\n"
                f"这将覆盖当前的课表和科目数据，确定继续吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            # 写入 localStorage
            js = f"""
            (function() {{
                localStorage.setItem('ch_subj', JSON.stringify({json.dumps(subjects, ensure_ascii=False)}));
                localStorage.setItem('ch_sch', JSON.stringify({json.dumps(schedule, ensure_ascii=False)}));
                load();
                renderSch();
                renderSubjs();
                renderDash();
            }})();
            """
            self.main_window.run_js(js)
            QMessageBox.information(parent_widget, "导入成功",
                f"✅ 课表已导入！\n  科目 {len(subjects)} 个\n  课程 {len(schedule)} 节")

        except json.JSONDecodeError:
            QMessageBox.warning(parent_widget, "错误", "❌ 文件解析失败，请确认是有效的 JSON 文件")
        except Exception as e:
            QMessageBox.warning(parent_widget, "错误", f"导入失败：{e}")

    def view_raw_data(self, parent_dialog):
        def on_result(result):
            if not result:
                QMessageBox.warning(parent_dialog, "错误", "无法读取数据")
                return
            dlg = QDialog(parent_dialog)
            dlg.setWindowTitle("📋 原始数据")
            dlg.resize(500, 400)
            layout = QVBoxLayout(dlg)
            te = QTextEdit()
            te.setReadOnly(True)
            try:
                data = json.loads(result)
                te.setText(json.dumps(data, ensure_ascii=False, indent=2))
            except:
                te.setText(result)
            layout.addWidget(te)
            dlg.exec()

        self.main_window.run_js(
            "JSON.stringify({hws: JSON.parse(localStorage.getItem('ch_hw')||'[]'), schs: JSON.parse(localStorage.getItem('ch_sch')||'[]'), subjs: JSON.parse(localStorage.getItem('ch_subj')||'[]')})",
            on_result
        )

    def _inject_test_data(self):
        """注入测试课程数据（仅当无真实数据时）"""
        js = """
        (function() {
            var existing = localStorage.getItem('ch_sch');
            var existingSchs = existing ? JSON.parse(existing) : [];
            var hasRealData = existingSchs.some(function(s) {
                return s.id && s.id.indexOf('test_') !== 0;
            });
            if (hasRealData) return;

            if (!localStorage.getItem('ch_subj')) {
                localStorage.setItem('ch_subj', JSON.stringify([
                    {id:'d1', name:'语文', teacher:'', color:'#e17055'},
                    {id:'d2', name:'数学', teacher:'', color:'#3b82f6'},
                    {id:'d3', name:'英语', teacher:'', color:'#0984e3'},
                    {id:'d4', name:'物理', teacher:'', color:'#00cec9'},
                    {id:'d5', name:'化学', teacher:'', color:'#fd79a8'},
                    {id:'d6', name:'生物', teacher:'', color:'#00b894'},
                    {id:'d7', name:'历史', teacher:'', color:'#fdcb6e'},
                    {id:'d8', name:'地理', teacher:'', color:'#74b9ff'},
                    {id:'d9', name:'政治', teacher:'', color:'#60a5fa'},
                ]));
            }

            var jsDay = new Date().getDay();
            var todayIdx = jsDay === 0 ? 6 : jsDay - 1;

            var testSchs = [];
            var subjIds = ['d1','d2','d3','d4','d5','d6','d7','d8'];
            var rooms = ['101','203','305','401','102','204','306','402'];
            for (var p = 1; p <= 8; p++) {
                testSchs.push({
                    id: 'test_' + p,
                    day: todayIdx,
                    period: p,
                    subjectId: subjIds[(p - 1) % subjIds.length],
                    room: rooms[(p - 1) % rooms.length]
                });
            }
            localStorage.setItem('ch_sch', JSON.stringify(testSchs));
            load();
            renderDash();
            renderSch();
        })();
        """
        self.main_window.run_js(js)

    def _quit(self):
        self.tray.hide()
        self.app.quit()

    def run(self):
        self.main_window.show()
        self.main_window.browser.loadFinished.connect(self._after_page_load)
        sys.exit(self.app.exec())

    def _after_page_load(self, ok):
        try:
            self.main_window.browser.loadFinished.disconnect(self._after_page_load)
        except:
            pass
        # 首次页面加载完成后关闭启动动画
        try:
            if getattr(self, "splash", None):
                self.splash.close_splash()
                self.splash = None
        except:
            pass
        if not ok:
            return
        self._inject_test_data()


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    app = ClassAssistantApp()
    app.run()
