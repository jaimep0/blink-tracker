#!/bin/bash
# Build BlinkNotify.app (AppleScript applet) for macOS notification banners with the eye icon.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RES="$ROOT/Blink Tracker.app/Contents/Resources"
SCRIPT="$RES/BlinkNotify.applescript"
OUT="$RES/BlinkNotify.app"
ICON="$RES/AppIcon.icns"

if [ ! -f "$SCRIPT" ]; then
  echo "Missing $SCRIPT" >&2
  exit 1
fi
if [ ! -f "$ICON" ]; then
  echo "Missing $ICON" >&2
  exit 1
fi
if ! command -v osacompile >/dev/null 2>&1; then
  echo "osacompile not found (macOS only)." >&2
  exit 1
fi

rm -rf "$OUT"
osacompile -o "$OUT" "$SCRIPT"
cp "$ICON" "$OUT/Contents/Resources/applet.icns"

PLIST="$OUT/Contents/Info.plist"
if [ -f "$PLIST" ] && command -v /usr/libexec/PlistBuddy >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName Blink Tracker' "$PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c 'Set :CFBundleName Blink Tracker' "$PLIST" 2>/dev/null || true
fi

echo "Built $OUT"
