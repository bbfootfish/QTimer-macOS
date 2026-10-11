"""
[macOS 补丁 3] 全屏穿透 —— 让悬浮窗显示在「其他应用的原生全屏 Space」之上

【问题现象】
  播放 PowerPoint 全屏放映时，QTimer 悬浮窗消失（用户描述："播放ppt的时候就不见了"）。

【根因】
  macOS 会为进入原生全屏的应用单独创建一个 Space（空间），
  其他应用的窗口默认被留在原 Space，因此用户看不见。
  实测 Qt 的 Tool 窗口（在 macOS 上是 QNSPanel）出厂属性为：

      collectionBehavior = 258 = FullScreenAuxiliary | MoveToActiveSpace
                                 ^^^^^^^^^^^^^^^^^^^^^ 缺 CanJoinAllSpaces
      styleMask          = 14                        ^ 缺 NonactivatingPanel
      hidesOnDeactivate  = True                      ^ 应用失焦即隐藏
      level              = 8  (NSModalPanelWindowLevel，这一项本来就对)

  `MoveToActiveSpace` 的语义是「窗口被激活时才移动到当前空间」，
  与「常驻所有空间」完全不同，所以全屏一切换就看不见了。

【解法】按 AppKit 标准做法调整四项属性：
      collectionBehavior = CanJoinAllSpaces | FullScreenAuxiliary
      styleMask         |= NonactivatingPanel
      hidesOnDeactivate  = False
      floatingPanel      = True

【实测结果】（本机 macOS 26.6.2 / PySide6 6.12.0）
  补丁前：另一应用进入原生全屏 Space 时
          isOnActiveSpace=False 且不在 CGWindowListCopyWindowInfo(OnScreenOnly) 中
  补丁后：同一场景 isOnActiveSpace=True 且仍在在屏窗口列表中（两个独立判据一致）

【设计要点】
  1. 覆盖「应用内所有可见的 Qt 窗口」，而不只是悬浮窗本身。
     原因：实测出现过补丁未落到目标窗口的窗口态（layer=0 的另一个窗口），
     逐个点名会留盲区；按类名前缀 QNS 批量处理更稳。
  2. 幂等：可反复调用。
  3. Qt 在 setWindowFlags() 时会销毁并重建底层 NSWindow，新窗口会退回出厂属性，
     因此必须靠 showEvent + 低频看门狗双重重申。

【依赖】
  需要 pyobjc-framework-Cocoa。缺失时本模块自动降级为空操作，不影响程序运行。
"""

import os
import sys
import time

__all__ = [
    "enable_fullscreen_overlay",
    "enable_fullscreen_overlay_all",
    "install_watchdog",
    "is_available",
    "OVERLAY_AVAILABLE",
]

# 诊断开关：环境变量 QTIMER_OVERLAY_DEBUG=1 时，把每次调用的结果写入日志文件。
_DEBUG = os.environ.get("QTIMER_OVERLAY_DEBUG") == "1"
_LOG_PATH = os.environ.get("QTIMER_OVERLAY_LOG", "/tmp/qtimer_overlay.log")


def _log(msg: str) -> None:
    if not _DEBUG:
        return
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


OVERLAY_AVAILABLE = False

if sys.platform == "darwin":
    try:
        import objc
        from AppKit import (
            NSApplication,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowStyleMaskNonactivatingPanel,
        )

        OVERLAY_AVAILABLE = True
    except Exception:  # pragma: no cover - 缺少 pyobjc 时降级为空操作
        OVERLAY_AVAILABLE = False

# 仅处理 Qt 自己创建的窗口，避免误伤系统窗口（NSStatusBarWindow 等）
_QT_WINDOW_PREFIX = "QNS"

# NSModalPanelWindowLevel
_NS_MODAL_PANEL_LEVEL = 8

_applied = set()


def is_available() -> bool:
    return OVERLAY_AVAILABLE


def _apply_to(win) -> bool:
    """给单个 NSWindow 套用全屏穿透属性。"""
    try:
        before = (win.collectionBehavior(), win.styleMask(), bool(win.hidesOnDeactivate()))
        win.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        win.setStyleMask_(win.styleMask() | NSWindowStyleMaskNonactivatingPanel)
        win.setHidesOnDeactivate_(False)
        win.setFloatingPanel_(True)
        win.setBecomesKeyOnlyIfNeeded_(True)
        win.setLevel_(_NS_MODAL_PANEL_LEVEL)
        after = (win.collectionBehavior(), win.styleMask(), bool(win.hidesOnDeactivate()))
        _applied.add(win.windowNumber())
        _log(f"OK class={win.className()} num={win.windowNumber()} {before} -> {after}")
        return True
    except Exception as e:
        _log(f"单窗口设置失败 {type(e).__name__}: {e}")
        return False


def enable_fullscreen_overlay_all() -> int:
    """给本应用所有可见的 Qt 窗口套用全屏穿透属性，返回处理成功的窗口数。

    批量处理而非逐个点名，是为了不依赖「正确识别出目标窗口」这一前提。
    """
    if not OVERLAY_AVAILABLE:
        return 0
    count = 0
    try:
        for win in NSApplication.sharedApplication().windows():
            try:
                if not win.isVisible():
                    continue
                if not win.className().startswith(_QT_WINDOW_PREFIX):
                    continue
                if _apply_to(win):
                    count += 1
            except Exception:
                continue
    except Exception as e:
        _log(f"枚举窗口失败 {type(e).__name__}: {e}")
    return count


def _ns_window_of(widget):
    """从指定 Qt widget 精确定位它自己的 NSWindow。

    实测：widget.winId() 返回 QNSView 指针，取其 .window() 得到的实例，
    与 NSApplication.sharedApplication().windows() 中同一 windowNumber 的对象完全一致。
    """
    try:
        view = objc.objc_object(c_void_p=int(widget.winId()))
        win = view.window()
        if win is not None:
            return win
    except Exception:
        pass
    return None


def enable_fullscreen_overlay(widget) -> bool:
    """针对单个 widget 的入口（供 showEvent 调用）。

    widget 不可见时回退为批量处理，避免因拿不到窗口而漏掉。
    """
    if not OVERLAY_AVAILABLE:
        return False
    try:
        if widget is not None and widget.isVisible():
            win = _ns_window_of(widget)
            if win is not None:
                return _apply_to(win)
    except Exception:
        pass
    return enable_fullscreen_overlay_all() > 0


def install_watchdog(widget, interval_ms: int = 1000):
    """挂一个低频看门狗，周期性重申全屏穿透属性。

    必要性：Qt 在 setWindowFlags() 时会销毁并重建底层 NSWindow，
    新窗口会退回出厂属性；showEvent 覆盖不全，看门狗保证任何情况下都能自愈。

    返回创建的 QTimer，失败返回 None。
    """
    if not OVERLAY_AVAILABLE:
        _log("看门狗：未安装（pyobjc 不可用）")
        return None
    try:
        from PySide6.QtCore import QTimer

        timer = QTimer(widget)
        timer.setInterval(interval_ms)
        timer.timeout.connect(enable_fullscreen_overlay_all)
        timer.start()
        _log(f"看门狗已启动 interval={interval_ms}ms")
        return timer
    except Exception as e:
        _log(f"看门狗异常 {type(e).__name__}: {e}")
        return None
