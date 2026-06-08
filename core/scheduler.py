"""
scheduler.py - 定时刷新调度器
-------------------------------
负责每隔固定时间自动调用 API 刷新余额，
并通过 PyQt6 信号机制通知 UI 更新，保证线程安全。
"""

import logging
from PyQt6.QtCore import QObject, QTimer, pyqtSignal   # Qt 定时器，运行在主线程

logger = logging.getLogger(__name__)

# 默认刷新间隔（毫秒），5分钟 = 300_000 ms
DEFAULT_INTERVAL_MS = 5 * 60 * 1000


class RefreshScheduler(QObject):
    """
    余额定时刷新调度器。
    
    使用 Qt 的 QTimer（运行在 Qt 事件循环内），避免多线程竞争。
    当定时器触发时发出 refresh_requested 信号，由 UI 层负责实际 API 调用。
    
    信号:
        refresh_requested: 到达刷新时间，通知外部执行刷新
    """
    
    # 自定义信号：需要刷新时发出，由主窗口连接并响应
    refresh_requested = pyqtSignal()
    
    def __init__(self, interval_ms: int = DEFAULT_INTERVAL_MS, parent=None):
        """
        初始化调度器。
        
        参数:
            interval_ms: 刷新间隔（毫秒），默认5分钟
            parent: Qt 父对象
        """
        super().__init__(parent)
        
        self._interval_ms = interval_ms
        
        # 创建 Qt 定时器（默认为重复触发模式）
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)        # 设置触发间隔
        self._timer.timeout.connect(self._on_timer) # 定时器触发时调用内部方法
        
        logger.info(f"调度器初始化，刷新间隔: {interval_ms // 1000}秒")
    
    def start(self):
        """启动定时器，开始周期性刷新。"""
        self._timer.start()
        logger.info("定时刷新调度器已启动")
    
    def stop(self):
        """停止定时器。"""
        self._timer.stop()
        logger.info("定时刷新调度器已停止")
    
    def restart(self):
        """重新启动定时器（用于手动刷新后重置计时，避免马上再次触发）。"""
        self._timer.stop()
        self._timer.start()
    
    def set_interval(self, interval_ms: int):
        """
        修改刷新间隔。
        
        参数:
            interval_ms: 新的间隔（毫秒）
        """
        self._interval_ms = interval_ms
        was_active = self._timer.isActive()
        self._timer.setInterval(interval_ms)
        if was_active:
            # 如果之前在运行，重启以使新间隔生效
            self._timer.stop()
            self._timer.start()
        logger.info(f"刷新间隔已更新为: {interval_ms // 1000}秒")
    
    def is_running(self) -> bool:
        """返回定时器是否正在运行。"""
        return self._timer.isActive()
    
    def _on_timer(self):
        """
        定时器触发时的内部回调，发出 refresh_requested 信号。
        由 Qt 事件循环在主线程中调用，线程安全。
        """
        logger.debug("定时刷新触发")
        self.refresh_requested.emit()
