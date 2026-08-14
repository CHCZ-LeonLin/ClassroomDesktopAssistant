#!/usr/bin/env python3
# PNG 转 ICO 脚本
# 使用方法: pip install Pillow && python convert_ico.py
# 或者: py -3 -m pip install Pillow && py -3 convert_ico.py

from PIL import Image
import os

def png_to_ico(png_path, ico_path):
    """将 PNG 图片转换为 ICO 格式"""
    img = Image.open(png_path)
    
    # ICO 需要多种尺寸，常见为 16, 32, 48, 256
    sizes = [16, 32, 48, 256]
    images = []
    
    for size in sizes:
        # 调整图片大小
        resized = img.resize((size, size), Image.Resampling.LANCZOS)
        images.append(resized)
    
    # 保存 ICO
    images[0].save(
        ico_path,
        format='ICO',
        sizes=[(s, s) for s in sizes]
    )
    print(f"已转换: {ico_path}")

if __name__ == "__main__":
    # 学生端图标
    if os.path.exists("student.png"):
        png_to_ico("student.png", "student.ico")
    
    # 教师端图标
    if os.path.exists("teacher.png"):
        png_to_ico("teacher.png", "teacher.ico")
    
    print("\n转换完成！现在可以运行 pyinstaller build.spec 重新打包")