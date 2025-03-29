# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from pathlib import Path
from PIL import Image
import subprocess
import rapidocr_onnxruntime

# 获取当前工作目录
current_dir = os.getcwd()
dist_dir = os.path.join(current_dir, 'dist')

# --------------------
# 动态收集 rapidocr_onnxruntime 数据文件
# --------------------
package_name = 'rapidocr_onnxruntime'
install_dir = Path(rapidocr_onnxruntime.__file__).resolve().parent

onnx_paths = list(install_dir.rglob('*.onnx'))
yaml_paths = list(install_dir.rglob('*.yaml'))

onnx_add_data = [(str(v.parent), f'{package_name}/{v.parent.name}')
                for v in onnx_paths]

yaml_add_data = []
for v in yaml_paths:
    if package_name == v.parent.name:
        yaml_add_data.append((str(v.parent / '*.yaml'), package_name))
    else:
        yaml_add_data.append(
            (str(v.parent / '*.yaml'), f'{package_name}/{v.parent.name}'))

add_data = list(set(yaml_add_data + onnx_add_data))

# --------------------
# 清空 dist 目录
# --------------------
if os.path.exists(dist_dir):
    for root, dirs, files in os.walk(dist_dir, topdown=False):
        for file in files:
            os.remove(os.path.join(root, file))
        for dir in dirs:
            shutil.rmtree(os.path.join(root, dir))

# --------------------
# 资源处理
# --------------------
folders_to_copy = ['resource', 'log', 'i18n', 'video', 'doc', 'config']
folders_to_empty = ['log', 'video']

# --------------------
# 打包配置
# --------------------
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=add_data,
    hiddenimports=['PyQt5.sip'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# --------------------
# 计算 splash 文字位置（含中英文）
# --------------------
splash_image_path = 'C:\\Users\\Li\\Documents\\Code\\LixAssistantLimbusCompany\\resource\\gui\\MagicGirl_White.png'
splash_text = "正在初始化（少女祈祷中）  Initializing"  # 中英文换行
text_size = 20  # 增大文字大小
text_color = 'black'  # 建议浅色文字适配深色背景

try:
    with Image.open(splash_image_path) as img:
        width, height = img.size
        text_size = 20
        text_pos = (100, height - text_size)  # 文字居中且在最下方
except Exception as e:
    print(f"读取图片 {splash_image_path} 时出错: {e}")
    text_pos = (10, 50)  # 默认位置

splash = Splash(
    splash_image_path,
    binaries=a.binaries,
    datas=a.datas,
    text_default=splash_text,  # 设置显示文本
    text_pos=text_pos,
    text_size=text_size,
    text_color=text_color,
    always_on_top=True,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    splash,
    a.scripts,
    name='LixAssistantLimbusCompany',
    console=False,
    icon="C:\\Users\\Li\\Documents\\Code\\LixAssistantLimbusCompany\\MagicAndWonder.ico",
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    splash.binaries,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lalc',
)


# --------------------
# 复制自定义资源到 lalc 目录
# --------------------
dist_lalc_dir = os.path.join(dist_dir, 'lalc')
os.makedirs(dist_lalc_dir, exist_ok=True)

for folder in folders_to_copy:
    # 清空 dist/lalc 中的 log 和 video
    if (folder in folders_to_empty):
        continue
    source = os.path.join(current_dir, folder)
    dest = os.path.join(dist_lalc_dir, folder)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(source, dest)

dist_lalc_log_dir = os.path.join(dist_dir, 'lalc/log')
os.makedirs(dist_lalc_log_dir, exist_ok=True)
dist_lalc_video_dir = os.path.join(dist_dir, 'lalc/video')
os.makedirs(dist_lalc_video_dir, exist_ok=True)


additional_files = [
    ('README.md', '.'),      # 复制到根目录
    ('README_en.md', '.'),   # 复制到根目录
    ('LICENSE', '.'),        # 复制到根目录
]
# 复制额外文件
for src_file, dest_dir in additional_files:
    src_path = os.path.join(current_dir, src_file)
    dest_path = os.path.join(dist_lalc_dir, dest_dir, src_file)
    shutil.copy2(src_path, dest_path)
    

# --------------------
# 压缩 lalc 文件夹为 zip
# --------------------
archive_name = os.path.join(dist_dir, 'lalc')
shutil.make_archive(archive_name, 'zip', dist_dir, 'lalc')

