#!/usr/bin/env python3
"""
班级桌面助手 - 图标生成脚本
生成现代简约渐变风格的学生端和教师端图标

风格: 现代简约渐变
配色: 橙青温暖配色
  - 学生端: 橙色渐变 + 白色学士帽
  - 教师端: 青色渐变 + 白色边框黑板
"""

from PIL import Image, ImageDraw, ImageFilter
import os


STUDENT_GRADIENT = [
    (255, 156, 56),
    (255, 179, 71),
    (255, 207, 102),
]

TEACHER_GRADIENT = [
    (0, 168, 154),
    (0, 184, 169),
    (78, 205, 196),
]


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def create_gradient(size, colors):
    img = Image.new('RGB', (size, size), colors[0])
    pixels = img.load()
    diagonal = 2 * size - 2
    n_segments = len(colors) - 1
    for y in range(size):
        for x in range(size):
            t = (x + y) / diagonal
            seg = min(int(t * n_segments), n_segments - 1)
            seg_t = (t * n_segments) - seg
            pixels[x, y] = lerp_color(colors[seg], colors[seg + 1], seg_t)
    return img


def apply_rounded_mask(img, size, radius):
    mask = Image.new('L', (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    result = img.convert('RGBA')
    result.putalpha(mask)
    return result


def add_top_gloss(img, size):
    gloss = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(gloss)
    gloss_height = int(size * 0.35)
    for y in range(gloss_height):
        alpha = int(45 * (1 - y / gloss_height) ** 1.5)
        gd.line([(0, y), (size, y)], fill=(255, 255, 255, alpha))
    return Image.alpha_composite(img, gloss)


def add_inner_shadow(img, size, radius):
    shadow = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    border = max(2, size // 80)
    sd.rounded_rectangle(
        [0, 0, size - 1, size - 1],
        radius=radius,
        outline=(0, 0, 0, 35),
        width=border
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=1.5))
    return Image.alpha_composite(img, shadow)


def draw_graduation_cap(draw, cx, cy, cap_size, color=(255, 255, 255, 255),
                       accent_color=(255, 220, 150, 255)):
    board_w = cap_size
    board_h = cap_size // 4
    board_cy = cy - cap_size // 4

    board_points = [
        (cx, board_cy - board_h),
        (cx + board_w // 2, board_cy),
        (cx, board_cy + board_h),
        (cx - board_w // 2, board_cy)
    ]
    draw.polygon(board_points, fill=color)

    base_top_w = int(board_w * 0.32)
    base_bot_w = int(board_w * 0.22)
    base_h = cap_size // 3
    base_y_top = board_cy + board_h - 4

    base_points = [
        (cx - base_top_w // 2, base_y_top),
        (cx + base_top_w // 2, base_y_top),
        (cx + base_bot_w // 2, base_y_top + base_h),
        (cx - base_bot_w // 2, base_y_top + base_h)
    ]
    base_color = (color[0], color[1], color[2], 235)
    draw.polygon(base_points, fill=base_color)

    tassel_start_x = cx + board_w // 2 - 2
    tassel_start_y = board_cy

    tassel_end_x = tassel_start_x + cap_size // 6
    tassel_end_y = tassel_start_y + cap_size // 3
    mid_x = tassel_start_x + cap_size // 8
    mid_y = tassel_start_y + cap_size // 5

    line_width = max(3, cap_size // 40)
    draw.line(
        [(tassel_start_x, tassel_start_y), (mid_x, mid_y), (tassel_end_x, tassel_end_y)],
        fill=color, width=line_width, joint='curve'
    )

    bead_r = max(5, cap_size // 30)
    bead_cx = tassel_end_x
    bead_cy = tassel_end_y + bead_r
    draw.ellipse(
        [bead_cx - bead_r, bead_cy - bead_r,
         bead_cx + bead_r, bead_cy + bead_r],
        fill=accent_color
    )

    tassel_fringe_y = bead_cy + bead_r
    for i in range(3):
        fx = bead_cx - bead_r // 2 + i * bead_r // 2
        draw.line(
            [(fx, tassel_fringe_y), (fx, tassel_fringe_y + bead_r)],
            fill=accent_color, width=max(2, line_width - 1)
        )


def make_student_icon(size=512):
    render_size = size * 2
    grad = create_gradient(render_size, STUDENT_GRADIENT)

    radius = render_size // 5
    img = apply_rounded_mask(grad, render_size, radius)
    img = add_top_gloss(img, render_size)
    img = add_inner_shadow(img, render_size, radius)

    cap_cx = render_size // 2
    cap_cy = int(render_size * 0.52)
    cap_size = int(render_size * 0.55)

    draw = ImageDraw.Draw(img)
    draw_graduation_cap(
        draw, cap_cx, cap_cy, cap_size,
        color=(255, 255, 255, 255),
        accent_color=(255, 220, 150, 255)
    )

    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def draw_chalkboard(draw, cx, cy, board_w, board_h, frame_color=(255, 255, 255, 255),
                    board_color=(38, 50, 64, 255), chalk_color=(255, 255, 255, 235),
                    chalk_accent=(255, 220, 150, 235)):
    frame_thickness = max(6, int(board_w * 0.05))

    frame_rect = [
        cx - board_w // 2 - frame_thickness,
        cy - board_h // 2 - frame_thickness,
        cx + board_w // 2 + frame_thickness,
        cy + board_h // 2 + frame_thickness
    ]
    frame_radius = max(4, frame_thickness // 2)
    draw.rounded_rectangle(frame_rect, radius=frame_radius, fill=frame_color)

    inner_rect = [
        cx - board_w // 2,
        cy - board_h // 2,
        cx + board_w // 2,
        cy + board_h // 2
    ]
    inner_radius = max(2, frame_thickness // 4)
    draw.rounded_rectangle(inner_rect, radius=inner_radius, fill=board_color)

    text_top = cy - int(board_h * 0.28)
    text_left = cx - int(board_w * 0.32)
    text_right = cx + int(board_w * 0.32)
    line_count = 4
    line_spacing = int(board_h * 0.14)
    line_thickness = max(3, int(board_w * 0.025))

    for i in range(line_count):
        y = text_top + i * line_spacing
        if i == 0:
            x_end = text_right
            draw.line([(text_left, y), (x_end, y)], fill=chalk_color, width=line_thickness + 1)
        elif i % 2 == 1:
            x_end = text_right - int(board_w * 0.15)
            draw.line([(text_left, y), (x_end, y)], fill=chalk_color, width=line_thickness)
        else:
            x_end = text_right - int(board_w * 0.05)
            draw.line([(text_left, y), (x_end, y)], fill=chalk_color, width=line_thickness)

    chalk_w = max(20, int(board_w * 0.18))
    chalk_h = max(6, int(board_w * 0.04))
    chalk_x = cx + board_w // 4
    chalk_y = cy + board_h // 2 + frame_thickness // 2 - chalk_h // 2

    draw.rounded_rectangle(
        [chalk_x, chalk_y, chalk_x + chalk_w, chalk_y + chalk_h],
        radius=chalk_h // 2,
        fill=chalk_color
    )

    tip_w = chalk_h
    tip_points = [
        (chalk_x + chalk_w, chalk_y),
        (chalk_x + chalk_w + tip_w, chalk_y + chalk_h // 2),
        (chalk_x + chalk_w, chalk_y + chalk_h),
    ]
    draw.polygon(tip_points, fill=chalk_accent)


def make_teacher_icon(size=512):
    render_size = size * 2
    grad = create_gradient(render_size, TEACHER_GRADIENT)

    radius = render_size // 5
    img = apply_rounded_mask(grad, render_size, radius)
    img = add_top_gloss(img, render_size)
    img = add_inner_shadow(img, render_size, radius)

    board_cx = render_size // 2
    board_cy = int(render_size * 0.5)
    board_w = int(render_size * 0.55)
    board_h = int(render_size * 0.42)

    draw = ImageDraw.Draw(img)
    draw_chalkboard(
        draw, board_cx, board_cy, board_w, board_h,
        frame_color=(255, 255, 255, 255),
        board_color=(38, 50, 64, 255),
        chalk_color=(255, 255, 255, 235),
        chalk_accent=(255, 220, 150, 235)
    )

    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 50)
    print("班级桌面助手 - 图标生成")
    print("=" * 50)
    print(f"输出目录: {out_dir}")
    print()

    print("生成 student.png ...")
    student_png = make_student_icon(512)
    student_png_path = os.path.join(out_dir, 'student.png')
    student_png.save(student_png_path)
    print(f"  ✓ {student_png_path}")

    print("生成 teacher.png ...")
    teacher_png = make_teacher_icon(512)
    teacher_png_path = os.path.join(out_dir, 'teacher.png')
    teacher_png.save(teacher_png_path)
    print(f"  ✓ {teacher_png_path}")

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

    print("生成 student.ico ...")
    student_ico_path = os.path.join(out_dir, 'student.ico')
    student_png.save(student_ico_path, format='ICO', sizes=ico_sizes)
    print(f"  ✓ {student_ico_path}")

    print("生成 teacher.ico ...")
    teacher_ico_path = os.path.join(out_dir, 'teacher.ico')
    teacher_png.save(teacher_ico_path, format='ICO', sizes=ico_sizes)
    print(f"  ✓ {teacher_ico_path}")

    print()
    print("=" * 50)
    print("完成！")
    print("=" * 50)
    print()
    print("图标已生成在 src/ 目录下，未替换任何 EXE 文件")
    print("如需应用到 EXE，请手动使用资源编辑器或重新打包")


if __name__ == "__main__":
    main()
