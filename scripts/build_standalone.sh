#!/bin/bash
#
# QTimer-macOS 独立打包脚本（PyInstaller）
#
#   用法：bash scripts/build_standalone.sh [输出目录]
#
# 与 install_macos.sh 的区别：
#   install_macos.sh   —— 依赖系统 Python + 本地 venv，产物体积小，装得快
#   build_standalone.sh —— 把 Python 运行时与 PySide6 一并冻结进 .app，
#                          产物约 32 MB，**零外部依赖**，可直接拷给别人用
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${1:-$REPO_DIR/dist}"
PYTHON="${PYTHON:-python3}"
BUILD_DIR="$REPO_DIR/build/standalone"

echo "==> QTimer-macOS 独立打包"
echo "    源码目录: $REPO_DIR"
echo "    输出目录: $OUT_DIR"
echo

command -v "$PYTHON" >/dev/null 2>&1 || { echo "✗ 找不到 Python：$PYTHON" >&2; exit 1; }

# ---------- 图标（可选） ----------
# 仓库不随附二进制 .icns。若有自带的 QTimer.icns 放在仓库根目录，则打包进去；
# 否则使用 macOS 默认应用图标（不影响功能）。
ICON_FILE=""
if [ -f "$REPO_DIR/QTimer.icns" ]; then
  ICON_FILE="$REPO_DIR/QTimer.icns"
  echo "==> 检测到 QTimer.icns，将打包为应用图标"
else
  echo "==> 未找到 QTimer.icns，使用系统默认图标（如需自定义，放一个 QTimer.icns 到仓库根目录）"
fi

# ---------- 1. 独立构建环境（避免污染用户环境） ----------
echo "==> 准备构建环境"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR/src"
"$PYTHON" -m venv "$BUILD_DIR/venv"
"$BUILD_DIR/venv/bin/pip" install --upgrade pip --quiet
"$BUILD_DIR/venv/bin/pip" install --quiet \
  pyinstaller -r "$REPO_DIR/requirements-macos.txt"

# ---------- 2. 拷贝待打包源码 ----------
cp "$REPO_DIR/main.py" \
   "$REPO_DIR/macos_overlay.py" \
   "$REPO_DIR/macos_ppt_detect.py" \
   "$REPO_DIR/default_config.json" \
   "$BUILD_DIR/src/"
[ -n "$ICON_FILE" ] && cp "$ICON_FILE" "$BUILD_DIR/src/"

# ---------- 3. 生成 PyInstaller spec ----------
ICON_ARG=""            # EXE/BUNDLE 的 icon= 参数（有图标时填入）
DATAS_LINE="('default_config.json', '.')"
if [ -n "$ICON_FILE" ]; then
  ICON_ARG="    icon='QTimer.icns',"
  DATAS_LINE="('default_config.json', '.'), ('QTimer.icns', '.')"
fi

cat > "$BUILD_DIR/src/QTimer.spec" <<SPEC
# -*- mode: python ; coding: utf-8 -*-
# QTimer-macOS 打包配置
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[$DATAS_LINE],
    hiddenimports=['objc', 'AppKit', 'Quartz'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='QTimer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 不弹终端窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
$ICON_ARG
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name='QTimer',
)

app = BUNDLE(
    coll,
    name='QTimer.app',
$ICON_ARG
    bundle_identifier='io.github.bbfootfish.qtimer-macos',
    info_plist={
        'CFBundleName': 'QTimer',
        'CFBundleDisplayName': 'QTimer',
        'CFBundleShortVersionString': '1.4.0-macos',
        'CFBundleVersion': '1',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSPrincipalClass': 'NSApplication',
        'NSHumanReadableCopyright':
            'GPL-3.0 | Based on QTimer by QwejayHuang (https://github.com/Qwejay/QTimer)',
    },
)
SPEC

# ---------- 4. 打包 ----------
echo "==> 执行 PyInstaller 打包"
cd "$BUILD_DIR/src"
"$BUILD_DIR/venv/bin/pyinstaller" --noconfirm --clean QTimer.spec

# ---------- 5. 输出 ----------
mkdir -p "$OUT_DIR"
rm -rf "$OUT_DIR/QTimer.app"
mv "$BUILD_DIR/src/dist/QTimer.app" "$OUT_DIR/QTimer.app"

# 重新自签（新增文件会使原签名失效）
codesign --force --deep --sign - "$OUT_DIR/QTimer.app" >/dev/null 2>&1 || \
  echo "  ! 自签失败（不影响本机运行）"

LSREG="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREG" ] && "$LSREG" -f "$OUT_DIR/QTimer.app" >/dev/null 2>&1 || true

SIZE="$(du -sh "$OUT_DIR/QTimer.app" | cut -f1)"
echo
echo "==> 打包完成"
echo "    产物: $OUT_DIR/QTimer.app（$SIZE）"
echo "    零外部依赖，可直接拷给他人使用"
