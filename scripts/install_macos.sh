#!/bin/bash
#
# QTimer-macOS 一键安装脚本
#
#   用法：
#     bash scripts/install_macos.sh                 # 装到 ~/Applications/QTimer.app
#     bash scripts/install_macos.sh /Applications   # 装到系统级目录（需 admin 权限）
#     PYTHON=/opt/homebrew/bin/python3.13 bash scripts/install_macos.sh
#
# 做的事：建独立 venv → 装依赖 → 生成可双击的 .app → 注册到启动台
# 卸载：rm -rf ~/Applications/QTimer.app
#       配置文件在 ~/Library/Preferences/QTimer，如需彻底清除请一并删除
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$HOME/Applications}"
APP="$TARGET/QTimer.app"
PYTHON="${PYTHON:-python3}"

echo "==> QTimer-macOS 安装"
echo "    源码目录: $REPO_DIR"
echo "    安装目标: $APP"
echo

# ---------- 1. 检查 Python ----------
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "✗ 找不到 Python 解释器：$PYTHON" >&2
  echo "  请先安装 Python 3.9+，或用 PYTHON=/path/to/python3 指定" >&2
  exit 1
fi

PY_VER="$("$PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
PY_OK="$("$PYTHON" -c 'import sys; print(1 if sys.version_info >= (3, 9) else 0)')"
if [ "$PY_OK" != "1" ]; then
  echo "✗ 需要 Python 3.9 及以上，当前为 $PY_VER" >&2
  exit 1
fi
echo "==> 使用 Python $PY_VER（$("$PYTHON" -c 'import sys; print(sys.executable)')）"

# ---------- 2. 生成 .app 骨架 ----------
echo "==> 生成应用骨架"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/app"

cp "$REPO_DIR/main.py" \
   "$REPO_DIR/macos_overlay.py" \
   "$REPO_DIR/macos_ppt_detect.py" \
   "$REPO_DIR/default_config.json" \
   "$REPO_DIR/requirements-macos.txt" \
   "$REPO_DIR/PATCHES.md" \
   "$REPO_DIR/README.md" \
   "$REPO_DIR/NOTICE.md" \
   "$REPO_DIR/LICENSE" \
   "$APP/Contents/Resources/app/"

# 图标（可选）：仓库不随附二进制 .icns，仅当用户自备时拷贝
if [ -f "$REPO_DIR/QTimer.icns" ]; then
  cp "$REPO_DIR/QTimer.icns" "$APP/Contents/Resources/QTimer.icns"
fi

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>QTimer</string>
	<key>CFBundleDisplayName</key><string>QTimer</string>
	<key>CFBundleExecutable</key><string>QTimer</string>
	<key>CFBundleIdentifier</key><string>io.github.bbfootfish.qtimer-macos</string>
	<key>CFBundleIconFile</key><string>QTimer</string>
	<key>CFBundleInfoDictionaryVersion</key><string>6.0</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleShortVersionString</key><string>1.4.0-macos</string>
	<key>CFBundleVersion</key><string>1</string>
	<key>LSMinimumSystemVersion</key><string>12.0</string>
	<key>NSHighResolutionCapable</key><true/>
	<key>NSPrincipalClass</key><string>NSApplication</string>
	<key>NSHumanReadableCopyright</key>
	<string>GPL-3.0 | Based on QTimer by QwejayHuang (https://github.com/Qwejay/QTimer)</string>
</dict>
</plist>
PLIST

cat > "$APP/Contents/MacOS/QTimer" <<'LAUNCHER'
#!/bin/bash
# QTimer-macOS 启动器
RES="$(cd "$(dirname "${BASH_SOURCE[0]}")/../Resources" && pwd)"
cd "$RES/app" || exit 1
exec "$RES/venv/bin/python" "$RES/app/main.py" "$@"
LAUNCHER
chmod +x "$APP/Contents/MacOS/QTimer"

# ---------- 3. 建虚拟环境并安装依赖 ----------
echo "==> 创建虚拟环境（约 300 MB，含 PySide6）"
"$PYTHON" -m venv "$APP/Contents/Resources/venv"

echo "==> 安装依赖（首次约需 1-3 分钟）"
"$APP/Contents/Resources/venv/bin/pip" install --upgrade pip --quiet
"$APP/Contents/Resources/venv/bin/pip" install \
  -r "$APP/Contents/Resources/app/requirements-macos.txt" --quiet

# ---------- 4. 验证依赖可用性 ----------
echo "==> 校验依赖"
"$APP/Contents/Resources/venv/bin/python" - <<'CHECK'
import sys
ok = True
try:
    from PySide6.QtWidgets import QApplication
    print("  ✓ PySide6 可用")
except Exception as e:
    ok = False; print(f"  ✗ PySide6 不可用: {e}")
try:
    import AppKit  # noqa
    print("  ✓ pyobjc-framework-Cocoa 可用（补丁 3 全屏穿透）")
except Exception as e:
    print(f"  ! pyobjc-framework-Cocoa 不可用: {e}（补丁 3 将失效）")
try:
    import Quartz  # noqa
    print("  ✓ pyobjc-framework-Quartz 可用（补丁 4 PPT 检测）")
except Exception as e:
    print(f"  ! pyobjc-framework-Quartz 不可用: {e}（补丁 4 将失效）")
sys.exit(0 if ok else 1)
CHECK

# ---------- 5. 注册到 LaunchServices ----------
LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREG" ] && "$LSREG" -f "$APP" >/dev/null 2>&1 || true

echo
echo "==> 安装完成"
echo "    应用位置: $APP"
echo "    启动方式: 打开启动台搜索 QTimer，或双击 $APP"
echo "    配置文件: ~/Library/Preferences/QTimer/config.json"
echo
echo "    提示：首次打开若被 Gatekeeper 拦截，右键 → 打开 即可放行。"
echo "          建议拖一个到 Dock，放映前一点即开。"
