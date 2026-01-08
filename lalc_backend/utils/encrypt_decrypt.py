import base64
import hashlib
import platform
import subprocess
import uuid
import os

# 导入win32crypt模块用于Windows数据保护API
try:
    import win32crypt
except ImportError:
    raise Exception("警告: 未找到pywin32库，请运行'pip install pywin32'安装。")
from utils.logger import init_logger

logger = init_logger()




def encrypt_cdk(text: str) -> str:
    """使用当前Windows用户凭据加密CDK字符串"""
    entropy = b"LALC"  
    
    if not text:
        return ""

    # 转换为字节
    data = text.encode('utf-8')

    # 加密数据（只能由同一用户在同一机器上解密）
    try:
        encrypted_data = win32crypt.CryptProtectData(
            data,
            None,  # 描述字符串（可选）
            entropy,  # 额外熵值（增强安全性）
            None,  # 保留
            None,  # 提示信息
            0  # 默认标志：CRYPTPROTECT_UI_FORBIDDEN
        )
        # 返回Base64编码的加密结果
        return base64.b64encode(encrypted_data).decode('utf-8')
    except Exception as e:
        logger.error(f"CDK加密失败: {e}")
        # 加密失败时返回原文
        return text


def decrypt_cdk(encrypted_b64: str) -> str:
    """使用当前Windows用户凭据解密CDK字符串"""
    entropy = b"LALC" 
    
    if not encrypted_b64:
        return ""

    if len(encrypted_b64) % 4 != 0:
        logger.error("CDK解密失败: Base64编码格式不正确")
        return encrypted_b64
        
    try:
        # 解码Base64
        encrypted_data = base64.b64decode(encrypted_b64)

        # 解密数据
        decrypted_data = win32crypt.CryptUnprotectData(
            encrypted_data,
            entropy,  # 必须与加密时相同的熵值
            None,  # 保留
            None,  # 提示信息
            0  # 默认标志
        )
        
        # 返回原始字符串
        return decrypted_data[1].decode('utf-8')
    except Exception as e:
        logger.error(f"CDK解密失败: {e}")
        # 解密失败时返回原始数据
        return encrypted_b64


def main():
    # 测试加解密
    original_cdk = "a1b2c3d4e5f6"
    print(f"原始CDK: {original_cdk}")
    
    # 加密
    encrypted = encrypt_cdk(original_cdk)
    print(f"加密结果: {encrypted}")
    
    # 解密
    decrypted = decrypt_cdk(encrypted)
    print(f"解密结果: {decrypted}")
    
    # 验证
    print(f"加解密是否成功: {original_cdk == decrypted}")


if __name__ == "__main__":
    main()