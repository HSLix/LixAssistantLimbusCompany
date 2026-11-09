"""初始化开发者 Skills 并固定本轮只读副本；格式发现交给 pi。"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import threading

from .work_files import WorkDirectory
from .file_content import FileContent, checkpoint, copy_content, file_operation, require_disk
from .process_lock import ProcessLock


DEFAULT_SKILLS = Path(__file__).with_name("skills")
DEFAULT_SKILL_NAMES = ("workflow-development", "workflow-repair", "workflow-conventions", "asset-management",
                       "page-development", "validation-and-trial", "human-feedback")


def skill_files(root, diagnostics):
    """枚举普通文件，发现链接或特殊文件时诊断并排除，避免 pi 跟随链接。"""
    if root.is_symlink() or root.is_junction() or not root.is_dir():
        raise ValueError(f"Skill 根目录必须是普通目录：{root}")
    files = {}
    directories = [root]
    while directories:
        checkpoint()
        for path in sorted(directories.pop().iterdir()):
            if path.is_symlink() or path.is_junction() or not (path.is_file() or path.is_dir()):
                diagnostics.append({"path": str(path), "message": "Skill 不允许链接或特殊文件，已跳过。"})
            elif path.is_dir():
                directories.append(path)
            elif path.is_file():
                files[path.relative_to(root)] = FileContent.from_path(path)
    return files


def copy_files(files, destination):
    """流式复制并验证固定哈希，源文件变化或容量不足时不交付半成品。"""
    require_disk([(destination, sum(len(content) for content in files.values()))])
    for relative, content in files.items():
        checkpoint()
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            copy_content(content, stream)


def initialize_skills(data_root):
    """仅在目录不存在时提交完整默认副本，已有目录（含空目录）不补齐。"""
    root = data_root / "skills"
    with ProcessLock(f"skills-init:{data_root}"):
        if root.exists() or root.is_symlink():
            if root.is_symlink() or root.is_junction() or not root.is_dir():
                raise ValueError(f"Skill 根目录必须是普通目录：{root}")
            return root
        data_root.mkdir(parents=True, exist_ok=True)
        diagnostics = []
        files = skill_files(DEFAULT_SKILLS, diagnostics)
        if diagnostics or any(Path(name) / "SKILL.md" not in files for name in DEFAULT_SKILL_NAMES):
            raise ValueError("程序内置 Skill 资源不完整。")
        with WorkDirectory(prefix=".skills-init-", dir=data_root) as temporary:
            stage = Path(temporary) / "skills"
            stage.mkdir()
            copy_files(files, stage)
            checkpoint()
            # 其他 LALC 初始化由同一锁互斥；人工新建目录也不得被补齐。
            if not root.exists():
                stage.rename(root)
        return root


def prepare_skills(data_root, destination, cancelled):
    """在工作线程准备固定内容；取消及文件变更交给轮次错误处理。"""
    with file_operation(cancelled.is_set):
        root = initialize_skills(data_root.resolve())
        diagnostics = []
        files = skill_files(root, diagnostics)
        copy_files(files, destination)
        current = skill_files(root, [])
        if files != current:
            raise ValueError("准备期间 Skill 内容发生变化，请重新提交消息。")
        return diagnostics


@asynccontextmanager
async def skill_snapshot(data_root):
    """副本只存本轮普通工作目录；取消时先等待复制线程退出再删除。"""
    cancelled = threading.Event()
    with WorkDirectory(prefix="lalc-skills-") as temporary:
        root = Path(temporary).resolve()
        pending = asyncio.create_task(asyncio.to_thread(prepare_skills, Path(data_root), root, cancelled))
        try:
            diagnostics = await asyncio.shield(pending)
        except asyncio.CancelledError:
            cancelled.set()
            await asyncio.gather(pending, return_exceptions=True)
            raise
        yield root, diagnostics
