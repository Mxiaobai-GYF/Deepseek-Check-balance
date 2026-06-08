@echo off
chcp 65001 > nul
echo 正在启动 DeepSeek 余额监控（后台常驻）...
cd /d "%~dp0"
start "" pythonw main.py
echo 程序已启动，本窗口可安全关闭。
