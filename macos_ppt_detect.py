"""
[macOS 补丁 4] PPT 放映联动检测 —— macOS 实现

【背景】
上游的 `is_ppt_slideshow_active()` 在非 Windows 上直接 `return False`，
所以「PPT放映联动」开关在 macOS 上是空转的（配置能存、界面能勾，但永远不触发）。

【为什么不用 AppleScript / System Events】
实测两条路都走不通：
  - `tell application "System Events" ...` → 权限违例 (-10004)
  - `tell application "Microsoft PowerPoint" to get name of every presentation`
    → 权限违例 (-10004)
  均需用户手动授予「自动化」权限，不适合作为常驻 600ms 轮询的实现。

【本方案的原理】
用 CoreGraphics 的窗口列表（`CGWindowListCopyWindowInfo`）做纯几何判断：
  幻灯片放映 = 演示类应用拥有一个「铺满整块屏幕」的窗口。

实测数据（本机 macOS 26.6.2，屏幕 1470x956）：
  - PowerPoint 编辑态窗口：1470 x 874 → 高度覆盖率 0.914（菜单栏占 82pt）
  - 原生全屏窗口：      覆盖率 1.0 / 1.0
  两者相差明显，取阈值 0.98 可干净区分。

【权限】
`kCGWindowOwnerName`（窗口属主应用名）与 `kCGWindowBounds`（窗口尺寸）
**无需「屏幕录制」权限**即可读取，实测 30/30 窗口全部可读。
（受限的是 `kCGWindowName` 窗口标题，本方案不使用。）

【依赖】
需要 pyobjc-framework-Quartz。缺失时降级为「永远返回 False」，不影响程序运行。
"""

import os
import sys
import time

__all__ = ["is_slideshow_active", "describe", "DETECT_AVAILABLE"]

# 诊断开关：QTIMER_PPT_DEBUG=1 时记录检测状态变迁，便于验证联动是否真的触发
_DEBUG = os.environ.get("QTIMER_PPT_DEBUG") == "1"
_LOG_PATH = os.environ.get("QTIMER_PPT_LOG", "/tmp/qtimer_ppt.log")

# 允许用环境变量覆盖要识别的应用名，便于测试与支持非主流演示软件
# 例：QTIMER_PPT_APPS="powerpoint,keynote"
_APPS_ENV = os.environ.get("QTIMER_PPT_APPS", "")


def _log(msg: str) -> None:
    if not _DEBUG:
        return
    try:
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


DETECT_AVAILABLE = False

if sys.platform == "darwin":
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionAll,
            kCGWindowListExcludeDesktopElements,
            kCGNullWindowID,
        )
        from AppKit import NSScreen

        DETECT_AVAILABLE = True
    except Exception:  # pragma: no cover
        DETECT_AVAILABLE = False

# 演示类应用的窗口属主名匹配片段（全部小写）
PRESENTATION_APP_PATTERNS = (
    "powerpoint",
    "keynote",
    "wps",
    "wpp",
    "impress",
    "libreoffice",
    "onlyoffice",
)

# 环境变量覆盖（逗号分隔）
if _APPS_ENV.strip():
    PRESENTATION_APP_PATTERNS = tuple(
        p.strip().lower() for p in _APPS_ENV.split(",") if p.strip()
    )

# 状态变迁记录（仅用于诊断日志）
_last_state = None

# 窗口尺寸与屏幕尺寸允许的误差（点）。超过即认为不是「正好铺满这块屏」。
SIZE_TOLERANCE = 8.0


def _screen_frames():
    try:
        return [(s.frame().size.width, s.frame().size.height) for s in NSScreen.screens()]
    except Exception:
        return []


def _matches_screen(ww, wh, screens) -> bool:
    """窗口尺寸是否与某块屏幕**一致**（而不是「大于等于」）。

    踩过的坑：最初用「覆盖率 >= 98%」判定，结果 WPS Office 一个 1920x1010 的窗口
    （比 1470x956 的屏幕还大）被误判为全屏放映。因此必须要求尺寸**接近相等**，
    同时排除明显大于屏幕的窗口。
    """
    for sw, sh in screens:
        if sw <= 0 or sh <= 0:
            continue
        if abs(ww - sw) <= SIZE_TOLERANCE and abs(wh - sh) <= SIZE_TOLERANCE:
            return True
    return False


def describe(app_patterns=None) -> dict:
    """返回本次检测的中间数据，便于排查（不参与判定逻辑）。"""
    if not DETECT_AVAILABLE:
        return {"available": False}
    patterns = tuple(p.lower() for p in (app_patterns or PRESENTATION_APP_PATTERNS))
    screens = _screen_frames()
    seen = []
    matched = []
    try:
        for w in CGWindowListCopyWindowInfo(
            kCGWindowListOptionAll | kCGWindowListExcludeDesktopElements, kCGNullWindowID
        ):
            owner = (w.get("kCGWindowOwnerName") or "").lower()
            b = w.get("kCGWindowBounds") or {}
            ww, wh = b.get("Width", 0) or 0, b.get("Height", 0) or 0
            if ww < 100 or wh < 100:
                continue
            if not any(p in owner for p in patterns):
                continue
            entry = {
                "owner": w.get("kCGWindowOwnerName"),
                "w": int(ww), "h": int(wh),
                "x": int(b.get("X", 0)), "y": int(b.get("Y", 0)),
                "layer": w.get("kCGWindowLayer"),
                "onscreen": bool(w.get("kCGWindowIsOnscreen")),
                "match": _matches_screen(ww, wh, screens),
            }
            seen.append(entry)
            if entry["match"]:
                matched.append(entry)
    except Exception as e:
        return {"available": True, "error": f"{type(e).__name__}: {e}"}
    return {
        "available": True,
        "screens": screens,
        "presentation_windows": seen,
        "fullscreen_presentation_windows": matched,
        "active": bool(matched),
    }


def is_slideshow_active(app_patterns=None) -> bool:
    """检测是否有演示类应用正在全屏放映。

    用 `kCGWindowListOptionAll` 而不是 OnScreenOnly：
    实测原生全屏窗口在窗口列表里 `kCGWindowIsOnscreen` 为 False，
    用 OnScreenOnly 会直接漏掉它。
    """
    global _last_state
    if not DETECT_AVAILABLE:
        return False
    patterns = tuple(p.lower() for p in (app_patterns or PRESENTATION_APP_PATTERNS))
    screens = _screen_frames()
    if not screens:
        return False

    result = False
    hit = None
    try:
        for w in CGWindowListCopyWindowInfo(
            kCGWindowListOptionAll | kCGWindowListExcludeDesktopElements, kCGNullWindowID
        ):
            owner = (w.get("kCGWindowOwnerName") or "").lower()
            if not any(p in owner for p in patterns):
                continue
            b = w.get("kCGWindowBounds") or {}
            ww = b.get("Width", 0) or 0
            wh = b.get("Height", 0) or 0
            if _matches_screen(ww, wh, screens):
                result = True
                hit = {"owner": w.get("kCGWindowOwnerName"), "w": int(ww), "h": int(wh)}
                break
    except Exception:
        result = False

    if result != _last_state:
        _log(f"状态变迁 {_last_state} -> {result}  命中={hit}")
        _last_state = result
    return result
