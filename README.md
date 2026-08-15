# 班级桌面助手（Classroom Desktop Assistant）

> 面向教学场景的轻量级桌面应用，学生端与教师端协同工作，覆盖课表编排、作业记录与数据流转。

**版本**：v1.2.3-Beta.1  
**作者**：CHCZ-LeonLin、FENG

> 下载预编译版本：[GitHub Releases](https://github.com/CHCZ-LeonLin/ClassroomDesktopAssistant/releases)

---

## 功能简介

### 学生端

- **仪表板**：快速查看今日课程与待办作业
- **作业记录**：记录并管理每日作业
- **课程表**：只读展示，支持导入教师编排的课程表
- **系统托盘**：常驻后台，提供快捷操作
- **数据导入**：一键导入教师端导出的课程表 JSON 文件

### 教师端

- **课程表编排**：灵活编排班级课表
- **科目管理**：添加、编辑、删除教学科目
- **课表导出**：导出为 JSON 文件供学生端导入

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| GUI 框架 | PySide6 (>=6.6.0,<6.9) |
| 界面渲染 | QtWebEngine（HTML + JavaScript） |
| 打包工具 | PyInstaller |

---

## 项目结构

```
ClassroomDesktopAssistant/
├── README.md               # 项目说明
├── LICENSE.md              # 开源许可
├── .gitignore              # 忽略构建产物与本地配置
└── src/                    # 完整源代码
    ├── app.py              # 学生端主程序
    ├── teacher_app.py      # 教师端主程序
    ├── student.html        # 学生端界面
    ├── teacher.html        # 教师端界面
    ├── build.spec          # PyInstaller 打包配置
    ├── requirements.txt    # Python 依赖
    ├── run.bat             # 一键运行学生端
    ├── convert_ico.py      # 图标生成脚本
    ├── generate_icons.py   # 图标生成脚本
    ├── student.ico / student.png
    └── teacher.ico / teacher.png
```

打包产物输出到 `src/dist/`（学生端 / 教师端），该目录已被 `.gitignore` 忽略。

---

## 快速开始

### 使用预编译版本（推荐）

1. 前往 [GitHub Releases](https://github.com/CHCZ-LeonLin/ClassroomDesktopAssistant/releases) 下载对应压缩包：
   - 学生端：`ClassroomDesktopAssistant-Student-v1.2.3-Beta.1-win64.zip`
   - 教师端：`ClassroomDesktopAssistant-Teacher-v1.2.3-Beta.1-win64.zip`
2. 解压压缩包
3. 运行目录内的 exe（需与同级的 `_internal` 目录放在一起）：
   - 学生端：`ClassroomDesktopAssistant.exe`
   - 教师端：`ClassroomDesktopAssistant-Teacher.exe`

### 从源码运行

```bash
# 进入源码目录
cd src

# 安装依赖
pip install -r requirements.txt

# 运行学生端
python app.py

# 运行教师端
python teacher_app.py
```

> Windows 下也可双击 `run.bat` 快速启动学生端。

### 打包为可执行文件

```bash
cd src
pyinstaller --clean --noconfirm build.spec
```

打包结果位于 `src/dist/student` 与 `src/dist/teacher`。

---

## 数据流转

```
教师端编排课表 → 导出 JSON 文件 → 学生端导入 → 课程表更新
```

1. **教师端** 编排完成后导出课程表为 JSON 文件
2. **学生端** 通过系统托盘或主界面导入该 JSON 文件
3. 学生端课程表自动更新为最新内容

---

## 注意事项

- 学生端课程表为只读，如需修改请联系教师重新编排导出
- 导入课表会覆盖原有课程数据，操作前请确认
- 教师端导出的 JSON 文件可多班共用，建议文件名包含班级信息

---

## 许可证

本项目基于 [MIT License](LICENSE.md) 开源。
