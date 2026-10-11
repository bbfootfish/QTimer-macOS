# QTimer-macOS

> macOS 适配版 · 基于 [Qwejay/QTimer](https://github.com/Qwejay/QTimer) 修改

**QTimer** 是一款专为**说课、答辩、演讲、会议**打造的桌面悬浮倒计时工具。
极简无边框半透明设计，平时安静悬浮在屏幕角落，鼠标悬停时如抽屉般展开控制面板。

原版只发布 Windows `.exe`，macOS 需自行跑源码。本仓库在 macOS 上把它跑通，并**补齐了两个 macOS 上完全不可用的关键功能**：

| | 功能 | 状态 |
|---|---|---|
| 🔴 | **窗口置顶层修正** —— 全屏放映 PPT 时悬浮窗不再消失 | 已修复 |
| 🔴 | **PPT 放映联动** —— 检测到幻灯片全屏放映时自动开始计时 | 已实现 |

---

## ⚠️ 来源与许可（请先读这一段）

本仓库是 **[Qwejay/QTimer](https://github.com/Qwejay/QTimer)** 的**修改版衍生作品**，不是原创项目。

| 项目 | 说明 |
|---|---|
| 上游仓库 | <https://github.com/Qwejay/QTimer> |
| 上游版本 | v1.4.0（commit `033cc23`，2026-08-26） |
| 上游作者 | QwejayHuang |
| 上游许可证 | **GNU General Public License v3.0** |
| **本仓库许可证** | **GNU General Public License v3.0**（继承上游） |
| 修改日期 | 2026-10-10 ~ 2026-10-11 |
| 修改人 | [bbfootfish](https://github.com/bbfootfish) |

**关于许可**：上游采用 GPL-3.0，该许可证要求衍生作品必须以相同条款发布，
因此本仓库同样是 **GPL-3.0**，并完整保留上游的 `LICENSE` 与版权声明。
若你需要用于闭源商业场景，请联系上游作者获取其他授权。

按 GPL-3.0 §5a 要求，**哪些文件被修改、修改了什么、何时修改**，
详见 [PATCHES.md](PATCHES.md) 与 [NOTICE.md](NOTICE.md)，
源码文件头部也带有修改声明。

---

## 🚀 快速开始

### 方式一：一键安装脚本（推荐）

```bash
git clone https://github.com/bbfootfish/QTimer-macOS.git
cd QTimer-macOS
bash scripts/install_macos.sh
```

脚本会创建独立虚拟环境、安装依赖，并在 `~/Applications/QTimer.app` 生成可双击启动的应用。
如需安装到系统级目录：

```bash
bash scripts/install_macos.sh /Applications/QTimer.app
```

### 方式二：手动运行

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements-macos.txt
./venv/bin/python main.py
```

> 要求 Python ≥ 3.9。建议用 Homebrew 或 python.org 的 Python，系统自带 `/usr/bin/python3` 也可用。

### 方式三：打包成零依赖的独立应用（进阶）

```bash
bash scripts/build_standalone.sh
```

用 PyInstaller 把 Python 运行时与 Tk/PySide 一并冻结进 `.app`，产物体积约 32 MB，
**不依赖任何外部 Python 环境**，可直接拷给他人使用。

---

## 🖱 使用

1. 启动后悬浮条出现在屏幕上（默认位置会被记住）
2. **鼠标悬停** → 展开控制面板
3. **拖动** → 按住任意位置移动
4. 右键悬浮条或点齿轮进入设置：环节时长、配色、透明度、字体、提示音、快捷键

### 与 PowerPoint 配合

开启「**PPT放映联动**」后：

- 开始幻灯片全屏放映 → 计时器**自动开始**
- 结束放映 → 计时器**自动暂停**
- 放映中你手动点了按钮 → 本次放映内不再自动接管（尊重你的操作）

---

## 🔧 本仓库相对上游的改动

共 4 处，全部为 macOS 适配，**未改动任何业务逻辑**。
逐条详解（含根因、实测数据、复现方法）见 **[PATCHES.md](PATCHES.md)**。

### 补丁 1：`ctypes.WINFUNCTYPE` 导入期崩溃（阻断级）

上游在模块顶层直接调用 `ctypes.WINFUNCTYPE`，该属性仅存在于 Windows。
macOS 上**导入即抛 `AttributeError`，程序完全无法启动**。
改为非 Windows 平台用等价的 `CFUNCTYPE` 占位。

### 补丁 2：默认字体「微软雅黑」不存在（显示级）

上游默认字体为 Windows 的「微软雅黑」，macOS 未内置，导致文字回退渲染、中英文基线不齐。
改用 macOS 系统级中文字体 **PingFang SC（苹方）**。

### 补丁 3：全屏放映时悬浮窗消失（功能级，核心）

**现象**：PPT 一进全屏放映，悬浮窗就不见了。

**根因**：macOS 会为进入**原生全屏**的应用单独创建一个 Space（空间），
其他应用的窗口默认被留在原 Space。实测 Qt 的 `Tool` 窗口（macOS 上是 `QNSPanel`）出厂属性为：

| 属性 | 出厂值 | 问题 |
|---|---|---|
| `collectionBehavior` | `258` = `FullScreenAuxiliary \| MoveToActiveSpace` | **缺 `CanJoinAllSpaces`** |
| `styleMask` | `14` | **缺 `NonactivatingPanel`** |
| `hidesOnDeactivate` | `True` | 应用失焦即隐藏 |

`MoveToActiveSpace` 的语义是「窗口被激活时才移动到当前空间」，与「常驻所有空间」完全不同 ——
所以全屏一切换，窗口就留在旧空间了。

**修正**（AppKit 标准做法，见 `macos_overlay.py`）：

```python
win.setCollectionBehavior_(CanJoinAllSpaces | FullScreenAuxiliary)   # 258 -> 257
win.setStyleMask_(win.styleMask() | NonactivatingPanel)             # 14  -> 142
win.setHidesOnDeactivate_(False)
```

> 关键前提：**必须用 NSPanel**。普通 `NSWindow` 把窗口层级调到再高都没用。

**踩过的坑**：Qt 在 `setWindowFlags()` 时会**销毁并重建底层 NSWindow**，
新窗口会退回出厂属性 —— 必须靠 `showEvent` + 1 秒看门狗**双重重申**，缺一不可。

### 补丁 4：PPT 放映联动在 macOS 上为空转（功能级）

**根因**：上游 `is_ppt_slideshow_active()` 在非 Windows 上直接 `return False`，
macOS 分支被短路。功能接线本身是完整的，只是检测函数永远返回 False。

**为什么不用 AppleScript**：两条路都被系统权限拦截（`System Events` 与 PowerPoint 的
`get name of every presentation` 均报 `-10004` 权限违例），且需用户手动授权，
不适合作为常驻 600ms 轮询的实现。

**本方案**：用 CoreGraphics 窗口列表做纯几何判断 ——
**放映 = 演示类应用拥有一个尺寸正好等于某块屏幕的窗口**（见 `macos_ppt_detect.py`）。

实测数据（屏幕 1470×956）：

| 状态 | 窗口尺寸 | 判定 |
|---|---|---|
| PowerPoint 编辑态 | 1470 × 874（菜单栏占 82pt） | 不是放映 |
| 原生全屏窗口 | 1470 × 956 | **是放映** |

两个必须注意的实现细节：

1. **必须用 `kCGWindowListOptionAll`，不能用 `OnScreenOnly`。**
   实测原生全屏窗口在窗口列表里 `kCGWindowIsOnscreen` 为 `False`，用 `OnScreenOnly` 会直接漏掉。
2. **必须用「尺寸近似相等」，不能用「覆盖率 ≥ 98%」。**
   初版用覆盖率判定，结果 WPS Office 一个 **1920×1010**（比屏幕还大）的窗口被误判为放映 ——
   「大于等于」把「比屏幕大」也算成了铺满。

**权限**：`kCGWindowOwnerName` 与 `kCGWindowBounds` **无需「屏幕录制」权限**即可读取
（实测 30/30 窗口全可读）。受限的只是 `kCGWindowName`（窗口标题），本方案不使用。

**可配置**：默认识别的应用名为
`powerpoint` / `keynote` / `wps` / `wpp` / `impress` / `libreoffice` / `onlyoffice`，
可用环境变量覆盖：

```bash
QTIMER_PPT_APPS="powerpoint,keynote" ./venv/bin/python main.py
```

---

## ✅ 验证记录

| 验证项 | 方法 | 结果 |
|---|---|---|
| 全屏穿透（补丁 3） | 原生全屏 Space 下查 `isOnActiveSpace()` + `CGWindowListCopyWindowInfo(OnScreenOnly)` 双判据 | 补丁前 `False`/不在 → 补丁后 `True`/在 |
| PPT 联动（补丁 4） | 进程内实例化 `App`，直接观察 `TimerController.paused` | 静置无变化；放映开始 `True→False`（秒数 90.0→88.2 确实在走）；结束 `False→True` |
| 误判检查 | PowerPoint 编辑态、WPS 各类窗口 | 均不触发 |
| 稳定性 | 连续 50 次调用检测函数 | 无异常，单次 3.66 ms（占 600 ms 周期的 0.61%） |
| 交互回归 | `ignoresMouseEvents` / `canBecomeKeyWindow` 补丁前后对比 | 无变化 |

---

## ⚠️ 已知限制

| 限制 | 说明 |
|---|---|
| 全局热键（应用失焦时仍生效） | macOS 上不可用。依赖 `keyboard` 库，需 root + 辅助功能授权；现降级为应用内快捷键。**此项为上游限制，本仓库未解决。** |
| WPS 误判风险 | 默认匹配表含 `wps`。若 WPS Office 的窗口恰好变成屏幕尺寸，可能误触发联动。可用 `QTIMER_PPT_APPS` 收窄。 |
| 签名 | 自签 / 未公证。首次打开若被 Gatekeeper 拦截，右键 → 打开 即可放行。 |
| 未做真机放映验证 | 补丁 4 的验证使用「原生全屏窗口」复现放映场景（AppleScript 被权限拦截，无法脚本驱动真实放映）。**建议实际放映一次确认。** |

---

## 📁 目录结构

```
QTimer-macOS/
├── main.py                  # 主程序（含 4 处补丁，文件头有修改声明）
├── macos_overlay.py         # 补丁 3：全屏穿透（置顶层修正）
├── macos_ppt_detect.py      # 补丁 4：PPT 放映检测
├── default_config.json      # 默认配置
├── QTimer.icns              # 应用图标
├── requirements-macos.txt   # macOS 依赖
├── PATCHES.md               # 4 处补丁详解（根因 / 实测数据 / 复现方法）
├── NOTICE.md                # 来源与修改声明（GPL-3.0 §5a 合规）
├── LICENSE                  # GPL-3.0（来自上游，未修改）
├── docs/
│   └── README.upstream.md   # 上游原始 README（存档）
└── scripts/
    ├── install_macos.sh     # 一键安装
    └── build_standalone.sh  # PyInstaller 打包为独立应用
```

---

## 🙏 致谢

- 原始项目：[Qwejay/QTimer](https://github.com/Qwejay/QTimer) by **QwejayHuang**
  上游功能设计（多环节流转、防抢焦点、变色提醒、自定义音效、多显示器拖拽）全部出自原作者
- 本仓库只做 macOS 平台适配，功能层面的功劳归于上游

## 📄 许可证

[GNU General Public License v3.0](LICENSE) —— 与上游一致。
