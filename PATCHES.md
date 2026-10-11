# QTimer macOS 本地补丁说明

本机安装方式：**源码安装**（上游 GitHub Releases 仅提供 Windows `.exe`，无 macOS 构建）。

- 上游仓库：https://github.com/Qwejay/QTimer
- 上游版本：v1.4.0（commit `033cc23`，2026-08-26）
- 安装日期：2026-10-10
- 安装路径：`~/Applications/QTimer.app`
- 运行环境：Python 3.13.13 (Homebrew) + PySide6_Essentials 6.12.0
- 额外依赖：`pyobjc-framework-Cocoa`、`pyobjc-framework-Quartz`（补丁 3 需要，已装入 venv）

## ⚠️ 升级须知

上游代码**未做 macOS 适配**。若将来从上游拉取新版 `main.py` 覆盖，
**必须重新应用以下四处补丁**，否则程序在 macOS 上无法启动、显示异常，全屏放映时消失，
或「PPT放映联动」开关空转。

---

## 补丁 1：`ctypes.WINFUNCTYPE` 导入期崩溃（阻断级）

**位置**：模块级常量定义处（原第 47 行）

**现象**：`ctypes.WINFUNCTYPE` 仅存在于 Windows。在 macOS 上该语句位于模块顶层，
导入即抛 `AttributeError: module 'ctypes' has no attribute 'WINFUNCTYPE'`，
程序完全无法启动。

**说明**：该类型只被 `is_ppt_slideshow_active()` 的 Windows 分支使用，
而该函数开头已有 `platform.system() != "Windows"` 早退判断，故非 Windows 平台用
`CFUNCTYPE` 等价占位即可，不改变任何行为。

```python
if platform.system() == "Windows":
    WNDENUMPROC_TYPE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
else:
    WNDENUMPROC_TYPE = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
```

## 补丁 2：默认字体「微软雅黑」不存在（显示级）

**位置**：`Config.__init__` 与 `FloatBar.__init__`，共 4 处

**现象**：默认字体为「微软雅黑」（Windows 字体），macOS 未内置，
导致计时数字与环节文字回退到默认字体，渲染发虚且中英文基线不齐。

**修正**：改为 macOS 系统级中文字体 `PingFang SC`（苹方）。

```python
self.font: str = "PingFang SC"          # Config
self.stage_font: str = "PingFang SC"    # Config
self._font_family = "PingFang SC"       # FloatBar
self._stage_font_family = "PingFang SC" # FloatBar
```

## 补丁 3：全屏放映时悬浮窗消失（功能级，核心）

**位置**：新增独立模块 `macos_overlay.py`；`main.py` 三处挂钩（导入段 / `FloatBar.__init__` / `FloatBar.showEvent`）

**现象**：PowerPoint 一进入全屏放映，悬浮计时窗就不见了。

**根因**：macOS 为进入**原生全屏**的应用单独创建一个 Space（空间），
其他应用的窗口默认被留在原 Space。实测 Qt 的 `Tool` 窗口（在 macOS 上是 `QNSPanel`）出厂属性为：

| 属性 | 出厂值 | 问题 |
|---|---|---|
| `collectionBehavior` | `258` = `FullScreenAuxiliary \| MoveToActiveSpace` | **缺 `CanJoinAllSpaces`** |
| `styleMask` | `14` | **缺 `NonactivatingPanel`** |
| `hidesOnDeactivate` | `True` | 应用失焦即隐藏 |
| `level` | `8`（`NSModalPanelWindowLevel`） | 本来就对 |

`MoveToActiveSpace` 的语义是「窗口被激活时才移动到当前空间」，与「常驻所有空间」完全不同 ——
所以全屏一切换，窗口就留在了旧空间。

**修正**（AppKit 标准做法）：

```python
win.setCollectionBehavior_(CanJoinAllSpaces | FullScreenAuxiliary)   # 258 -> 257
win.setStyleMask_(win.styleMask() | NonactivatingPanel)             # 14  -> 142
win.setHidesOnDeactivate_(False)
win.setFloatingPanel_(True)
win.setBecomesKeyOnlyIfNeeded_(True)
win.setLevel_(8)
```

**实测结果**（macOS 26.6.2 / PySide6 6.12.0，两个独立判据一致）：

| 场景 | `isOnActiveSpace()` | 在 `CGWindowListCopyWindowInfo(OnScreenOnly)` 中 |
|---|---|---|
| 补丁前 | `False` | ❌ 不在 |
| 补丁后 | `True` | ✅ 在 |

**注意**：Qt 在 `setWindowFlags()` 时会**销毁并重建底层 NSWindow**，新窗口会退回出厂属性。
因此必须 `showEvent` + 1 秒看门狗双重重申，缺一不可。

**升级时需一并保留**：`macos_overlay.py` 整个文件，以及 `main.py` 中
`import macos_overlay`、`install_watchdog`、`showEvent` 三处调用。

## 补丁 4：PPT 放映联动在 macOS 上为空转（功能级）

**位置**：新增独立模块 `macos_ppt_detect.py`；`main.py` 的 `is_ppt_slideshow_active()` 加 Darwin 分支

**现象**：设置里的「PPT放映联动 —— 当检测到幻灯片全屏放映时，自动开始计时」
开关在 macOS 上勾了也没用，永远不触发。

**根因**：上游函数第 64 行是 `if platform.system() != "Windows": return False`，
macOS 直接短路。功能接线是完整的（`App._check_ppt_status` 每 600ms 轮询，
放映开始自动恢复计时、结束自动暂停），只是检测函数永远返回 False。

**为什么不用 AppleScript**（两条路实测都被系统拦下）：

| 方案 | 结果 |
|---|---|
| `tell application "System Events" ...` | 权限违例 `-10004` |
| `tell application "Microsoft PowerPoint" to get name of every presentation` | 权限违例 `-10004` |

均需用户手动授予「自动化」权限，不适合作为常驻 600ms 轮询的实现。

**本方案：CoreGraphics 窗口几何判断**
幻灯片放映 = 演示类应用拥有一个「尺寸正好等于某块屏幕」的窗口。

实测数据（屏幕 1470×956）：

| 状态 | 窗口尺寸 | 判定 |
|---|---|---|
| PowerPoint 编辑态 | 1470 × 874（菜单栏占 82pt） | 不是放映 |
| 原生全屏窗口 | 1470 × 956 | **是放映** |

**两个必须注意的实现细节**：

1. **必须用 `kCGWindowListOptionAll`，不能用 `OnScreenOnly`。**
   实测原生全屏窗口在窗口列表中 `kCGWindowIsOnscreen` 为 **False**，
   用 OnScreenOnly 会直接漏掉它。
2. **必须用「尺寸近似相等」，不能用「覆盖率 ≥ 98%」。**
   初版用覆盖率判定，结果 WPS Office 一个 **1920×1010** 的窗口
   （比屏幕还大）被误判为放映 —— 因为「大于等于」把「比屏幕大」也算成了铺满。
   改为 `|窗口尺寸 − 屏幕尺寸| ≤ 8pt` 后消除。

**权限**：`kCGWindowOwnerName`（属主应用名）与 `kCGWindowBounds`（窗口尺寸）
**无需「屏幕录制」权限**即可读取，实测 30/30 窗口全部可读。
（受限的是 `kCGWindowName` 窗口标题，本方案不使用。）

**可配置**：环境变量 `QTIMER_PPT_APPS="powerpoint,keynote"` 可覆盖要识别的应用名。
默认匹配：`powerpoint` / `keynote` / `wps` / `wpp` / `impress` / `libreoffice` / `onlyoffice`。

**验证结果**（整链路，直接观察 `TimerController.paused`）：

| 阶段 | `paused` | 结果 |
|---|---|---|
| 静置 2s | `True` → `True` | ✅ 无变化 |
| 放映开始 | `True` → `False` | ✅ 自动开始计时（实测秒数 90.0 → 88.2） |
| 放映结束 | `False` → `True` | ✅ 自动暂停计时 |

其他验证：PowerPoint 编辑态不误判；属主名过滤有效（非演示类应用全屏也不触发）；
屏幕列表为空不崩溃；连续 50 次调用无异常，单次 3.66ms（占 600ms 周期的 0.61%）。

**升级时需一并保留**：`macos_ppt_detect.py` 整个文件，以及 `main.py` 中
`import macos_ppt_detect` 与 `is_ppt_slideshow_active()` 的 Darwin 分支。

---

## 已知功能差异（非补丁，无法在 macOS 修复）

| 功能 | Windows | macOS | 原因 |
|---|---|---|---|
| PPT 放映自动检测 / 自动开始计时 | ✅ | ✅（本机已补，见补丁 4） | 上游仅实现 Windows 分支，本机用 CoreGraphics 窗口几何判断补齐 |
| 全局热键（应用失焦时仍生效） | ✅ | ❌ | 依赖 `keyboard` 库，macOS 需 root + 辅助功能授权；现降级为 Qt 应用内快捷键 |

其余功能（无误差计时、多环节流转、变色闪烁提醒、`afplay` 提示音、窗口位置记忆、
自定义音效、多显示器拖拽、单实例锁）在 macOS 上均正常。

## 配置文件位置

`~/Library/Preferences/QTimer/config.json`（首次保存设置时生成）
