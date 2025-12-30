import base64
import hashlib
import platform
import subprocess
import uuid
import os
from utils.logger import init_logger

logger = init_logger()


def get_device_id():
    """
    获取设备唯一标识符
    """
    try:
        # 尝试使用不同方式获取设备ID，按优先级排序
        if platform.system() == "Windows":
            # Windows系统
            out = subprocess.check_output(
                'wmic csproduct get UUID /value',
                shell=True, stderr=subprocess.DEVNULL
            ).decode('utf-8', errors='ignore')
            for line in out.splitlines():
                if line.startswith('UUID='):
                    uuid = line.split('=', 1)[1].strip()
                    if uuid and not uuid.upper().startswith('FFFFFFFF'):
                        return uuid
            raise RuntimeError("获取设备 ID 失败")
        else: 
            raise Exception("现阶段只支持 Windows 系统")
    except Exception as e:
        # 如果所有方法都失败，返回一个默认值
        raise RuntimeError("获取设备 ID 失败")


# ---------- 异或加/解密 ----------
_XOR_KEY = (get_device_id() + "LALC").encode('utf-8')   # 40 字节循环密钥


def _xor_bytes(data: bytes) -> bytes:
    return bytes(b ^ _XOR_KEY[i % len(_XOR_KEY)] for i, b in enumerate(data))


def encrypt_cdk(plain: str) -> str:
    return base64.b64encode(_xor_bytes(plain.encode('utf-8'))).decode('ascii')


def decrypt_cdk(cipher: str) -> str:
    try:
        ans = _xor_bytes(base64.b64decode(cipher.encode('ascii'))).decode('utf-8')
    except Exception as e:
        raise Exception(f"CDK Decrypt ERROR:{e}")
    return ans



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
    
    # 测试获取设备ID
    print(f"设备ID: {get_device_id()}")



if __name__ == "__main__":
    main()