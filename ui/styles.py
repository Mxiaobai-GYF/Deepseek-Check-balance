"""
styles.py — 液态玻璃共享样式与绘制工具
------------------------------------------
集中管理颜色、透明度、光晕绘制、QSS 模板。
主窗口和设置窗口共用此模块，确保视觉完全一致。
"""

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QColor, QPainter, QRadialGradient, QLinearGradient,
    QBrush, QPen, QPainterPath, QFont
)


# ═══════════════════════════════════════════════════════════════════════════
# 颜色常量 — 液态玻璃调色板
# ═══════════════════════════════════════════════════════════════════════════

# 卡片背景（深紫蓝，半透明 — 核心液态感）
CARD_BG_R = 14
CARD_BG_G = 11
CARD_BG_B = 36
CARD_BG_ALPHA = 0.82          # 透明度：既可见玻璃质感，又不透视桌面

# 边框虹彩颜色
BORDER_PURPLE = QColor(138, 115, 255, 90)   # 左上紫
BORDER_BLUE   = QColor(72, 159, 255, 85)    # 右下蓝
BORDER_CYAN   = QColor(56, 220, 240, 50)    # 点缀青

# 光晕颜色
GLOW_PURPLE   = QColor(114, 90, 255, 70)    # 左上紫色光晕
GLOW_BLUE     = QColor(56, 140, 255, 55)    # 右下蓝色光晕
GLOW_CYAN     = QColor(45, 210, 230, 30)    # 中心青色微光

# 内高光（玻璃厚度感）
HIGHLIGHT_WHITE = QColor(255, 255, 255, 18)

# 文字颜色
TEXT_PRIMARY   = "rgba(255, 255, 255, 0.92)"
TEXT_SECONDARY = "rgba(255, 255, 255, 0.62)"
TEXT_HINT      = "rgba(255, 255, 255, 0.38)"
TEXT_DIM       = "rgba(255, 255, 255, 0.22)"

# 强调色（靛蓝）
ACCENT        = QColor(99, 102, 241)
ACCENT_LIGHT  = QColor(129, 132, 255)
ACCENT_HOVER  = "rgba(99, 102, 241, 0.50)"
ACCENT_ACTIVE = "rgba(99, 102, 241, 0.70)"
ACCENT_BORDER = "rgba(99, 102, 241, 0.55)"

# 危险色
DANGER        = QColor(220, 38, 38)
DANGER_HOVER  = "rgba(220, 38, 38, 0.55)"
DANGER_TEXT   = "rgba(248, 113, 113, 0.80)"

# 状态色
GREEN  = "#4ade80"
YELLOW = "#fbbf24"
RED    = "#f87171"


# ═══════════════════════════════════════════════════════════════════════════
# 绘制函数
# ═══════════════════════════════════════════════════════════════════════════

def card_background_rgba() -> str:
    """卡片背景色 QSS 字符串。"""
    r, g, b = CARD_BG_R, CARD_BG_G, CARD_BG_B
    a = CARD_BG_ALPHA
    return f"rgba({r}, {g}, {b}, {a:.2f})"


def draw_glass_glow(painter: QPainter, width: int, height: int,
                    margin: int = 12):
    """
    在透明背景上绘制液态玻璃光晕（paintEvent 调用）。
    
    四层叠加：
      1. 左上大面积紫色光晕
      2. 右下中等蓝色光晕
      3. 中心偏上微青色光晕
      4. 卡片顶部内高光（模拟玻璃厚度）
    """
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    w, h, m = width, height, margin

    # 层 1：左上紫色光晕（大面积）
    g1 = QRadialGradient(QPointF(m + 70, m + 60), 160, QPointF(m + 40, m + 30))
    g1.setColorAt(0.0, GLOW_PURPLE)
    g1.setColorAt(0.5, QColor(114, 90, 255, 35))
    g1.setColorAt(1.0, QColor(114, 90, 255, 0))
    painter.fillRect(0, 0, w, h, QBrush(g1))

    # 层 2：右下蓝色光晕
    g2 = QRadialGradient(QPointF(w - m - 70, h - m - 70), 140, QPointF(w - m - 40, h - m - 40))
    g2.setColorAt(0.0, GLOW_BLUE)
    g2.setColorAt(0.5, QColor(56, 140, 255, 28))
    g2.setColorAt(1.0, QColor(56, 140, 255, 0))
    painter.fillRect(0, 0, w, h, QBrush(g2))

    # 层 3：中心偏上青色微光（增加"流动"感）
    g3 = QRadialGradient(QPointF(w * 0.45, h * 0.28), 100)
    g3.setColorAt(0.0, GLOW_CYAN)
    g3.setColorAt(0.6, QColor(45, 210, 230, 8))
    g3.setColorAt(1.0, QColor(45, 210, 230, 0))
    painter.fillRect(0, 0, w, h, QBrush(g3))

    # 层 4：顶部内高光椭圆（模拟玻璃厚度折射）
    highlight_path = QPainterPath()
    highlight_path.addRoundedRect(m + 2, m + 2, w - 2*m - 4, (h - 2*m) * 0.45,
                                  16, 16)
    h_grad = QLinearGradient(QPointF(0, m), QPointF(0, m + (h - 2*m) * 0.45))
    h_grad.setColorAt(0.0, HIGHLIGHT_WHITE)
    h_grad.setColorAt(0.7, QColor(255, 255, 255, 6))
    h_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    painter.fillPath(highlight_path, QBrush(h_grad))


def create_noise_pixmap(size: int = 256) -> 'QPixmap':
    """
    生成磨砂玻璃微纹理（仅在首次调用时创建，后续缓存）。
    使用 QPixmap + QPainter 绘制随机像素点，模拟磨砂质感。
    """
    from PyQt6.QtGui import QPixmap
    import random
    # 固定种子确保每次一致
    rng = random.Random(42)

    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    # 稀疏的半透明白点
    for _ in range(size * 4):
        x = rng.randint(0, size - 1)
        y = rng.randint(0, size - 1)
        a = rng.randint(0, 8)          # 极低透明度
        painter.setPen(QColor(255, 255, 255, a))
        painter.drawPoint(x, y)
    painter.end()

    return pixmap


# ═══════════════════════════════════════════════════════════════════════════
# 通用 QSS 片段
# ═══════════════════════════════════════════════════════════════════════════

def card_qss(object_name: str) -> str:
    """卡片容器基础样式。"""
    bg = card_background_rgba()
    return f"""
        {object_name} {{
            background: {bg};
            border-radius: 20px;
            border: 1px solid rgba(138, 115, 255, 0.25);
        }}
    """


def divider_qss() -> str:
    """分隔线样式。"""
    return """
        QFrame#divider {
            background: rgba(255, 255, 255, 0.08);
            border: none;
            max-height: 1px;
        }
    """


def close_btn_qss() -> str:
    """关闭按钮样式。"""
    return """
        QPushButton#closeBtn {
            background: transparent;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.10);
            color: rgba(255, 255, 255, 0.35);
            font-size: 16px;
        }
        QPushButton#closeBtn:hover {
            background: rgba(220, 50, 50, 0.50);
            border-color: rgba(220, 50, 50, 0.55);
            color: white;
        }
    """


def primary_btn_qss() -> str:
    """主要按钮（充值/保存）。"""
    return """
        QPushButton#primaryBtn {
            background: rgba(99, 102, 241, 0.25);
            border: 1px solid rgba(99, 102, 241, 0.50);
            border-radius: 10px;
            color: rgba(255, 255, 255, 0.85);
            font-size: 13px;
            font-weight: 500;
            padding: 9px 0;
        }
        QPushButton#primaryBtn:hover {
            background: rgba(99, 102, 241, 0.45);
            border-color: rgba(129, 132, 255, 0.75);
            color: white;
        }
        QPushButton#primaryBtn:pressed {
            background: rgba(99, 102, 241, 0.65);
        }
    """


def secondary_btn_qss() -> str:
    """次要按钮（设置/验证）。"""
    return """
        QPushButton#secondaryBtn {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 10px;
            color: rgba(255, 255, 255, 0.55);
            font-size: 13px;
            padding: 9px 0;
        }
        QPushButton#secondaryBtn:hover {
            background: rgba(255, 255, 255, 0.14);
            border-color: rgba(255, 255, 255, 0.25);
            color: rgba(255, 255, 255, 0.88);
        }
        QPushButton#secondaryBtn:pressed {
            background: rgba(255, 255, 255, 0.22);
        }
    """


def danger_btn_qss() -> str:
    """危险按钮（删除 Key）。"""
    return """
        QPushButton#dangerBtn {
            background: rgba(220, 38, 38, 0.12);
            border: 1px solid rgba(220, 38, 38, 0.30);
            border-radius: 9px;
            color: rgba(248, 113, 113, 0.75);
            font-size: 12px;
            padding: 7px 0;
        }
        QPushButton#dangerBtn:hover {
            background: rgba(220, 38, 38, 0.25);
            border-color: rgba(220, 38, 38, 0.50);
            color: #fca5a5;
        }
    """


def icon_btn_qss() -> str:
    """图标按钮（刷新）。"""
    return """
        QPushButton#iconBtn {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.16);
            color: rgba(255, 255, 255, 0.60);
            font-size: 16px;
        }
        QPushButton#iconBtn:hover {
            background: rgba(255, 255, 255, 0.20);
            border-color: rgba(255, 255, 255, 0.30);
            color: white;
        }
        QPushButton#iconBtn:pressed {
            background: rgba(99, 102, 241, 0.40);
        }
    """


def input_qss() -> str:
    """输入框样式。"""
    return """
        QLineEdit#keyInput {
            background: rgba(255, 255, 255, 0.07);
            border: 1px solid rgba(255, 255, 255, 0.16);
            border-radius: 10px;
            color: rgba(255, 255, 255, 0.82);
            font-family: "Consolas", monospace;
            font-size: 12px;
            padding: 8px 14px;
        }
        QLineEdit#keyInput:focus {
            border: 1px solid rgba(99, 102, 241, 0.60);
            background: rgba(255, 255, 255, 0.10);
        }
    """


def tray_menu_qss() -> str:
    """托盘右键菜单样式。"""
    return """
        QMenu {
            background: rgba(16, 13, 40, 0.95);
            border: 1px solid rgba(138, 115, 255, 0.22);
            border-radius: 12px;
            padding: 5px 0;
            color: rgba(255, 255, 255, 0.82);
            font-size: 13px;
        }
        QMenu::item {
            padding: 8px 24px 8px 16px;
            border-radius: 7px;
            margin: 2px 5px;
        }
        QMenu::item:selected {
            background: rgba(99, 102, 241, 0.40);
            color: white;
        }
        QMenu::separator {
            height: 1px;
            background: rgba(255, 255, 255, 0.08);
            margin: 5px 8px;
        }
    """
