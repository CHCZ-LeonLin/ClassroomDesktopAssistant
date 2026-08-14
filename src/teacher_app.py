# -*- coding: utf-8 -*-
"""
班级桌面助手 v1.2.3-Beta.1 - 教师端
功能：设置课表、管理科目、导出课表数据供学生导入、联网上传课表
"""

import sys
import os
import json
import uuid
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

from PySide6.QtCore import (
    Qt, QUrl, Signal, QThread, QTimer, QObject,
    QPropertyAnimation, QEasingCurve, QRect, QPoint
)
from PySide6.QtGui import (
    QIcon, QAction, QFont, QColor, QPainter, QBrush, QLinearGradient,
    QPixmap, QPen, QPainterPath
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QSystemTrayIcon, QMenu, QDialog,
    QVBoxLayout, QLabel, QPushButton, QLineEdit, QTextEdit, QMessageBox,
    QFileDialog, QGroupBox, QFormLayout, QHBoxLayout, QCheckBox, QTabWidget,
    QWidget
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

HTML_FILE = os.path.join(RESOURCE_DIR, "teacher.html")
SETTINGS_FILE = os.path.join(APP_DIR, "teacher_settings.json")
TEACHER_ICO = os.path.join(RESOURCE_DIR, "teacher.ico")


def load_settings():
    defaults = {
        "teacher_password": "",
        "network": {
            "update_url": "",
            "notice_url": "",
            "github_token": "",
            "gist_id": "",
            "auto_check_update": True,
            "last_upload_time": "",
            "seen_notice_ids": [],
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


APP_VERSION = "1.2.3-Beta.1"
GITHUB_API_BASE = "https://api.github.com/gists"


# ============================================================
# 网络工具函数
# ============================================================
def _parse_version(v):
    """解析版本号 'v1.1.1-Beta.1' -> (1, 1, 1, 'Beta', 1)"""
    v = v.strip().lstrip("vV")
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
    if r[:3] != l[:3]:
        return r[:3] > l[:3]
    if not r[3] and l[3]:
        return True
    if r[3] and not l[3]:
        return False
    if r[3] and l[3]:
        if r[3] != l[3]:
            return r[3] > l[3]
        return r[4] > l[4]
    return False


def _http_request(url, method="GET", data=None, headers=None, timeout=10, retries=1):
    """通用 HTTP 请求封装,返回 (status_code, response_text)。
    网络层错误（超时/连接失败）会自动重试 retries 次；HTTP 错误码（4xx/5xx）不重试。
    """
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", "ClassAssistant-Teacher/1.1")
    if data is not None and not isinstance(data, bytes):
        data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")

    last_err = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.getcode(), resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
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


# ============================================================
# 关于对话框
# ============================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于")
        self.setFixedSize(380, 320)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog { background: #1a1a2e; }
            QLabel { color: #dfe6e9; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 28, 28, 24)

        icon_lbl = QLabel("👨‍🏫")
        icon_lbl.setStyleSheet("font-size: 42px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        title_lbl = QLabel("班级桌面助手 - 教师端")
        title_lbl.setAlignment(Qt.AlignCenter)
        title_lbl.setStyleSheet("font-size: 20px; font-weight: bold; color: #f97316; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        ver_lbl = QLabel("v1.2.3-Beta.1")
        ver_lbl.setAlignment(Qt.AlignCenter)
        ver_lbl.setStyleSheet("font-size: 11px; color: #636e72; background: transparent; border: none;")
        layout.addWidget(ver_lbl)

        from PySide6.QtWidgets import QFrame
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: rgba(249, 115, 22, 0.15); border: none; max-height: 1px;")
        layout.addWidget(line)

        info_lbl = QLabel(
            "教师课表编辑工具<br>"
            "科目管理 · 课表编排 · 一键导出<br><br>"
            "<span style='color:#636e72;'>技术栈</span>  Python + PySide6 + QtWebEngine<br>"
            "<span style='color:#636e72;'>作者：</span>CHCZ-LeonLin、FENG"
        )
        info_lbl.setStyleSheet("font-size: 12px; color: #dfe6e9; background: transparent; border: none; line-height: 1.8;")
        info_lbl.setAlignment(Qt.AlignCenter)
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        layout.addStretch()

        btn_close = QPushButton("关 闭")
        btn_close.setStyleSheet("""
            QPushButton {
                background: rgba(249, 115, 22, 0.15); color: #f97316;
                border: 1px solid rgba(249, 115, 22, 0.3);
                border-radius: 8px; padding: 8px 32px; font-size: 13px;
            }
            QPushButton:hover { background: #f97316; color: #fff; border-color: #f97316; }
        """)
        btn_close.clicked.connect(self.accept)
        btn_row = QVBoxLayout()
        btn_row.addWidget(btn_close, alignment=Qt.AlignCenter)
        layout.addLayout(btn_row)


# ============================================================
# 网络管理器（异步线程）
# ============================================================
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


class NetworkManager(QObject):
    """网络功能管理器:在线更新 / 在线公告 / 云上传课表"""
    task_finished = Signal(str, bool, object)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._thread = None
        self._worker = None

    def _ensure_network(self):
        if "network" not in self.settings:
            self.settings["network"] = {}
        return self.settings["network"]

    def check_update_async(self):
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

    def fetch_notices_async(self):
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

    def upload_schedule_async(self, payload):
        """异步上传课表数据到 GitHub Gist"""
        net = self._ensure_network()
        token = net.get("github_token", "")
        if not token:
            self.task_finished.emit("upload", False, "未配置 GitHub Token")
            return
        self._run_in_thread("upload", self._do_upload_schedule, token, payload)

    def _do_upload_schedule(self, token, payload):
        net = self._ensure_network()
        gist_id = net.get("gist_id", "")
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        body_data = {
            "description": "班级桌面助手 - 教师课表数据",
            "files": {
                "teacher_schedule.json": {
                    "content": content
                }
            }
        }
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        if gist_id:
            url = f"{GITHUB_API_BASE}/{gist_id}"
            code, body = _http_request(url, method="PATCH", data=body_data,
                                       headers=headers, timeout=20)
        else:
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
            "uploaded_at": datetime.now().isoformat(),
        }

    def _run_in_thread(self, task_id, func, *args):
        self._thread = QThread()
        self._worker = _NetworkWorker(task_id, func, *args)
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._on_task_finished)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()
        QTimer.singleShot(0, self._worker.run)

    def _on_task_finished(self, task_id, success, result):
        self.task_finished.emit(task_id, success, result)


# ============================================================
# 联网功能对话框
# ============================================================
NETWORK_STYLE = """
QDialog { background: #1a1a2e; }
QGroupBox {
    color: #f97316; font-size: 12px; font-weight: 600;
    border: 1px solid rgba(249, 115, 22, 0.15);
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
QLineEdit {
    background: #16213e; color: #dfe6e9; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
    font-size: 12px; border: 1px solid rgba(249, 115, 22, 0.15);
    border-radius: 8px; padding: 8px 12px;
}
QLineEdit:focus { border-color: #f97316; }
QPushButton {
    background: rgba(249, 115, 22, 0.10); color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.25);
    border-radius: 8px; padding: 8px 18px; font-size: 12px;
    font-family: "Microsoft YaHei UI", "Microsoft YaHei";
}
QPushButton:hover { background: #f97316; color: #fff; border-color: #f97316; }
QPushButton:pressed { background: #ea580c; }
QPushButton:disabled { background: #1a1a2e; color: #636e72; border-color: #2d2d4a; }
QPushButton[primary="true"] {
    background: #f97316; color: #fff; border: none; font-weight: 600;
}
QPushButton[primary="true"]:hover { background: #fb923c; }
QPushButton[primary="true"]:pressed { background: #ea580c; }
QTabWidget::pane {
    border: none;
    border-top: 1px solid rgba(249, 115, 22, 0.12);
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
    background: transparent; color: #f97316;
    border: none;
    border-bottom: 2px solid #f97316;
}
QTabBar::tab:hover:!selected { color: #fb923c; border-bottom: 2px solid rgba(249, 115, 22, 0.3); }
QCheckBox { color: #dfe6e9; font-size: 12px; spacing: 6px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border-radius: 4px;
    border: 1px solid rgba(249, 115, 22, 0.3);
    background: #16213e;
}
QCheckBox::indicator:checked {
    background: #f97316; border-color: #f97316;
}
QScrollBar:vertical {
    background: transparent; width: 8px; margin: 0;
}
QScrollBar::handle:vertical {
    background: rgba(249, 115, 22, 0.25); border-radius: 4px; min-height: 30px;
}
QScrollBar::handle:vertical:hover { background: rgba(249, 115, 22, 0.4); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


class NetworkDialog(QDialog):
    """联网功能：上传课表 / 在线更新 / 在线公告"""

    def __init__(self, settings, app=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.parent_app = app
        if "network" not in self.settings:
            self.settings["network"] = {}
        self.net = self.settings["network"]
        self.nm = NetworkManager(self.settings)
        self.nm.task_finished.connect(self._on_task_finished)
        self.setWindowTitle("🌐 联网功能")
        self.setFixedSize(580, 560)
        self.setStyleSheet(NETWORK_STYLE)
        self._build_ui()
        self._refresh_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("🌐 联网功能")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f97316;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_upload(), "⬆️ 上传课表")
        self.tabs.addTab(self._tab_update(), "🔄 在线更新")
        self.tabs.addTab(self._tab_notice(), "📢 在线公告")
        layout.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _tab_upload(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp = QGroupBox("☁️ 上传课表到云端（GitHub Gist）")
        gl = QVBoxLayout(grp)
        gl.setSpacing(8)

        hint = QLabel("在 GitHub 创建 Personal Access Token（勾选 gist 权限）后填入下方。\n上传后，学生在「实用工具 → 网络」中配置相同 Token 即可下载课表。")
        hint.setStyleSheet("color: #636e72; font-size: 11px;")
        hint.setWordWrap(True)
        gl.addWidget(hint)

        row_tok = QHBoxLayout()
        row_tok.addWidget(QLabel("Token："))
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("ghp_xxxxxxxxxxxx")
        self.token_input.setEchoMode(QLineEdit.Password)
        self.token_input.setText(self.net.get("github_token", ""))
        row_tok.addWidget(self.token_input, 2)
        gl.addLayout(row_tok)

        row_gid = QHBoxLayout()
        row_gid.addWidget(QLabel("Gist ID："))
        self.gist_id_lbl = QLabel(self.net.get("gist_id", "") or "（首次上传后自动生成）")
        self.gist_id_lbl.setStyleSheet("color: #636e72; font-size: 11px;")
        self.gist_id_lbl.setWordWrap(True)
        row_gid.addWidget(self.gist_id_lbl, 2)
        gl.addLayout(row_gid)

        row_btns = QHBoxLayout()
        btn_save = QPushButton("💾 保存设置")
        btn_save.clicked.connect(self._save_settings)
        row_btns.addWidget(btn_save)
        btn_upload = QPushButton("⬆️ 上传当前课表")
        btn_upload.setProperty("primary", True)
        btn_upload.clicked.connect(self._upload_schedule)
        row_btns.addWidget(btn_upload)
        gl.addLayout(row_btns)

        self.lbl_upload = QLabel("（未上传）")
        self.lbl_upload.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_upload.setWordWrap(True)
        gl.addWidget(self.lbl_upload)

        v.addWidget(grp)
        v.addStretch()
        return w

    def _tab_update(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp = QGroupBox("🔄 在线更新")
        gl = QVBoxLayout(grp)
        gl.setSpacing(8)

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("更新源："))
        self.update_url_input = QLineEdit()
        self.update_url_input.setPlaceholderText("https://.../version.json")
        self.update_url_input.setText(self.net.get("update_url", ""))
        row_url.addWidget(self.update_url_input, 2)
        gl.addLayout(row_url)

        self.chk_auto = QCheckBox("启动时自动检查更新")
        self.chk_auto.setChecked(self.net.get("auto_check_update", True))
        gl.addWidget(self.chk_auto)

        row_btns = QHBoxLayout()
        btn_save = QPushButton("💾 保存设置")
        btn_save.clicked.connect(self._save_update_settings)
        row_btns.addWidget(btn_save)
        btn_check = QPushButton("🔍 立即检查更新")
        btn_check.setProperty("primary", True)
        btn_check.clicked.connect(self._check_update)
        row_btns.addWidget(btn_check)
        gl.addLayout(row_btns)

        self.lbl_update = QLabel(f"当前版本：v{APP_VERSION}")
        self.lbl_update.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_update.setWordWrap(True)
        gl.addWidget(self.lbl_update)

        v.addWidget(grp)
        v.addStretch()
        return w

    def _tab_notice(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)

        grp = QGroupBox("📢 在线公告")
        gl = QVBoxLayout(grp)
        gl.setSpacing(8)

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("公告源："))
        self.notice_url_input = QLineEdit()
        self.notice_url_input.setPlaceholderText("https://.../notice.json")
        self.notice_url_input.setText(self.net.get("notice_url", ""))
        row_url.addWidget(self.notice_url_input, 2)
        gl.addLayout(row_url)

        row_btns = QHBoxLayout()
        btn_save = QPushButton("💾 保存设置")
        btn_save.clicked.connect(self._save_notice_settings)
        row_btns.addWidget(btn_save)
        btn_fetch = QPushButton("📢 拉取公告")
        btn_fetch.setProperty("primary", True)
        btn_fetch.clicked.connect(self._fetch_notices)
        row_btns.addWidget(btn_fetch)
        gl.addLayout(row_btns)

        self.lbl_notice = QLabel("（点击「拉取公告」获取最新通知）")
        self.lbl_notice.setStyleSheet("color: #636e72; font-size: 11px;")
        self.lbl_notice.setWordWrap(True)
        gl.addWidget(self.lbl_notice)

        v.addWidget(grp)
        v.addStretch()
        return w

    def _refresh_status(self):
        last = self.net.get("last_upload_time", "")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                self.lbl_upload.setText(f"上次上传：{dt.strftime('%Y-%m-%d %H:%M:%S')}")
            except Exception:
                self.lbl_upload.setText(f"上次上传：{last}")

    def _save_settings(self):
        self.net["github_token"] = self.token_input.text().strip()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "云上传设置已保存")

    def _save_update_settings(self):
        self.net["update_url"] = self.update_url_input.text().strip()
        self.net["auto_check_update"] = self.chk_auto.isChecked()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "更新设置已保存")

    def _save_notice_settings(self):
        self.net["notice_url"] = self.notice_url_input.text().strip()
        save_settings(self.settings)
        QMessageBox.information(self, "已保存", "公告设置已保存")

    def _upload_schedule(self):
        self.net["github_token"] = self.token_input.text().strip()
        save_settings(self.settings)
        if not self.parent_app:
            return
        self.lbl_upload.setText("⬆️ 正在上传课表...")
        # 从 localStorage 获取课表数据
        self.parent_app.main_window.run_js(
            "JSON.stringify({"
            "subjs: JSON.parse(localStorage.getItem('ch_subj')||'[]'), "
            "schs: JSON.parse(localStorage.getItem('ch_sch')||'[]')"
            "})",
            self._on_schedule_data_ready
        )

    def _on_schedule_data_ready(self, result):
        if not result:
            self.lbl_upload.setText("❌ 无法读取课表数据")
            return
        try:
            data = json.loads(result)
        except Exception as e:
            self.lbl_upload.setText(f"❌ 数据解析失败：{e}")
            return

        subjs = data.get("subjs", [])
        schs = data.get("schs", [])
        if not subjs and not schs:
            self.lbl_upload.setText("⚠️ 当前没有数据可上传")
            QMessageBox.information(self, "提示", "当前没有课表数据，请先添加科目和课程。")
            return

        payload = {
            "version": APP_VERSION,
            "export_type": "teacher_schedule",
            "export_time": datetime.now().isoformat(),
            "subjects": subjs,
            "schedule": schs,
        }
        self.nm.upload_schedule_async(payload)

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

    def _on_task_finished(self, task_id, success, result):
        if task_id == "update":
            self._handle_update_result(success, result)
        elif task_id == "notice":
            self._handle_notice_result(success, result)
        elif task_id == "upload":
            self._handle_upload_result(success, result)

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
                f"更新内容：\n{info.get('release_notes', '（无）')}\n\n"
                f"下载地址：\n{info.get('download_url', '（无）')}"
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
        all_ids = [n.get("id", "") for n in notices if n.get("id")]
        self.net["seen_notice_ids"] = all_ids
        save_settings(self.settings)

    def _handle_upload_result(self, success, result):
        if not success:
            self.lbl_upload.setText(f"❌ 上传失败：{result}")
            QMessageBox.warning(self, "上传失败", str(result))
            return
        self.net["last_upload_time"] = datetime.now().isoformat()
        if isinstance(result, dict) and "gist_id" in result:
            self.net["gist_id"] = result["gist_id"]
            self.gist_id_lbl.setText(result["gist_id"])
        save_settings(self.settings)
        self._refresh_status()
        QMessageBox.information(self, "上传成功",
            "✅ 课表已上传到云端！\n\n"
            "学生可在「实用工具 → 网络」中使用相同的 Token 和 Gist ID 下载课表。")


# ============================================================
# 主窗口
# ============================================================
class TeacherWindow(QMainWindow):
    export_requested = Signal()
    about_requested = Signal()
    network_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("班级桌面助手 v1.2.3-Beta.1 - 教师端")
        self.resize(1200, 800)
        self.setMinimumSize(900, 600)

        if os.path.exists(TEACHER_ICO):
            self.setWindowIcon(QIcon(TEACHER_ICO))

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
                background: #1a1a2e; color: #f97316;
                padding: 0px; margin: 0px; spacing: 2px;
                font-size: 13px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
                border-bottom: 1px solid rgba(249, 115, 22, 0.15);
            }
            QMenuBar::item {
                background: transparent; color: #f97316;
                padding: 6px 18px; border-radius: 0px; margin: 0px;
            }
            QMenuBar::item:selected { background: rgba(249, 115, 22, 0.2); color: #fff; }
            QMenuBar::item:pressed { background: rgba(249, 115, 22, 0.35); color: #fff; }
            QMenu {
                background: #16213e;
                border: 1px solid rgba(249, 115, 22, 0.25);
                border-radius: 8px; padding: 6px;
                font-size: 13px; font-family: "Microsoft YaHei UI", "Microsoft YaHei";
            }
            QMenu::item { padding: 8px 28px 8px 16px; border-radius: 6px; color: #dfe6e9; }
            QMenu::item:selected { background: rgba(249, 115, 22, 0.25); color: #fff; }
            QMenu::separator { height: 1px; background: rgba(249, 115, 22, 0.15); margin: 4px 8px; }
        """)

        # --- 导出菜单 ---
        menu_export = menubar.addMenu("导出")
        act_export = QAction("📤 导出课表数据", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self.export_requested.emit)
        menu_export.addAction(act_export)

        # --- 联网菜单 ---
        menu_network = menubar.addMenu("联网")
        act_network = QAction("🌐 联网功能", self)
        act_network.setShortcut("Ctrl+N")
        act_network.triggered.connect(self.network_requested.emit)
        menu_network.addAction(act_network)

        # --- 关于菜单 ---
        menu_about = menubar.addMenu("关于")
        act_about = QAction("ℹ️ 关于教师端", self)
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
        e.accept()


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

        rect = self.rect().adjusted(0, 0, -1, -1)
        radius = 20
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor("#1a1a3a"))
        grad.setColorAt(0.5, QColor("#16162e"))
        grad.setColorAt(1.0, QColor("#0f0f25"))
        p.fillPath(path, QBrush(grad))

        pen = QPen(QColor(59, 130, 246, 60), 1.2)
        p.setPen(pen)
        p.drawPath(path)

        glow = QLinearGradient(rect.topLeft(), QPoint(rect.width(), 0))
        glow.setColorAt(0.0, QColor(96, 165, 250, 0))
        glow.setColorAt(0.5, QColor(96, 165, 250, 25))
        glow.setColorAt(1.0, QColor(96, 165, 250, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRect(rect.adjusted(0, 0, 0, -(rect.height() - 3)))

        cx, cy = rect.width() // 2, 120
        outer_r = 38
        inner_r = 28

        pen_bg = QPen(QColor(59, 130, 246, 25), 4)
        p.setPen(pen_bg)
        p.drawEllipse(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2)

        pen_fg = QPen(QColor(96, 165, 250, 230), 4, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen_fg)
        span = 30 * 16
        start = (self._angle * 16) % 360 * 16
        p.drawArc(cx - outer_r, cy - outer_r, outer_r * 2, outer_r * 2, -start, span)

        pen_inner = QPen(QColor(129, 140, 248, 140), 2)
        p.setPen(pen_inner)
        span2 = 20 * 16
        start2 = ((360 - self._angle * 1.5) * 16) % 360 * 16
        p.drawArc(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2, -start2, span2)

        pulse = 4 + (self._step % 20) * 0.25
        dot_alpha = 200 - (self._step % 20) * 8
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(96, 165, 250, max(30, dot_alpha))))
        p.drawEllipse(cx - pulse / 2, cy - pulse / 2, pulse, pulse)

        p.setPen(QPen(QColor("#e2e8f0")))
        title_font = QFont("Microsoft YaHei UI", 15, QFont.Bold)
        p.setFont(title_font)
        p.drawText(QRect(0, 175, rect.width(), 28), Qt.AlignCenter, self._app_name)

        p.setPen(QPen(QColor(96, 165, 250, 180)))
        ver_font = QFont("Microsoft YaHei UI", 8)
        p.setFont(ver_font)
        p.drawText(QRect(0, 205, rect.width(), 16), Qt.AlignCenter, self._version)

        p.setPen(QPen(QColor(148, 163, 186, 200)))
        sub_font = QFont("Microsoft YaHei UI", 9)
        p.setFont(sub_font)
        dots = "." * ((self._dot_offset // 10) + 1)
        p.drawText(
            QRect(0, 230, rect.width(), 20),
            Qt.AlignCenter,
            self._subtitle + dots
        )


# ============================================================
# 主应用
# ============================================================
class TeacherApp:
    def __init__(self):
        self.app = QApplication(sys.argv)

        # 全局默认字体
        font = QFont("Microsoft YaHei UI", 9)
        font.setStyleHint(QFont.SansSerif)
        self.app.setFont(font)

        self.settings = load_settings()

        # 显示启动动画
        self.splash = SplashWidget("班级桌面助手", "v1.2.3-Beta.1", "正在初始化教师端...")
        self.splash.show_splash()
        QApplication.processEvents()

        self.splash.set_subtitle("正在加载界面...")
        QApplication.processEvents()

        self.main_window = TeacherWindow()
        self.main_window.export_requested.connect(self._export_schedule)
        self.main_window.about_requested.connect(self._open_about)
        self.main_window.network_requested.connect(self._open_network_dialog)

        self.splash.set_subtitle("即将就绪...")
        QApplication.processEvents()

    def _export_schedule(self):
        """导出课表数据为 JSON 文件"""
        def on_result(result):
            if not result:
                QMessageBox.warning(self.main_window, "错误", "无法读取数据，请先添加课程")
                return
            try:
                data = json.loads(result)
                subjs = data.get("subjs", [])
                schs = data.get("schs", [])

                if not subjs and not schs:
                    QMessageBox.warning(self.main_window, "提示", "⚠️ 当前没有数据可导出")
                    return

                export_data = {
                    "version": "1.2.3-Beta.1",
                    "export_type": "teacher_schedule",
                    "export_time": datetime.now().isoformat(),
                    "subjects": subjs,
                    "schedule": schs,
                }

                default_name = f"教师课表_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                path, _ = QFileDialog.getSaveFileName(
                    self.main_window, "导出课表数据", default_name,
                    "JSON Files (*.json)"
                )
                if path:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                    QMessageBox.information(self.main_window, "导出成功",
                        f"✅ 课表已导出到\n{path}\n\n"
                        f"科目 {len(subjs)} 个\n课程 {len(schs)} 节\n\n"
                        f"请将此文件发送给学生，学生可通过「导入教师课表」功能导入。")
            except Exception as e:
                QMessageBox.warning(self.main_window, "错误", f"导出失败：{e}")

        self.main_window.run_js(
            "JSON.stringify({"
            "subjs: JSON.parse(localStorage.getItem('ch_subj')||'[]'), "
            "schs: JSON.parse(localStorage.getItem('ch_sch')||'[]')"
            "})",
            on_result
        )

    def _open_about(self):
        dlg = AboutDialog(parent=self.main_window)
        dlg.exec()

    def _open_network_dialog(self):
        dlg = NetworkDialog(self.settings, app=self, parent=self.main_window)
        dlg.exec()

    def _inject_default_subjects(self):
        """注入默认科目（首次启动）"""
        js = """
        (function() {
            if (!localStorage.getItem('ch_subj')) {
                localStorage.setItem('ch_subj', JSON.stringify([
                    {id:'d1', name:'语文', teacher:'', color:'#e17055'},
                    {id:'d2', name:'数学', teacher:'', color:'#6c5ce7'},
                    {id:'d3', name:'英语', teacher:'', color:'#0984e3'},
                    {id:'d4', name:'物理', teacher:'', color:'#00cec9'},
                    {id:'d5', name:'化学', teacher:'', color:'#fd79a8'},
                    {id:'d6', name:'生物', teacher:'', color:'#00b894'},
                    {id:'d7', name:'历史', teacher:'', color:'#fdcb6e'},
                    {id:'d8', name:'地理', teacher:'', color:'#74b9ff'},
                    {id:'d9', name:'政治', teacher:'', color:'#a29bfe'},
                ]));
                load();
                renderSubjs();
                renderSch();
            }
        })();
        """
        self.main_window.run_js(js)

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
        self._inject_default_subjects()


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    app = TeacherApp()
    app.run()
