"""
tray.py - 系统托盘管理器
--------------------------
负责：
  1. 在 Windows 任务栏注册托盘图标
  2. 响应左键单击（弹出/隐藏主窗口）
  3. 右键菜单：刷新 / 设置 / 退出
  4. 协调主窗口和设置窗口之间的通信

使用 PyQt6 内置的 QSystemTrayIcon，无需额外的 pystray 依赖。
"""

import logging
import sys
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu, QApplication
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QObject, QPoint
from ui.styles import tray_menu_qss

logger = logging.getLogger(__name__)


class TrayManager(QObject):
    """
    托盘图标管理器。
    
    持有主窗口和设置窗口的引用，处理所有托盘交互逻辑。
    """
    
    def __init__(self, icon: QIcon, main_window, settings_window, parent=None):
        """
        初始化托盘管理器。
        
        参数:
            icon: 托盘图标
            main_window: MainWindow 实例
            settings_window: SettingsWindow 实例
            parent: Qt 父对象
        """
        super().__init__(parent)
        
        self._main_window = main_window
        self._settings_window = settings_window
        
        # 创建系统托盘图标
        self._tray = QSystemTrayIcon(icon, parent=self)
        self._tray.setToolTip("DeepSeek 余额监控\n点击查看余额")
        
        # 构建右键菜单
        self._menu = self._create_menu()
        self._tray.setContextMenu(self._menu)
        
        # 左键单击 → 弹出/隐藏主窗口
        self._tray.activated.connect(self._on_tray_activated)
        
        # 连接主窗口的"打开设置"信号
        main_window.open_settings_requested.connect(self._show_settings)
        
        # 连接设置窗口的"已保存"信号
        settings_window.settings_saved.connect(main_window.refresh_key_display)
        
        # 显示托盘图标
        self._tray.show()
        logger.info("托盘图标已显示")
    
    def _create_menu(self) -> QMenu:
        """
        创建右键上下文菜单。
        
        菜单结构：
          查看余额
          ──────────
          手动刷新
          设置...
          ──────────
          退出
        """
        menu = QMenu()
        menu.setStyleSheet(tray_menu_qss())
        
        # 查看余额
        action_show = QAction("  查看余额", self)
        action_show.triggered.connect(self._show_main_window_at_tray)
        menu.addAction(action_show)
        
        menu.addSeparator()
        
        # 手动刷新
        action_refresh = QAction("  手动刷新", self)
        action_refresh.triggered.connect(self._on_refresh)
        menu.addAction(action_refresh)
        
        # 设置
        action_settings = QAction("  设置...", self)
        action_settings.triggered.connect(self._show_settings)
        menu.addAction(action_settings)
        
        menu.addSeparator()
        
        # 退出
        action_quit = QAction("  退出", self)
        action_quit.triggered.connect(self._on_quit)
        menu.addAction(action_quit)
        
        return menu
    
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason):
        """
        托盘图标激活事件处理。
        
        参数:
            reason: 激活原因（单击/双击/右键等）
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # 左键单击：切换主窗口显示/隐藏
            if self._main_window.isVisible():
                self._main_window.hide()
            else:
                self._show_main_window_at_tray()
        
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            # 双击：强制显示主窗口
            self._show_main_window_at_tray()
    
    def _show_main_window_at_tray(self):
        """
        在托盘图标附近弹出主窗口。
        获取托盘图标的屏幕位置，传给主窗口定位。
        """
        # 获取托盘图标的几何位置
        tray_geometry = self._tray.geometry()
        
        if tray_geometry.isValid():
            # 使用托盘图标中心位置
            pos = tray_geometry.center()
        else:
            # 回退方案：使用屏幕右下角附近
            screen = QApplication.primaryScreen().availableGeometry()
            pos = QPoint(screen.right() - 200, screen.bottom() - 50)
        
        self._main_window.show_at(pos)
    
    def _show_settings(self):
        """显示设置窗口。"""
        self._settings_window.show_centered()
    
    def _on_refresh(self):
        """从托盘菜单触发刷新。"""
        # 确保主窗口可见
        if not self._main_window.isVisible():
            self._show_main_window_at_tray()
        # 触发刷新
        self._main_window._do_refresh()
    
    def _on_quit(self):
        """退出程序。"""
        logger.info("用户从托盘菜单退出程序")
        # 隐藏托盘图标（避免程序退出后图标残留）
        self._tray.hide()
        QApplication.instance().quit()
    
    def show_notification(self, title: str, message: str, 
                          icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
                          duration_ms: int = 3000):
        """
        显示系统托盘通知气泡。
        
        参数:
            title: 通知标题
            message: 通知内容
            icon: 通知类型图标
            duration_ms: 显示时长（毫秒）
        """
        self._tray.showMessage(title, message, icon, duration_ms)
    
    def update_tooltip(self, balance_text: str):
        """
        更新托盘图标悬停提示（显示当前余额）。
        
        参数:
            balance_text: 余额文本，例如 "¥42.80"
        """
        self._tray.setToolTip(f"DeepSeek 余额监控\n当前余额：{balance_text}")
