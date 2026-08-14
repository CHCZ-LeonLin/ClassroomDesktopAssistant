# -*- mode: python ; coding: utf-8 -*-
# 班级桌面助手 v1.2.3-Beta.1 PyInstaller 打包配置（学生端 + 教师端）
# 
# 图标使用方法：
# 1. 将 student.ico 放到 src/student.ico
# 2. 将 teacher.ico 放到 src/teacher.ico
# 3. 重新运行: pyinstaller build.spec
#
# ICO 文件要求：
# - 建议尺寸 256x256 或 512x512
# - 可使用 https://www.icoconverter.com/ 将 PNG 转为 ICO
# - 或使用在线工具 https://cloudconvert.com/png-to-ico

import os

block_cipher = None

# 图标路径
STUDENT_ICON = 'student.ico'
TEACHER_ICON = 'teacher.ico'

# 检查图标是否存在
def get_icon_path(icon_name):
    if os.path.exists(icon_name):
        return icon_name
    return None  # 如果图标不存在则不设置

# ============================================================
# 学生端
# ============================================================
a_student = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('student.html', '.'),
        ('student.ico', '.'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'email',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.header',
        'email.utils',
        'email.encoders',
        'email.parser',
        'email.generator',
        'email.charset',
        'email.contentmanager',
        'email.policy',
        'email.errors',
        'email.quoprimime',
        'email.base64mime',
        'email.iterators',
        'email.message',
        'email.feedparser',
        'email._encoded_words',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_student = PYZ(a_student.pure, a_student.zipped_data, cipher=block_cipher)

exe_student = EXE(
    pyz_student,
    a_student.scripts,
    [],
    exclude_binaries=True,
    name='ClassroomDesktopAssistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=get_icon_path(STUDENT_ICON),  # 使用自定义图标
)

coll_student = COLLECT(
    exe_student,
    a_student.binaries,
    a_student.zipfiles,
    a_student.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='student',
)

# ============================================================
# 教师端
# ============================================================
a_teacher = Analysis(
    ['teacher_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('teacher.html', '.'),
        ('teacher.ico', '.'),
    ],
    hiddenimports=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',
        'email',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.header',
        'email.utils',
        'email.encoders',
        'email.parser',
        'email.generator',
        'email.charset',
        'email.contentmanager',
        'email.policy',
        'email.errors',
        'email.quoprimime',
        'email.base64mime',
        'email.iterators',
        'email.message',
        'email.feedparser',
        'email._encoded_words',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz_teacher = PYZ(a_teacher.pure, a_teacher.zipped_data, cipher=block_cipher)

exe_teacher = EXE(
    pyz_teacher,
    a_teacher.scripts,
    [],
    exclude_binaries=True,
    name='ClassroomDesktopAssistant-Teacher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=get_icon_path(TEACHER_ICON),  # 使用自定义图标
)

coll_teacher = COLLECT(
    exe_teacher,
    a_teacher.binaries,
    a_teacher.zipfiles,
    a_teacher.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='teacher',
)