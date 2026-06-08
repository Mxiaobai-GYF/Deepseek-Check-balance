"""
key_manager.py - API Key 安全管理模块
--------------------------------------
使用 Windows Credential Manager (keyring) 存储 API Key，
Key 永远不会以明文形式写入任何文件，只存在于操作系统安全区域。
只有当前 Windows 用户账户才能访问，即使拿到硬盘也无法直接读取。
"""

import keyring                  # 系统级密钥链库
import logging

# 服务名称：在 Windows 凭据管理器中的分组名
SERVICE_NAME = "DeepSeekMonitor"
# 凭据键名：同一服务下可以存多个 Key（此处只存一个主 Key）
USERNAME = "api_key"

logger = logging.getLogger(__name__)


def save_api_key(api_key: str) -> bool:
    """
    将 API Key 加密保存到系统凭据管理器。
    
    参数:
        api_key: 用户输入的 DeepSeek API Key，格式通常为 sk-xxxxxxxx
    返回:
        True 表示保存成功，False 表示失败
    """
    try:
        # keyring 自动调用系统级加密（Windows: DPAPI + Credential Manager）
        keyring.set_password(SERVICE_NAME, USERNAME, api_key)
        logger.info("API Key 已安全保存到系统凭据管理器")
        return True
    except Exception as e:
        logger.error(f"保存 API Key 失败: {e}")
        return False


def load_api_key() -> str | None:
    """
    从系统凭据管理器读取 API Key。
    
    返回:
        API Key 字符串，或 None（未设置时）
    注意:
        读取后应立即使用，不要长期保存在变量中
    """
    try:
        key = keyring.get_password(SERVICE_NAME, USERNAME)
        return key  # 可能为 None（从未设置过）
    except Exception as e:
        logger.error(f"读取 API Key 失败: {e}")
        return None


def delete_api_key() -> bool:
    """
    从系统凭据管理器删除 API Key（用于"退出登录"功能）。
    
    返回:
        True 表示删除成功，False 表示失败
    """
    try:
        keyring.delete_password(SERVICE_NAME, USERNAME)
        logger.info("API Key 已从凭据管理器删除")
        return True
    except keyring.errors.PasswordDeleteError:
        # Key 本来就不存在，视为成功
        return True
    except Exception as e:
        logger.error(f"删除 API Key 失败: {e}")
        return False


def has_api_key() -> bool:
    """
    检查是否已保存 API Key（用于判断是否需要首次设置）。
    
    返回:
        True 表示已有保存的 Key，False 表示尚未设置
    """
    return load_api_key() is not None


def get_masked_key() -> str:
    """
    返回脱敏后的 Key 显示字符串（只显示末4位），用于 UI 展示。
    例如：sk-••••••••••••••••••••4f2a
    
    返回:
        脱敏字符串，或 "未设置" 字符串
    """
    key = load_api_key()
    if not key:
        return "未设置"
    
    # 只显示 "sk-" 前缀 + 中间全部遮罩 + 末4位
    visible_suffix = key[-4:] if len(key) >= 4 else key
    masked_middle = "•" * max(0, len(key) - 7)  # 7 = len("sk-") + 4
    return f"sk-{masked_middle}{visible_suffix}"
