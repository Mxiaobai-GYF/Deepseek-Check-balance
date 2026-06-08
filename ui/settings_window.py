"""
settings_window.py - 设置窗口
--------------------------------
用于首次输入 API Key 和修改告警阈值。
同样使用液态玻璃风格，与主窗口保持视觉一致。

安全设计：
  - 输入框使用 PasswordEchoOnEdit 模式（输入时可见，失焦后遮罩）
  - 点击"保存"时调用 key_manager.save_api_key，不在本模块保留 Key
  - 提供"验证 Key"功能，即时检验有效性
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame,
    QCheckBox, QApplication
)
from PyQt6.QtCore import Qt, QPoint, pyqtSignal, QThread, QObject
from PyQt6.QtGui import QPainter, QPixmap

from core.key_manager import save_api_key, load_api_key, delete_api_key
from core.api_client import validate_api_key, ApiResult
from ui.styles import (
    card_background_rgba, draw_glass_glow, create_noise_pixmap,
    divider_qss, close_btn_qss, primary_btn_qss, secondary_btn_qss,
    danger_btn_qss, input_qss, GREEN, RED
)

logger = logging.getLogger(__name__)


# ─── 验证 Key 的工作线程 ───────────────────────────────────────────────────

class ValidateWorker(QObject):
    """
    在独立线程中验证 API Key，避免阻塞 UI。
    """
    finished = pyqtSignal(object, str)  # (ApiResult, api_key)
    
    def __init__(self, api_key: str):
        super().__init__()
        self._api_key = api_key
    
    def run(self):
        result = validate_api_key(self._api_key)
        self.finished.emit(result, self._api_key)
        # 显式覆写清除，防止 del 后对象延迟析构导致 Key 残留
        self._api_key = ""


# ─── 设置窗口 ─────────────────────────────────────────────────────────────

class SettingsWindow(QWidget):
    """
    设置窗口：API Key 管理 + 告警阈值配置。
    """
    
    # 保存成功后通知主窗口刷新 Key 显示
    settings_saved = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setFixedSize(360, 400)
        self.setWindowTitle("设置 - DeepSeek 余额监控")
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 拖动支持
        self._drag_pos = None
        
        # 验证线程
        self._thread = None
        self._worker = None
        
        # 磨砂纹理缓存
        self._noise_texture: QPixmap | None = None
        
        self._init_ui()
        self._load_current_settings()
    
    def _init_ui(self):
        """构建设置 UI。"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        
        self._card = QFrame(self)
        self._card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(12)
        outer.addWidget(self._card)
        
        # ── 标题栏 ───────────────────────────────────────────────
        title_row = QHBoxLayout()
        
        title = QLabel("⚙  设置")
        title.setObjectName("settingsTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        
        close_btn = QPushButton("×")
        close_btn.setFixedSize(30, 30)
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.hide)
        title_row.addWidget(close_btn)
        
        card_layout.addLayout(title_row)
        
        # ── 分隔线 ───────────────────────────────────────────────
        d1 = QFrame()
        d1.setFrameShape(QFrame.Shape.HLine)
        d1.setObjectName("divider")
        card_layout.addWidget(d1)
        
        # ── API Key 区域 ─────────────────────────────────────────
        key_section = QLabel("API Key")
        key_section.setObjectName("sectionTitle")
        card_layout.addWidget(key_section)
        
        key_hint = QLabel("请输入您的 DeepSeek API Key（以 sk- 开头）")
        key_hint.setObjectName("hintLabel")
        card_layout.addWidget(key_hint)
        
        # Key 输入框
        self._key_input = QLineEdit()
        self._key_input.setObjectName("keyInput")
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        # 密码模式：输入时可见，但界面上会显示遮罩字符
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setMinimumHeight(40)
        card_layout.addWidget(self._key_input)
        
        # 显示/隐藏 Key 复选框
        self._show_key_check = QCheckBox("显示 Key 内容")
        self._show_key_check.setObjectName("showKeyCheck")
        self._show_key_check.toggled.connect(self._toggle_key_visibility)
        card_layout.addWidget(self._show_key_check)
        
        # 验证 + 保存按钮行
        key_btn_row = QHBoxLayout()
        
        self._validate_btn = QPushButton("验证 Key")
        self._validate_btn.setObjectName("secondaryBtn")
        self._validate_btn.clicked.connect(self._on_validate_clicked)
        key_btn_row.addWidget(self._validate_btn)
        
        self._save_btn = QPushButton("保存 Key")
        self._save_btn.setObjectName("primaryBtn")
        self._save_btn.clicked.connect(self._on_save_clicked)
        key_btn_row.addWidget(self._save_btn)
        
        card_layout.addLayout(key_btn_row)
        
        # 清除 Key 按钮
        self._clear_btn = QPushButton("删除已保存的 Key")
        self._clear_btn.setObjectName("dangerBtn")
        self._clear_btn.clicked.connect(self._on_clear_clicked)
        card_layout.addWidget(self._clear_btn)
        
        # ── 分隔线 ───────────────────────────────────────────────
        d2 = QFrame()
        d2.setFrameShape(QFrame.Shape.HLine)
        d2.setObjectName("divider")
        card_layout.addWidget(d2)
        
        # ── 验证/操作状态消息 ────────────────────────────────────
        self._status_msg = QLabel("")
        self._status_msg.setObjectName("statusMsg")
        self._status_msg.setWordWrap(True)
        self._status_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._status_msg)
        
        card_layout.addStretch()
        
        # 应用样式
        self._apply_styles()
    
    def _apply_styles(self):
        """应用与主窗口一致的液态玻璃风格。"""
        card_bg = card_background_rgba()
        self.setStyleSheet(f"""
            QFrame#settingsCard {{
                background: {card_bg};
                border-radius: 20px;
                border: 1px solid rgba(138, 115, 255, 0.22);
            }}
            QLabel#settingsTitle {{
                color: rgba(255, 255, 255, 0.88);
                font-size: 15px;
                font-weight: 500;
            }}
            QLabel#sectionTitle {{
                color: rgba(255, 255, 255, 0.72);
                font-size: 13px;
                font-weight: 500;
            }}
            QLabel#hintLabel {{
                color: rgba(255, 255, 255, 0.34);
                font-size: 11px;
            }}
            {input_qss()}
            QCheckBox#showKeyCheck {{
                color: rgba(255, 255, 255, 0.40);
                font-size: 11px;
            }}
            {primary_btn_qss()}
            {secondary_btn_qss()}
            {danger_btn_qss()}
            {close_btn_qss()}
            {divider_qss()}
            QLabel#statusMsg {{
                font-size: 12px;
            }}
        """)
    
    def paintEvent(self, event):
        """绘制多层液态玻璃光晕 + 磨砂纹理。"""
        painter = QPainter(self)
        draw_glass_glow(painter, self.width(), self.height())

        if self._noise_texture is None:
            self._noise_texture = create_noise_pixmap()
        painter.drawTiledPixmap(self.rect(), self._noise_texture)

        painter.end()
    
    def _load_current_settings(self):
        """加载已保存的 Key（脱敏显示在输入框中）。"""
        existing_key = load_api_key()
        if existing_key:
            # 输入框用占位符提示已有 Key（不显示实际值）
            self._key_input.setPlaceholderText(
                f"已保存（末4位：...{existing_key[-4:]}），留空则不修改"
            )
    
    def _toggle_key_visibility(self, visible: bool):
        """切换 Key 显示/隐藏。"""
        if visible:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
    
    def _on_validate_clicked(self):
        """验证 Key 按钮：在独立线程中验证，不阻塞 UI。"""
        raw_key = self._key_input.text().strip()
        
        if not raw_key:
            # 如果没输入新 Key，验证已保存的 Key
            existing = load_api_key()
            if existing:
                raw_key = existing
            else:
                self._show_status("请先输入 API Key", error=True)
                return
        
        self._validate_btn.setEnabled(False)
        self._show_status("正在验证...", error=False)
        
        # 在独立线程中验证
        self._thread = QThread(self)
        self._worker = ValidateWorker(raw_key)
        self._worker.moveToThread(self._thread)
        
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_validate_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        
        self._thread.start()
    
    def _on_validate_done(self, result: ApiResult, api_key: str):
        """验证完成回调。"""
        self._validate_btn.setEnabled(True)
        
        if result.success:
            self._show_status("✓ API Key 有效！可以保存", error=False)
            self._save_btn.setEnabled(True)
        else:
            self._show_status(f"✗ {result.error}", error=True)
    
    def _on_save_clicked(self):
        """保存 API Key 到系统凭据管理器。"""
        raw_key = self._key_input.text().strip()
        
        if not raw_key:
            self._show_status("请输入 API Key 后再保存", error=True)
            return
        
        # 基本格式验证
        if not raw_key.startswith("sk-"):
            self._show_status("API Key 格式不正确，应以 sk- 开头", error=True)
            return
        
        # 调用 keyring 加密保存
        if save_api_key(raw_key):
            # 清空输入框（安全考虑，不在内存中保留）
            self._key_input.clear()
            self._key_input.setPlaceholderText(
                f"已保存（末4位：...{raw_key[-4:]}），留空则不修改"
            )
            
            # 清除局部变量
            del raw_key
            
            self._show_status("✓ API Key 已加密保存到系统凭据管理器", error=False)
            
            # 通知主窗口刷新 Key 显示并重新获取余额
            self.settings_saved.emit()
        else:
            self._show_status("保存失败，请重试", error=True)
    
    def _on_clear_clicked(self):
        """删除已保存的 API Key。"""
        if delete_api_key():
            self._key_input.clear()
            self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
            self._show_status("✓ API Key 已删除", error=False)
            self.settings_saved.emit()
        else:
            self._show_status("删除失败", error=True)
    
    def _show_status(self, msg: str, error: bool = False):
        """显示状态提示。"""
        self._status_msg.setText(msg)
        if error:
            self._status_msg.setStyleSheet("color: #f87171; font-size: 12px;")
        else:
            self._status_msg.setStyleSheet("color: #86efac; font-size: 12px;")
    
    # ── 拖动支持 ─────────────────────────────────────────────────
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        self._drag_pos = None
    
    def closeEvent(self, event):
        """关闭时隐藏而不销毁。"""
        event.ignore()
        self.hide()
    
    def show_centered(self):
        """居中显示设置窗口。"""
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.center().x() - self.width() // 2
        y = screen.center().y() - self.height() // 2
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
