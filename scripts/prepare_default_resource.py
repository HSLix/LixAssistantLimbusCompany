"""从维护者的本机数据导出随仓库提交的默认资源包。"""

from contextlib import closing
from datetime import datetime, timezone
from hashlib import file_digest
from pathlib import Path

from lalc.application import default_data_root
from lalc.default_resources import DEFAULT_RESOURCE_NAME, check_default_package, export_default_resources
from lalc.process_lock import ProcessLock
from lalc.resource_version import RESOURCE_VERSION_FORMAT
from lalc.sharing import SharingPackage
from lalc.work_files import WorkDirectory, work_file

ROOT = Path(__file__).resolve().parents[1]


def main():
    """在目标同盘验证 ZIP，再更新默认包及配套的导出时间文件。"""
    destination = ROOT / "packaging" / DEFAULT_RESOURCE_NAME
    metadata = destination.with_suffix(".txt")
    with ProcessLock("default-resource-export"), WorkDirectory(dir=destination.parent, prefix=".default-resources-") as directory:
        if any(path.is_symlink() or (path.exists() and not path.is_file()) for path in (destination, metadata)):
            raise ValueError("默认资源包与时间文件的目标必须是普通文件。")
        version = datetime.now(timezone.utc).strftime(RESOURCE_VERSION_FORMAT)
        archive = Path(directory) / destination.name
        counts = export_default_resources(default_data_root(), archive)
        with closing(SharingPackage(archive, archive.parent)) as package:
            check_default_package(package)
        pending_metadata = archive.with_suffix(".txt")
        with archive.open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()
        pending_metadata.write_text(f"{version}\n{digest}\n", encoding="ascii")
        previous_metadata = None
        metadata_replaced = keep_backup = False
        try:
            if metadata.exists():
                with work_file(dir=metadata.parent, prefix=".default-resources-previous-", suffix=".txt", delete=False) as backup:
                    previous_metadata = Path(backup.name)
                    backup.write(metadata.read_bytes())
            pending_metadata.replace(metadata)
            metadata_replaced = True
            archive.replace(destination)
        except OSError:
            if metadata_replaced:
                if previous_metadata is None:
                    metadata.unlink(missing_ok=True)
                else:
                    keep_backup = True
                    try:
                        previous_metadata.replace(metadata)
                    except OSError as error:
                        raise RuntimeError(f"无法恢复导出时间文件，原件保留在 {previous_metadata}") from error
            raise
        finally:
            if previous_metadata is not None and not keep_backup:
                previous_metadata.unlink(missing_ok=True)
    print(f"默认资源包已准备好：{destination} {counts}")
    print(f"默认资源导出版本：{version}（{metadata}）")


if __name__ == "__main__":
    main()
