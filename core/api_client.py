"""
api_client.py - DeepSeek API 接口封装模块
------------------------------------------
封装所有对 DeepSeek 平台 API 的请求。
安全设计原则：
  1. API Key 只在发送请求时从 keyring 读取，请求结束后立即清除引用
  2. 所有请求强制 HTTPS，开启 SSL 证书验证
  3. 接口返回的数据结构统一封装，调用方无需处理原始 HTTP
"""

import httpx                    # 现代 HTTP 客户端，支持超时和重试
import logging
from dataclasses import dataclass
from core.key_manager import load_api_key   # 唯一读取 Key 的入口

logger = logging.getLogger(__name__)

# DeepSeek API 基础地址
BASE_URL = "https://api.deepseek.com"

# 请求超时时间（秒）
REQUEST_TIMEOUT = 10.0


@dataclass
class BalanceInfo:
    """
    余额信息数据类，封装从 API 返回的余额相关字段。
    """
    is_available: bool              # 账户是否可用
    balance_infos: list             # 原始余额列表（可能有多个币种）
    
    # 以下是解析后的主要字段（人民币）
    total_balance: float = 0.0      # 总余额（¥）
    granted_balance: float = 0.0    # 赠送余额（¥）
    topped_up_balance: float = 0.0  # 充值余额（¥）
    
    # 错误信息（请求失败时填充）
    error: str | None = None


@dataclass 
class ApiResult:
    """
    通用 API 调用结果，携带成功标志和可选错误信息。
    """
    success: bool
    data: object | None = None
    error: str | None = None
    error_code: int | None = None  # HTTP 状态码


def _build_headers() -> dict | None:
    """
    构建包含 Authorization 的请求头。
    
    安全要点：
        - 从 keyring 读取 Key，不做任何持久化
        - 函数返回后局部变量即出栈释放
    
    返回:
        请求头字典，或 None（未设置 Key 时）
    """
    # 从系统凭据管理器读取 Key
    api_key = load_api_key()
    if not api_key:
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    # 手动释放 api_key 变量，减少内存中明文 Key 的存留时间
    del api_key
    
    return headers


def fetch_balance() -> ApiResult:
    """
    查询账户余额。
    
    调用接口：GET https://api.deepseek.com/user/balance
    
    返回:
        ApiResult 对象，成功时 data 为 BalanceInfo 实例
    """
    headers = _build_headers()
    if headers is None:
        return ApiResult(
            success=False,
            error="未设置 API Key，请先在设置中填入您的 DeepSeek API Key"
        )
    
    try:
        # verify=True 强制验证 SSL 证书，防止中间人攻击
        with httpx.Client(verify=True, timeout=REQUEST_TIMEOUT) as client:
            response = client.get(
                f"{BASE_URL}/user/balance",
                headers=headers
            )
        
        # 清除 headers 中的认证信息（防止引用残留）
        del headers
        
        # 处理 HTTP 错误状态码
        if response.status_code == 401:
            return ApiResult(
                success=False,
                error="API Key 无效或已过期，请重新设置",
                error_code=401
            )
        elif response.status_code == 403:
            return ApiResult(
                success=False,
                error="权限不足，请检查 API Key 是否有余额查询权限",
                error_code=403
            )
        elif response.status_code == 429:
            return ApiResult(
                success=False,
                error="请求过于频繁，请稍后再试",
                error_code=429
            )
        elif response.status_code != 200:
            return ApiResult(
                success=False,
                error=f"API 请求失败，状态码: {response.status_code}",
                error_code=response.status_code
            )
        
        # 解析 JSON 响应
        data = response.json()
        
        # 解析余额信息
        # DeepSeek API 返回格式示例：
        # {
        #   "is_available": true,
        #   "balance_infos": [
        #     {
        #       "currency": "CNY",
        #       "total_balance": "42.80",
        #       "granted_balance": "0.00",
        #       "topped_up_balance": "42.80"
        #     }
        #   ]
        # }
        
        balance_info = BalanceInfo(
            is_available=data.get("is_available", False),
            balance_infos=data.get("balance_infos", [])
        )
        
        # 找人民币 CNY 余额（通常只有一条记录）
        for item in balance_info.balance_infos:
            if item.get("currency") == "CNY":
                balance_info.total_balance = float(item.get("total_balance", 0))
                balance_info.granted_balance = float(item.get("granted_balance", 0))
                balance_info.topped_up_balance = float(item.get("topped_up_balance", 0))
                break
        else:
            # 如果没有 CNY 币种，取第一条记录
            if balance_info.balance_infos:
                item = balance_info.balance_infos[0]
                balance_info.total_balance = float(item.get("total_balance", 0))
                balance_info.granted_balance = float(item.get("granted_balance", 0))
                balance_info.topped_up_balance = float(item.get("topped_up_balance", 0))
        
        logger.info(f"余额查询成功：¥{balance_info.total_balance:.2f}")
        return ApiResult(success=True, data=balance_info)
    
    except httpx.ConnectError:
        return ApiResult(
            success=False,
            error="网络连接失败，请检查网络后重试"
        )
    except httpx.TimeoutException:
        return ApiResult(
            success=False,
            error=f"请求超时（>{REQUEST_TIMEOUT}秒），请检查网络"
        )
    except httpx.SSLError:
        return ApiResult(
            success=False,
            error="SSL 证书验证失败，可能存在网络安全风险"
        )
    except ValueError as e:
        return ApiResult(
            success=False,
            error=f"API 响应格式异常: {e}"
        )
    except Exception as e:
        logger.error(f"余额查询异常: {e}", exc_info=True)
        return ApiResult(
            success=False,
            error=f"未知错误: {str(e)}"
        )


def validate_api_key(api_key: str) -> ApiResult:
    """
    验证一个 API Key 是否有效（不通过 keyring，直接用传入的 key）。
    用于首次设置 Key 时的即时验证。
    
    参数:
        api_key: 待验证的 API Key 字符串
    返回:
        ApiResult，成功表示 Key 有效，失败表示无效
    """
    if not api_key or not api_key.strip():
        return ApiResult(success=False, error="API Key 不能为空")
    
    if not api_key.startswith("sk-"):
        return ApiResult(success=False, error="API Key 格式不正确，应以 sk- 开头")
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        with httpx.Client(verify=True, timeout=REQUEST_TIMEOUT) as client:
            response = client.get(
                f"{BASE_URL}/user/balance",
                headers=headers
            )
        
        # 清除 headers 中的 Key
        del headers
        del api_key
        
        if response.status_code == 200:
            return ApiResult(success=True, data=response.json())
        elif response.status_code == 401:
            return ApiResult(success=False, error="API Key 无效", error_code=401)
        else:
            return ApiResult(
                success=False,
                error=f"验证失败，状态码: {response.status_code}",
                error_code=response.status_code
            )
    
    except httpx.ConnectError:
        return ApiResult(success=False, error="网络连接失败")
    except httpx.TimeoutException:
        return ApiResult(success=False, error="连接超时，请检查网络")
    except Exception as e:
        return ApiResult(success=False, error=f"验证出错: {str(e)}")
