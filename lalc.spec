# -*- mode: python ; coding: utf-8 -*-

import os
import shutil
from PIL import Image

# 获取当前工作目录
current_dir = os.getcwd()
dist_dir = os.path.join(current_dir, 'dist')


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
# 计算 splash 文字位置（含中英文）
# --------------------
splash_image_path = 'C:\\Users\\Li\\Documents\\Code\\QtLALC\\resource\\gui\\MagicGirl_White.png'
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


# --------------------
# 打包配置
# --------------------
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PyQt5.sip'],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

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
    icon="C:\\Users\\Li\\Documents\\Code\\QtLALC\\MagicAndWonder.ico",
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

# --------------------
# 压缩 lalc 文件夹
# --------------------
archive_name = os.path.join(dist_dir, 'lalc')
shutil.make_archive(archive_name, 'zip', dist_dir, 'lalc')