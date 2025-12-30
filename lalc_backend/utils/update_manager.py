import requests
import os
from typing import Optional, Callable
import asyncio
from typing import Awaitable
from utils.logger import init_logger
import time

# 全局logger实例
logger = init_logger()


async def _stream_to_file_with_cancel(
    response: requests.Response,
    file_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    chunk_size: int = 8192,
) -> None:
    """
    可取消的流式写文件
    调用者必须保证该协程运行在一个可以被 asyncio.Task.cancel() 的任务里
    """
    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0
    last_log_time = time.time()

    with open(file_path, "wb") as f:
        # 外层 for 循环里定期让出事件循环，使取消信号有机会进来
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                # ① 响应 asyncio.CancelledError
                await asyncio.sleep(0)
                # ② 业务自己再检查一次（双重保险）
                if asyncio.current_task().cancelled():
                    raise asyncio.CancelledError("下载被用户取消")

                f.write(chunk)
                downloaded += len(chunk)

                # 进度回调
                if total_size:
                    progress = (downloaded / total_size) * 100
                    if time.time() - last_log_time >= 1.0:
                        if progress_callback:
                            progress_callback(progress)
                        last_log_time = time.time()


def download_latest_release_asset(
    repo_owner: str, 
    repo_name: str, 
    asset_name: str, 
    download_path: str = ".",
    progress_callback: Optional[Callable[[float], None]] = None  # 添加进度回调函数
) -> tuple:
    """
    从GitHub仓库的最新release中下载指定的asset文件
    
    Args:
        repo_owner: 仓库所有者名称
        repo_name: 仓库名称
        asset_name: 要下载的asset名称
        download_path: 下载路径，默认为当前目录
        progress_callback: 进度回调函数，接受一个浮点数参数（0-100表示进度百分比）
    
    Returns:
        (task, file_path) 元组，task是可取消的下载任务，file_path是下载文件路径
    """
    # 构建获取最新release的API URL
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest"
    
    # 检查下载路径中是否已存在同名文件，如果存在则删除
    file_path = os.path.join(download_path, asset_name)
    if os.path.exists(file_path):
        logger.debug(f"发现已存在的文件 {file_path}，正在删除...")
        os.remove(file_path)
    
    async def _do_download():
        loop = asyncio.get_running_loop()
        # ① 先在线程里把 asset 的 download_url 拿到（很轻，几乎瞬时）
        resp = await loop.run_in_executor(None, lambda: requests.get(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest",
            headers={"User-Agent": "LixAssistantDownloader"},
        ))
        
        # 检查是否有速率限制错误
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            raise Exception("GitHub下载量达到最大限制|GitHub rate limit exceeded")
        
        resp.raise_for_status()
        release_info = resp.json()

        tag_name = release_info.get("tag_name", "未知")
        logger.debug(f"获取到的最新版本号: {tag_name}")
        logger.debug(f"GitHub 回应：{release_info}")

        asset_url = None
        for asset in release_info.get("assets", []):
            if asset["name"] == asset_name:
                asset_url = asset["url"]
                break
        if not asset_url:
            raise Exception(f"在仓库 {repo_owner}/{repo_name} 的最新release中未找到asset: {asset_name}")

        # ② 真正下载流（仍在线程池，但把 requests.Response 对象传回主线程）
        def _sync_download():
            headers = {
                "Accept": "application/octet-stream",
                "User-Agent": "LixAssistantDownloader",
            }
            return requests.get(asset_url, headers=headers, stream=True, timeout=30)

        sync_resp = await loop.run_in_executor(None, _sync_download)
        sync_resp.raise_for_status()

        # ③ 使用可取消的写文件协程
        await _stream_to_file_with_cancel(sync_resp, file_path, progress_callback)
        return file_path

    # 返回一个任务对象 + 目标路径，由调用方自行调度/取消
    task = asyncio.create_task(_do_download())
    return task, file_path


def download_lalc_release_asset(download_path: str = ".", progress_callback: Optional[Callable[[float], None]] = None) -> tuple:
    """
    专门用于下载HSLix/LixAssistantLimbusCompany仓库的lalc.zip文件
    
    Args:
        download_path: 下载路径，默认为当前目录
        progress_callback: 进度回调函数，接受一个浮点数参数（0-100表示进度百分比）
    
    Returns:
        (task, file_path) 元组，task是可取消的下载任务，file_path是下载文件路径
    """
    return download_latest_release_asset(
        repo_owner="HSLix",
        repo_name="LixAssistantLimbusCompany",
        asset_name="lalc.zip",
        download_path=download_path,
        progress_callback=progress_callback
    )

_MIRRORCHAN_ERROR_MAP = {
    (403, 7001): "CDK 已过期",
    (403, 7002): "CDK 格式错误",
    (403, 7003): "CDK 今日下载次数已达上限",
    (403, 7004): "CDK 类型与资源不匹配",
    (403, 7005): "CDK 已被封禁",
    (404, 8001): "指定系统/架构的资源不存在",
    (400, 8002): "错误的系统参数",
    (400, 8003): "错误的架构参数",
    (400, 8004): "错误的更新通道参数",
}

def download_lalc_from_mirrorchan(
    download_path: str = ".", 
    cdk: str = None,
    current_version: str = None,
    progress_callback: Optional[Callable[[float], None]] = None  # 添加进度回调函数
) -> tuple:
    """
    从mirrorchan下载LALC最新版release
    
    Args:
        download_path: 下载路径，默认为当前目录
        cdk: 访问码，如果未提供或无效，将抛出异常
        current_version: 当前版本名称，用于检查是否需要增量更新
        progress_callback: 进度回调函数，接受一个浮点数参数（0-100表示进度百分比）
    
    Returns:
        (task, file_path) 元组，task是可取消的下载任务，file_path是下载文件路径
    
    Raises:
        Exception: 当CDK无效时抛出异常
    """
    # API基础URL
    base_url = "https://mirrorchyan.com/api"
    resource_id = "LALC"  # LALC的资源ID，根据API样例应为大写
    api_url = f"{base_url}/resources/{resource_id}/latest"

    # 构建查询参数
    params = {
        "cdk": cdk,
        "user_agent": "LALC",
    }

    # 添加当前版本参数（如果提供）
    if current_version:
        params["current_version"] = current_version

    # 过滤掉未提供的参数
    params = {k: v for k, v in params.items() if v is not None}

    filename = "lalc.zip"  # 强制使用lalc.zip作为文件名，而不是服务器返回的文件名
    file_path = os.path.join(download_path, filename)

    # 检查下载路径中是否已存在同名文件，如果存在则删除
    if os.path.exists(file_path):
        logger.debug(f"发现已存在的文件 {file_path}，正在删除...")
        os.remove(file_path)

    async def _do_download():
        loop = asyncio.get_running_loop()
        logger.debug(f"正在从mirrorchan获取LALC最新版本信息")

        # response = await loop.run_in_executor(None, lambda: requests.get(api_url, params=params))
        # response.raise_for_status()
        try:
            raw_resp = await loop.run_in_executor(
                None, lambda: requests.get(api_url, params=params, timeout=30)
            )
            # 手动 raise，方便后面捕获
            raw_resp.raise_for_status()
            result = raw_resp.json()
            logger.debug(f"MirrorChan 回应：{result}")
        except requests.HTTPError as e:
            resp = e.response
            status = resp.status_code
            try:
                body = resp.json()
                code = body.get("code")
                msg  = body.get("msg", "")
            except ValueError:          # 非 JSON
                body = {}
                code = None
                msg  = resp.text

            # 查表翻译
            key = (status, code)
            if key in _MIRRORCHAN_ERROR_MAP:
                raise Exception(f"镜像站错误: {_MIRRORCHAN_ERROR_MAP[key]}; origin_msg={msg}") from None
            else:
                # 兜底
                raise Exception(f"镜像站错误 (HTTP {status}, code={code}): {msg}") from None

        

        # 检查是否有下载URL
        if "data" not in result or "url" not in result["data"]:
            raise Exception("响应中没有包含下载URL")

        download_url = result["data"]["url"]
        
        # 开始下载文件
        logger.debug(f"正在从mirrorchan下载文件")
        download_response = await loop.run_in_executor(None, lambda: requests.get(download_url, stream=True, timeout=30))
        download_response.raise_for_status()

        # 使用可取消的写文件协程
        await _stream_to_file_with_cancel(download_response, file_path, progress_callback)
        return file_path

    # 返回一个任务对象 + 目标路径，由调用方自行调度/取消
    task = asyncio.create_task(_do_download())
    return task, file_path


def test_mirrorchan_download(download_path: str = ".", cdk: str = None) -> Optional[str]:
    """
    测试从mirrorchan下载LALC最新版release的功能
    
    Args:
        download_path: 下载路径，默认为当前目录
        cdk: 访问码，默认为None以测试CDK无效的情况
    
    Returns:
        下载文件的完整路径，如果下载失败则返回None
    """
    logger.debug("开始测试从mirrorchan下载LALC...")
    try:
        task, file_path = download_lalc_from_mirrorchan(download_path=download_path, cdk=cdk)
        # 等待任务完成
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(task)
        if result:
            logger.debug(f"测试成功: 文件已下载到 {result}")
        else:
            logger.debug("测试完成，但未成功下载文件")
        return result
    except Exception as e:
        raise Exception(f"测试捕获到异常: {e}")


def get_latest_version() -> str:
    """
    获取最新的LALC版本号
    首先尝试从GitHub获取，如果失败则从mirrorchan获取
    
    Returns:
        最新版本号字符串
    """
    # 尝试从GitHub获取版本号
    try:
        logger.debug("尝试从GitHub获取最新版本号")
        api_url = "https://api.github.com/repos/HSLix/LixAssistantLimbusCompany/releases/latest"
        response = requests.get(api_url)
        response.raise_for_status()
        
        release_info = response.json()
        tag_name = release_info.get("tag_name", "")
        logger.debug(f"从GitHub获取到版本号: {tag_name}")
        return tag_name
    except Exception as e:
        logger.debug(f"从GitHub获取版本号失败: {e}，尝试从mirrorchan获取")
        
        # 如果GitHub获取失败，尝试从mirrorchan获取
        try:
            logger.debug("尝试从mirrorchan获取最新版本号")
            base_url = "https://mirrorchyan.com/api"
            resource_id = "LALC"  # LALC的资源ID，根据API样例应为大写
            api_url = f"{base_url}/resources/{resource_id}/latest"
            
            params = {
                "user_agent": "LALC",
            }
            
            response = requests.get(api_url, params=params)
            response.raise_for_status()
            
            result = response.json()
            version = result.get("data", {}).get("version_name", "Unknown")
            
                
            logger.debug(f"从mirrorchan获取到版本号: {version}")
            return version
        except Exception as mirrorchan_error:
            logger.debug(f"从mirrorchan获取版本号也失败了: {mirrorchan_error}")
            raise Exception(f"无法获取最新版本号，GitHub错误: {e}，mirrorchan错误: {mirrorchan_error}")


def main():
    import sys

    def test_github_download(download_path: str = "."):
        """测试从GitHub下载功能"""
        print("正在测试从 HSLix/LixAssistantLimbusCompany 仓库下载最新的 lalc.zip 文件...")
        
        # 调用下载函数
        task, file_path = download_lalc_release_asset(download_path=download_path)
        
        # 等待任务完成
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(task)
            if result:
                print(f"GitHub下载测试完成: {result}")
            else:
                print("GitHub下载测试失败，请检查网络连接或仓库中是否存在指定的asset文件")
        except asyncio.CancelledError:
            print("GitHub下载被取消")
        except Exception as e:
            print(f"GitHub下载失败: {e}")


    def test_mirrorchan_download_with_cdk(download_path: str = ".", cdk: str = None):
        """测试从mirrorchan下载功能，可以指定CDK"""
        print("正在测试从mirrorchan下载LALC最新版release...")
        try:
            task, file_path = download_lalc_from_mirrorchan(download_path=download_path, cdk=cdk)
            # 等待任务完成
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(task)
            if result:
                print(f"mirrorchan下载测试成功: 文件已下载到 {result}")
            else:
                print("mirrorchan下载测试完成，但未成功下载文件")
        except asyncio.CancelledError:
            print("mirrorchan下载被取消")
        except Exception as e:
            print(f"mirrorchan下载测试捕获到异常: {e}")

    print(f"latest verison:{get_latest_version()}")
    
    source = "mirrorchan"
    download_path = "."
    cdk = None
    
    # 检查下载路径是否存在
    if not os.path.exists(download_path):
        print(f"错误: 下载路径 '{download_path}' 不存在")
        sys.exit(1)
    
    if source == "github":
        test_github_download(download_path)
    elif source == "mirrorchan":
        test_mirrorchan_download_with_cdk(download_path, cdk)
    else:
        print("错误: source参数必须是 'github' 或 'mirrorchan'")
        sys.exit(1)


if __name__ == "__main__":
    main()
