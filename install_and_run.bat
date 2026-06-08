@echo off
chcp 65001 > nul
echo ============================================
echo   DeepSeek 余额监控 - 安装和启动脚本
echo ============================================
echo.

:: 检查 Python 是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检查 Python 版本...
python --version

echo.
echo [2/3] 安装依赖库...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接后重试
    pause
    exit /b 1
)

echo.
echo [3/3] 生成图标资源...
python generate_icon.py

echo.
echo ============================================
echo   安装完成！正在启动程序...
echo   程序将在任务栏托盘区域显示图标
echo   点击图标即可查看余额
echo   本窗口可安全关闭
echo ============================================
echo.

start "" pythonw main.py
