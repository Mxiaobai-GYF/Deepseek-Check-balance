"""
main.py - 程序入口
-------------------
DeepSeek 余额监控工具启动入口。

启动流程：
  1. 配置日志
  2. 生成托盘图标（如不存在）
  3. 创建 Qt 应用（设置高 DPI 和深色风格）
  4. 创建主窗口 + 设置窗口
  5. 创建托盘管理器
  6. 检查是否已设置 API Key，若无则自动弹出设置窗口
  7. 进入 Qt 事件循环

打包命令（生成单文件 exe）：
  pyinstaller --onefile --windowed --icon=assets/icon.ico --name=DeepSeekMonitor main.py
"""

import sys
import os
import logging

# ── 日志配置 ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# ── 添加项目根目录到 Python 路径 ────────────────────────────────────────────
# 确保在打包后也能正确找到各模块
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ── Qt 应用初始化 ───────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont

# 设置应用元信息（在创建 QApplication 之前）
QCoreApplication.setApplicationName("DeepSeekMonitor")
QCoreApplication.setOrganizationName("DeepSeekTools")
QCoreApplication.setApplicationVersion("1.0.0")


def get_icon() -> QIcon:
    """
    加载托盘图标。
    优先使用 assets/icon.ico，若不存在则用代码动态生成。
    
    返回:
        QIcon 对象
    """
    icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")
    
    # 如果图标文件不存在，先生成
    if not os.path.exists(icon_path):
        logger.info("图标文件不存在，正在生成...")
        try:
            # 动态运行图标生成脚本
            generate_script = os.path.join(BASE_DIR, "generate_icon.py")
            if os.path.exists(generate_script):
                import subprocess
                subprocess.run(
                    [sys.executable, generate_script],
                    check=True, capture_output=True
                )
        except Exception as e:
            logger.warning(f"生成图标文件失败: {e}，将使用内置图标")
    
    # 尝试从文件加载
    if os.path.exists(icon_path):
        return QIcon(icon_path)
    
    # 回退：用 Qt 绘制内置图标（不依赖任何文件）
    return _create_fallback_icon()


def _create_fallback_icon() -> QIcon:
    """
    在内存中绘制一个简单的托盘图标（不需要 Pillow 或外部文件）。
    
    返回:
        QIcon 对象
    """
    size = 64
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 深紫色圆形背景
    painter.setBrush(QColor(22, 18, 75))
    painter.setPen(QColor(99, 102, 241, 180))
    painter.drawEllipse(2, 2, size - 4, size - 4)
    
    # 白色 "D" 字母
    font = QFont("Segoe UI", 30, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 230))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "D")
    
    painter.end()
    
    return QIcon(pixmap)


def main():
    """程序主入口函数。"""
    
    # ── 创建 Qt 应用 ─────────────────────────────────────────────
    app = QApplication(sys.argv)
    
    # 不在任务栏显示主应用图标（只在托盘显示）
    app.setQuitOnLastWindowClosed(False)
    
    # 检查系统托盘是否可用（在某些 Linux 桌面环境下可能不支持）
    from PyQt6.QtWidgets import QSystemTrayIcon
    if not QSystemTrayIcon.isSystemTrayAvailable():
        logger.error("当前系统不支持系统托盘，程序无法运行")
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "启动失败",
            "当前系统不支持系统托盘图标，程序无法正常运行。\n"
            "请确认您的 Windows 系统版本（需要 Windows 7 及以上）。"
        )
        return 1
    
    # ── 加载图标 ─────────────────────────────────────────────────
    icon = get_icon()
    
    # ── 创建窗口 ─────────────────────────────────────────────────
    from ui.main_window import MainWindow
    from ui.settings_window import SettingsWindow
    from tray import TrayManager
    from core.key_manager import has_api_key
    
    logger.info("正在初始化窗口...")
    
    main_window = MainWindow()
    settings_window = SettingsWindow()
    
    # 设置窗口图标
    main_window.setWindowIcon(icon)
    settings_window.setWindowIcon(icon)
    
    # ── 创建托盘管理器 ───────────────────────────────────────────
    tray_manager = TrayManager(
        icon=icon,
        main_window=main_window,
        settings_window=settings_window
    )
    
    # ── 首次运行检查 ─────────────────────────────────────────────
    if not has_api_key():
        # 首次使用，自动弹出设置窗口让用户输入 API Key
        logger.info("未检测到 API Key，弹出设置窗口")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, settings_window.show_centered)
    else:
        # 已有 Key，弹出主窗口显示余额
        logger.info("检测到 API Key，启动完成")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: main_window.show_at(
            QApplication.primaryScreen().availableGeometry().bottomRight()
        ))
    
    logger.info("DeepSeek 余额监控已启动，图标在系统托盘中")
    
    # ── 进入事件循环 ─────────────────────────────────────────────
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
