"""
main_window.py - 液态玻璃风格主窗口
--------------------------------------
实现余额展示、刷新、充值跳转等核心功能。
UI 风格：深色背景 + 白色半透明卡片 + 模糊光晕，模拟液态玻璃效果。

窗口行为：
  - 无边框、无任务栏图标（Popup 模式）
  - 点击窗口外部自动隐藏
  - 弹出时定位在任务栏图标附近（由 tray.py 调用 show_at 控制位置）
"""

import webbrowser
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QApplication
)
from PyQt6.QtCore import (
    Qt, QPoint, QTimer, QThread, pyqtSignal, QObject
)
from PyQt6.QtGui import QPainter, QPixmap

from core.api_client import fetch_balance, BalanceInfo, ApiResult
from core.key_manager import has_api_key, get_masked_key
from core.scheduler import RefreshScheduler
from ui.styles import (
    card_background_rgba, draw_glass_glow, create_noise_pixmap,
    divider_qss, close_btn_qss, primary_btn_qss, secondary_btn_qss,
    icon_btn_qss, GREEN, YELLOW, RED
)

logger = logging.getLogger(__name__)

# DeepSeek 官方充值页面地址
TOPUP_URL = "https://platform.deepseek.com/top_up"


# ─── 后台 API 请求工作线程 ──────────────────────────────────────────────────

class FetchWorker(QObject):
    """
    在独立线程中执行 API 请求，避免阻塞 UI 主线程。
    
    信号:
        finished(ApiResult): 请求完成，携带结果
    """
    finished = pyqtSignal(object)   # 携带 ApiResult 对象
    
    def run(self):
        """执行 API 请求（在工作线程中调用）。"""
        result = fetch_balance()
        self.finished.emit(result)


# ─── 主窗口 ────────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    """
    DeepSeek 余额监控主窗口。
    液态玻璃风格，无边框弹出式。
    """
    
    # 通知 tray 打开设置窗口的信号
    open_settings_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 窗口尺寸
        self.setFixedSize(360, 440)
        
        # 窗口标志：无边框 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        
        # 背景透明（由 paintEvent 自己绘制背景）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 拖动窗口支持
        self._drag_pos = None
        
        # 当前余额数据缓存
        self._last_balance: BalanceInfo | None = None
        
        # 是否正在加载
        self._is_loading = False
        
        # 工作线程（用于异步请求）
        self._thread = None
        self._worker = None
        
        # 磨砂纹理（lazy init，首次 paintEvent 时创建）
        self._noise_texture: QPixmap | None = None
        
        # 构建 UI
        self._init_ui()
        
        # 初始化定时刷新调度器（5分钟）
        self._scheduler = RefreshScheduler(interval_ms=5 * 60 * 1000, parent=self)
        self._scheduler.refresh_requested.connect(self._do_refresh)
        self._scheduler.start()
    
    # ── UI 构建 ────────────────────────────────────────────────────────
    
    def _init_ui(self):
        """构建窗口所有 UI 元素。"""
        # 主布局，留出外边距给圆角和阴影
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)
        
        # 内容容器（真正的"卡片"）
        self._card = QFrame(self)
        self._card.setObjectName("card")
        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(22, 20, 22, 18)
        card_layout.setSpacing(0)
        outer.addWidget(self._card)
        
        # ── 标题栏 ──────────────────────────────────────────────────
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        
        # 左侧 Logo 圆圈
        self._logo = QLabel("D")
        self._logo.setFixedSize(38, 38)
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setObjectName("logo")
        title_row.addWidget(self._logo)
        
        # 标题和副标题
        title_info = QVBoxLayout()
        title_info.setSpacing(1)
        self._title_label = QLabel("DeepSeek 余额监控")
        self._title_label.setObjectName("titleLabel")
        self._subtitle_label = QLabel("上次更新：--")
        self._subtitle_label.setObjectName("subtitleLabel")
        title_info.addWidget(self._title_label)
        title_info.addWidget(self._subtitle_label)
        title_row.addLayout(title_info)
        
        title_row.addStretch()
        
        # 刷新按钮
        self._refresh_btn = QPushButton("↻")
        self._refresh_btn.setFixedSize(30, 30)
        self._refresh_btn.setObjectName("iconBtn")
        self._refresh_btn.setToolTip("手动刷新")
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        title_row.addWidget(self._refresh_btn)
        
        # 关闭按钮
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(30, 30)
        self._close_btn.setObjectName("closeBtn")
        self._close_btn.setToolTip("隐藏到托盘")
        self._close_btn.clicked.connect(self.hide)
        title_row.addWidget(self._close_btn)
        
        card_layout.addLayout(title_row)
        card_layout.addSpacing(18)
        
        # ── 余额区域 ────────────────────────────────────────────────
        self._balance_label_text = QLabel("可用余额")
        self._balance_label_text.setObjectName("sectionLabel")
        card_layout.addWidget(self._balance_label_text)
        card_layout.addSpacing(4)
        
        self._balance_amount = QLabel("¥ --")
        self._balance_amount.setObjectName("balanceAmount")
        card_layout.addWidget(self._balance_amount)
        
        self._balance_detail = QLabel("充值余额 ¥-- · 赠送余额 ¥--")
        self._balance_detail.setObjectName("balanceDetail")
        card_layout.addWidget(self._balance_detail)
        
        card_layout.addSpacing(16)
        
        # ── 分隔线 ──────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setObjectName("divider")
        card_layout.addWidget(divider)
        card_layout.addSpacing(14)
        
        # ── 统计卡片行 ──────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)
        
        self._stat_topped = self._make_stat_card("充值余额", "¥--")
        self._stat_granted = self._make_stat_card("赠送余额", "¥--")
        self._stat_status = self._make_stat_card("账户状态", "--")
        
        stats_row.addWidget(self._stat_topped[0])
        stats_row.addWidget(self._stat_granted[0])
        stats_row.addWidget(self._stat_status[0])
        card_layout.addLayout(stats_row)
        card_layout.addSpacing(14)
        
        # ── API Key 状态栏 ──────────────────────────────────────────
        key_frame = QFrame()
        key_frame.setObjectName("keyFrame")
        key_layout = QHBoxLayout(key_frame)
        key_layout.setContentsMargins(12, 8, 12, 8)
        key_layout.setSpacing(8)
        
        # 绿色指示点（用 QLabel 模拟）
        self._key_dot = QLabel("●")
        self._key_dot.setObjectName("keyDot")
        self._key_dot.setFixedWidth(12)
        key_layout.addWidget(self._key_dot)
        
        self._key_text = QLabel(get_masked_key())
        self._key_text.setObjectName("keyText")
        key_layout.addWidget(self._key_text, 1)
        
        self._key_lock = QLabel("🔒 已加密")
        self._key_lock.setObjectName("keyLock")
        key_layout.addWidget(self._key_lock)
        
        card_layout.addWidget(key_frame)
        card_layout.addSpacing(14)
        
        # ── 底部按钮行 ──────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        
        self._topup_btn = QPushButton("立即充值 →")
        self._topup_btn.setObjectName("primaryBtn")
        self._topup_btn.clicked.connect(self._on_topup_clicked)
        
        self._settings_btn = QPushButton("⚙ 设置")
        self._settings_btn.setObjectName("secondaryBtn")
        self._settings_btn.clicked.connect(self._on_settings_clicked)
        
        btn_row.addWidget(self._topup_btn)
        btn_row.addWidget(self._settings_btn)
        card_layout.addLayout(btn_row)
        
        # ── 状态提示（加载中/错误信息） ─────────────────────────────
        card_layout.addSpacing(10)
        self._status_msg = QLabel("")
        self._status_msg.setObjectName("statusMsg")
        self._status_msg.setWordWrap(True)
        self._status_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._status_msg)
        
        # ── 应用样式表 ───────────────────────────────────────────────
        self._apply_styles()
    
    def _make_stat_card(self, label_text: str, value_text: str):
        """
        创建一个小统计卡片（标签 + 数值），返回 (QFrame, value_label)。
        """
        frame = QFrame()
        frame.setObjectName("statCard")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(3)
        
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        
        value = QLabel(value_text)
        value.setObjectName("statValue")
        
        layout.addWidget(label)
        layout.addWidget(value)
        
        return frame, label, value
    
    def _apply_styles(self):
        """应用 QSS 样式表，实现液态玻璃视觉效果。"""
        card_bg = card_background_rgba()
        self.setStyleSheet(f"""
            /* ── 卡片主体（液态玻璃） ─────────────── */
            QFrame#card {{
                background: {card_bg};
                border-radius: 20px;
                border: 1px solid rgba(138, 115, 255, 0.22);
            }}
            
            /* ── Logo 圆圈 ───────────────────────────── */
            QLabel#logo {{
                background: rgba(99, 102, 241, 0.45);
                border-radius: 19px;
                border: 1px solid rgba(138, 115, 255, 0.30);
                color: white;
                font-size: 16px;
                font-weight: 500;
            }}
            
            /* ── 标题文字 ───────────────────────────── */
            QLabel#titleLabel {{
                color: rgba(255, 255, 255, 0.90);
                font-size: 14px;
                font-weight: 500;
            }}
            QLabel#subtitleLabel {{
                color: rgba(255, 255, 255, 0.36);
                font-size: 11px;
            }}
            
            {icon_btn_qss()}
            
            {close_btn_qss()}
            
            /* ── 分区标签 ──────────────────────────── */
            QLabel#sectionLabel {{
                color: rgba(255, 255, 255, 0.40);
                font-size: 11px;
                letter-spacing: 0.5px;
            }}
            
            /* ── 余额大数字 ─────────────────────────── */
            QLabel#balanceAmount {{
                color: white;
                font-size: 34px;
                font-weight: 500;
                letter-spacing: -1px;
            }}
            
            /* ── 余额详细 ───────────────────────────── */
            QLabel#balanceDetail {{
                color: rgba(255, 255, 255, 0.32);
                font-size: 11px;
                margin-top: 3px;
            }}
            
            {divider_qss()}
            
            /* ── 统计小卡片 ─────────────────────────── */
            QFrame#statCard {{
                background: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 12px;
            }}
            QLabel#statLabel {{
                color: rgba(255, 255, 255, 0.34);
                font-size: 10px;
            }}
            QLabel#statValue {{
                color: rgba(255, 255, 255, 0.80);
                font-size: 14px;
                font-weight: 500;
            }}
            
            /* ── API Key 状态栏 ─────────────────────── */
            QFrame#keyFrame {{
                background: rgba(255, 255, 255, 0.04);
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 10px;
            }}
            QLabel#keyDot {{
                color: {GREEN};
                font-size: 9px;
            }}
            QLabel#keyText {{
                color: rgba(255, 255, 255, 0.44);
                font-family: "Consolas", monospace;
                font-size: 12px;
            }}
            QLabel#keyLock {{
                color: rgba(255, 255, 255, 0.24);
                font-size: 11px;
            }}
            
            {primary_btn_qss()}
            
            {secondary_btn_qss()}
            
            /* ── 状态消息 ───────────────────────────── */
            QLabel#statusMsg {{
                color: rgba(255, 255, 255, 0.34);
                font-size: 11px;
            }}
        """)
    
    # ── 绘制背景（圆角 + 光晕效果） ────────────────────────────────
    
    def paintEvent(self, event):
        """绘制多层液态玻璃光晕 + 磨砂微纹理。"""
        painter = QPainter(self)
        draw_glass_glow(painter, self.width(), self.height())

        # 磨砂纹理叠加（稀疏噪点，模拟蚀刻玻璃）
        if self._noise_texture is None:
            self._noise_texture = create_noise_pixmap()
        painter.drawTiledPixmap(self.rect(), self._noise_texture)

        painter.end()
    
    # ── 数据更新逻辑 ──────────────────────────────────────────────
    
    def _do_refresh(self):
        """
        执行余额刷新：在独立线程中调用 API，防止 UI 卡顿。
        """
        if self._is_loading:
            return  # 避免重复请求
        
        if not has_api_key():
            self._show_status("请先在设置中填入 API Key", error=True)
            return
        
        self._is_loading = True
        self._set_loading_state(True)
        
        # 创建工作线程
        self._thread = QThread(self)
        self._worker = FetchWorker()
        self._worker.moveToThread(self._thread)
        
        # 连接信号
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_fetch_done)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)
        
        self._thread.start()
    
    def _on_fetch_done(self, result: ApiResult):
        """
        API 请求完成回调（由工作线程信号触发，在主线程执行）。
        
        参数:
            result: ApiResult 对象
        """
        self._is_loading = False
        self._set_loading_state(False)
        
        if result.success:
            self._last_balance = result.data
            self._update_ui(result.data)
            self._show_status("")  # 清空错误状态
            self._update_time_label()
            # 手动刷新后重置计时器，避免马上再次触发
            self._scheduler.restart()
        else:
            self._show_status(result.error or "刷新失败", error=True)
    
    def _update_ui(self, info: BalanceInfo):
        """
        用最新余额数据刷新所有 UI 元素。
        
        参数:
            info: 从 API 解析出的 BalanceInfo 数据
        """
        # 更新大余额数字
        self._balance_amount.setText(f"¥ {info.total_balance:.2f}")
        
        # 更新余额详细
        self._balance_detail.setText(
            f"充值余额 ¥{info.topped_up_balance:.2f} · "
            f"赠送余额 ¥{info.granted_balance:.2f}"
        )
        
        # 更新统计小卡片
        _, _, topped_val = self._stat_topped
        topped_val.setText(f"¥{info.topped_up_balance:.2f}")
        
        _, _, granted_val = self._stat_granted
        granted_val.setText(f"¥{info.granted_balance:.2f}")
        
        _, _, status_val = self._stat_status
        if info.is_available:
            status_val.setText("正常")
            status_val.setStyleSheet("color: #4ade80; font-size: 14px; font-weight: 500;")
        else:
            status_val.setText("受限")
            status_val.setStyleSheet("color: #f87171; font-size: 14px; font-weight: 500;")
        
        # 余额不足时标红
        if info.total_balance < 5.0:
            self._balance_amount.setStyleSheet(
                "color: #f87171; font-size: 34px; font-weight: 500;"
            )
        elif info.total_balance < 20.0:
            self._balance_amount.setStyleSheet(
                "color: #fbbf24; font-size: 34px; font-weight: 500;"
            )
        else:
            self._balance_amount.setStyleSheet(
                "color: white; font-size: 34px; font-weight: 500;"
            )
        
        # 更新 Key 脱敏显示
        self._key_text.setText(get_masked_key())
        self._key_dot.setStyleSheet("color: #4ade80; font-size: 9px;")
    
    def _update_time_label(self):
        """更新"上次更新时间"标签。"""
        from datetime import datetime
        now = datetime.now().strftime("%H:%M:%S")
        self._subtitle_label.setText(f"上次更新：{now}")
    
    def _set_loading_state(self, loading: bool):
        """控制加载状态：刷新按钮旋转动画 + 禁用交互。"""
        self._refresh_btn.setEnabled(not loading)
        if loading:
            self._refresh_btn.setText("⟳")
            self._show_status("正在获取数据...")
        else:
            self._refresh_btn.setText("↻")
    
    def _show_status(self, msg: str, error: bool = False):
        """
        在底部显示状态提示文字。
        
        参数:
            msg: 提示内容，空字符串则隐藏
            error: True 则以红色显示（错误状态）
        """
        self._status_msg.setText(msg)
        if error:
            self._status_msg.setStyleSheet("color: #f87171; font-size: 11px;")
        else:
            self._status_msg.setStyleSheet("color: rgba(255,255,255,0.38); font-size: 11px;")
    
    # ── 事件处理 ──────────────────────────────────────────────────
    
    def _on_refresh_clicked(self):
        """刷新按钮点击。"""
        self._do_refresh()
    
    def _on_topup_clicked(self):
        """充值按钮：在默认浏览器打开 DeepSeek 充值页面。"""
        webbrowser.open(TOPUP_URL)
    
    def _on_settings_clicked(self):
        """设置按钮：发出信号，由托盘管理器打开设置窗口。"""
        self.open_settings_requested.emit()
    
    def show_at(self, pos: QPoint):
        """
        在指定位置附近弹出窗口（由 tray.py 调用）。
        自动调整位置，确保不超出屏幕边界。
        
        参数:
            pos: 目标位置（通常是托盘图标坐标）
        """
        # 获取当前屏幕尺寸
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 默认在鼠标右上方弹出
        x = pos.x() - self.width() // 2
        y = pos.y() - self.height() - 10
        
        # 边界修正：不超出屏幕左右
        x = max(screen.left() + 8, min(x, screen.right() - self.width() - 8))
        
        # 边界修正：如果上方空间不足，弹到下方
        if y < screen.top() + 8:
            y = pos.y() + 10
        
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        
        # 首次弹出时自动刷新一次
        if self._last_balance is None:
            QTimer.singleShot(200, self._do_refresh)
    
    def mousePressEvent(self, event):
        """支持拖动窗口（因为是无边框窗口）。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
    
    def mouseMoveEvent(self, event):
        """拖动窗口移动。"""
        if (event.buttons() == Qt.MouseButton.LeftButton and 
                self._drag_pos is not None):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
    
    def mouseReleaseEvent(self, event):
        """释放拖动。"""
        self._drag_pos = None
    
    def closeEvent(self, event):
        """关闭事件：隐藏而不是真正退出（保持托盘常驻）。"""
        event.ignore()
        self.hide()
    
    def refresh_key_display(self):
        """设置 Key 后刷新 Key 显示（由设置窗口关闭时调用）。"""
        self._key_text.setText(get_masked_key())
        # Key 更新后立刻刷新余额
        self._do_refresh()
