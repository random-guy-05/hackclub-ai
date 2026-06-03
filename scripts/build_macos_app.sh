#!/usr/bin/env bash
# Build a self-contained HackClub AI.app and install to ~/Applications
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="HackClub AI"
BUNDLE_ID="com.hackclub.ai"
BUILD_DIR="$ROOT/build"
APP_DIR="$BUILD_DIR/${APP_NAME}.app"
INSTALL_DIR="${HOME}/Applications/${APP_NAME}.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
LIB="$RESOURCES/lib"
VENV="$RESOURCES/venv"
ICON_SRC="$ROOT/assets/AppIcon-1024.png"
ICON_ICNS="$ROOT/assets/AppIcon.icns"

echo "==> Building ${APP_NAME}..."

# Build .icns if missing
if [[ ! -f "$ICON_ICNS" ]]; then
  echo "==> Generating app icon..."
  if [[ ! -f "$ICON_SRC" ]]; then
    echo "Missing $ICON_SRC — add a 1024x1024 PNG first." >&2
    exit 1
  fi
  ICONSET="$ROOT/assets/icon.iconset"
  rm -rf "$ICONSET"
  mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
    sips -z $((size * 2)) $((size * 2)) "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
  done
  iconutil -c icns "$ICONSET" -o "$ICON_ICNS"
fi

echo "==> Creating Python environment inside app bundle..."
rm -rf "$APP_DIR"
mkdir -p "$MACOS" "$RESOURCES" "$LIB"

python3 -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$ROOT/requirements.txt"

echo "==> Copying application code..."
cp "$ROOT/hackclub_ai.py" "$ROOT/hackclub_app.py" "$LIB/"

echo "==> Verifying app imports..."
PYTHONPATH="$LIB" "$VENV/bin/python" -c "import hackclub_app; print('import ok:', hackclub_app.APP_NAME)"

cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleExecutable</key>
  <string>hackclub-ai</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>${BUNDLE_ID}</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>LSApplicationCategoryType</key>
  <string>public.app-category.productivity</string>
</dict>
</plist>
PLIST

cp "$ICON_ICNS" "$RESOURCES/AppIcon.icns"

cat > "$MACOS/hackclub-ai" <<'LAUNCHER'
#!/bin/zsh

# MacOS -> Contents -> Resources
CONTENTS="${0:A:h:h}"
RESOURCES="$CONTENTS/Resources"
LIB="$RESOURCES/lib"
VENV="$RESOURCES/venv"
PYTHON="$VENV/bin/python"

_load_key_from_file() {
  local f="$1"
  [[ -f "$f" ]] || return 1
  local line
  line=$(grep -E '^[[:space:]]*(export[[:space:]]+)?HACKCLUB_API_KEY=' "$f" 2>/dev/null | tail -1) || return 1
  line=${line#export }
  line=${line#HACKCLUB_API_KEY=}
  line=${line#"${line%%[![:space:]]*}"}
  line=${line%"${line##*[![:space:]]}"}
  line=${line#\"}; line=${line%\"}
  line=${line#\'}; line=${line%\'}
  [[ -n "$line" ]] || return 1
  export HACKCLUB_API_KEY="$line"
}

if [[ -z "${HACKCLUB_API_KEY:-}" && -x "$PYTHON" ]]; then
  HACKCLUB_API_KEY="$("$PYTHON" - <<'PY' 2>/dev/null || true
import json, os
p = os.path.expanduser("~/.hackclub-ai/config.json")
try:
    d = json.load(open(p))
    print((d.get("hackclub_api_key") or d.get("api_key") or "").strip())
except Exception:
    pass
PY
)"
  [[ -n "$HACKCLUB_API_KEY" ]] && export HACKCLUB_API_KEY
fi
if [[ -z "${HACKCLUB_API_KEY:-}" ]]; then
  _load_key_from_file "$HOME/.zshrc" || _load_key_from_file "$HOME/.zprofile" || _load_key_from_file "$HOME/.bashrc" || true
fi

export PYTHONPATH="$LIB${PYTHONPATH:+:$PYTHONPATH}"
cd "$LIB"
LOG="$HOME/Library/Logs/HackClub-AI.log"
exec "$PYTHON" -u "$LIB/hackclub_app.py" "$@" 2>> "$LOG"
LAUNCHER

chmod +x "$MACOS/hackclub-ai"

echo "==> Installing to ${INSTALL_DIR}..."
rm -rf "$INSTALL_DIR"
mkdir -p "$(dirname "$INSTALL_DIR")"
ditto "$APP_DIR" "$INSTALL_DIR"

# Refresh Launch Services so Dock/Finder pick up the icon
touch "$INSTALL_DIR"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$INSTALL_DIR" 2>/dev/null || true

echo ""
echo "Installed: ${INSTALL_DIR}"
echo "Launch:    open \"${INSTALL_DIR}\""
echo ""
echo "First launch will prompt for your Hack Club API key (saved in ~/.hackclub-ai/config.json)."

echo "==> Packaging DMG..."
DMG_STAGING="$BUILD_DIR/dmg-staging"
DMG_PATH="$ROOT/dist/HackClub-AI.dmg"
rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING" "$ROOT/dist"
ditto "$APP_DIR" "$DMG_STAGING/${APP_NAME}.app"
ln -sf /Applications "$DMG_STAGING/Applications"
rm -f "$DMG_PATH"
hdiutil create -volname "$APP_NAME" -srcfolder "$DMG_STAGING" -ov -format UDZO "$DMG_PATH"
rm -rf "$DMG_STAGING"

echo ""
echo "DMG:       ${DMG_PATH}"
