"""
generate_icon.py - 图标生成脚本
----------------------------------
使用 Pillow 绘制托盘图标（.ico 格式），无需外部图片素材。
图标设计：深紫蓝色背景圆形 + 白色 "D" 字母，简洁美观。

运行方式：python generate_icon.py
生成文件：assets/icon.ico
"""

import sys
import os

# 确保脚本可以从项目根目录运行
script_dir = os.path.dirname(os.path.abspath(__file__))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("正在安装 Pillow...")
    os.system(f"{sys.executable} -m pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont


def create_icon(size: int = 64) -> Image.Image:
    """
    绘制一个圆形图标。
    
    参数:
        size: 图标边长（像素）
    返回:
        PIL Image 对象
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))  # 透明背景
    draw = ImageDraw.Draw(img)
    
    padding = 2
    # 绘制深紫色圆形背景
    draw.ellipse(
        [padding, padding, size - padding, size - padding],
        fill=(22, 18, 75, 255),          # 深紫蓝色
        outline=(99, 102, 241, 200),     # 半透明紫色边框
        width=max(1, size // 20)
    )
    
    # 在圆心绘制 "D" 字母
    letter = "D"
    font_size = int(size * 0.52)
    
    # 尝试使用系统字体，失败则使用默认字体
    font = None
    font_paths = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, font_size)
                break
            except Exception:
                continue
    
    if font is None:
        font = ImageFont.load_default()
    
    # 计算文字居中位置
    bbox = draw.textbbox((0, 0), letter, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2 - bbox[0]
    y = (size - text_h) / 2 - bbox[1]
    
    # 绘制白色字母
    draw.text((x, y), letter, fill=(255, 255, 255, 240), font=font)
    
    return img


def generate_ico(output_path: str):
    """
    生成多尺寸 .ico 文件（Windows 图标格式支持多尺寸）。
    
    参数:
        output_path: 输出文件路径
    """
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [create_icon(s) for s in sizes]
    
    # 以最大尺寸为基础，保存为多尺寸 ico
    images[0].save(
        output_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"图标已生成：{output_path}")


if __name__ == "__main__":
    output = os.path.join(script_dir, "assets", "icon.ico")
    os.makedirs(os.path.dirname(output), exist_ok=True)
    generate_ico(output)
