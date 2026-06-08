# DeepSeek 余额监控工具

一个常驻任务栏的 DeepSeek API 余额查询工具，液态玻璃 UI 风格，API Key 本地加密保存。

## 功能特性

- **任务栏常驻**：程序后台运行，点击托盘图标弹出余额卡片
- **余额实时查询**：调用 DeepSeek 官方 API 查询账户余额
- **液态玻璃 UI**：深色毛玻璃风格，美观现代
- **API Key 安全保护**：使用 Windows Credential Manager 加密存储，Key 不写入任何文件
- **定时自动刷新**：每 5 分钟自动刷新一次余额
- **快捷充值**：一键跳转官方充值页面
- **低余额提示**：余额不足时以红色/黄色高亮警示

## 文件结构

```
project/
├── main.py                 程序入口
├── tray.py                 系统托盘管理
├── generate_icon.py        图标生成脚本
├── requirements.txt        依赖列表
├── install_and_run.bat     一键安装并运行（首次使用）
├── start.bat               快速启动
├── assets/
│   └── icon.ico            托盘图标（首次运行自动生成）
├── core/
│   ├── api_client.py       DeepSeek API 封装
│   ├── key_manager.py      API Key 安全存储
│   └── scheduler.py        定时刷新调度
└── ui/
    ├── main_window.py      主窗口（余额展示）
    └── settings_window.py  设置窗口（Key 管理）
```

## 快速开始

### 方式一：一键安装并运行（推荐首次使用）

双击 `install_and_run.bat`

### 方式二：手动安装

```bash
# 安装依赖
pip install -r requirements.txt

# 生成图标
python generate_icon.py

# 启动程序
python main.py
```

## 使用说明

1. **首次启动**：程序会自动弹出设置窗口，要求输入 API Key
2. **输入 API Key**：粘贴您的 DeepSeek API Key（格式：`sk-xxxx`），点击"验证 Key"确认有效后"保存 Key"
3. **查看余额**：主界面自动显示余额，点击"↻"手动刷新
4. **后台使用**：关闭主窗口后程序继续在托盘运行，点击图标可随时弹出

## API Key 安全说明

本工具采用三层安全保护：

1. **Windows Credential Manager**：Key 存储在操作系统安全区域（控制面板 → 凭据管理器），只有当前 Windows 账户可访问
2. **内存安全**：读取 Key 后立即在请求头中使用，不赋值给持久变量，请求完成后即清除
3. **传输加密**：所有网络请求强制 HTTPS + SSL 证书验证

您可以在 Windows 凭据管理器中查看/删除已保存的凭据（搜索"DeepSeekMonitor"）。

## 打包为 .exe（可选）

如需打包成单文件 exe，方便分发：

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=assets/icon.ico --name=DeepSeekMonitor main.py
```

生成的 exe 在 `dist/DeepSeekMonitor.exe`。

## 系统要求

- Windows 10 / 11
- Python 3.10+（若使用源码运行）
- 网络连接（用于 API 查询）
