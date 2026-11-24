"""从维护者的本机数据导出随仓库提交的默认资源包。"""

from contextlib import closing
from pathlib import Path

from lalc.application import default_data_root
from lalc.default_resources import DEFAULT_RESOURCE_NAME, check_default_package, export_default_resources
from lalc.sharing import SharingPackage
from lalc.work_files import WorkDirectory

ROOT = Path(__file__).resolve().parents[1]


def main():
    """在目标同盘验证 ZIP，成功后再替换现有默认包。"""
    destination = ROOT / "packaging" / DEFAULT_RESOURCE_NAME
    if destination.is_symlink():
        raise ValueError("默认资源包目标不能是链接。")
    with WorkDirectory(dir=destination.parent, prefix=".default-resources-") as directory:
        archive = Path(directory) / destination.name
        counts = export_default_resources(default_data_root(), archive)
        with closing(SharingPackage(archive, archive.parent)) as package:
            check_default_package(package)
        archive.replace(destination)
    print(f"默认资源包已准备好：{destination} {counts}")


if __name__ == "__main__":
    main()
