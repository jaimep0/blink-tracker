#!/bin/bash
# Ensure BlinkNotify.app exists beside BlinkNotify.applescript (macOS only).
set -euo pipefail

RES="${1:?Resources directory required}"
SCRIPT="$RES/BlinkNotify.applescript"
OUT="$RES/BlinkNotify.app"
ICON="$RES/AppIcon.icns"
HELPER="$OUT/Contents/MacOS/applet"

if [ -x "$HELPER" ]; then
  exit 0
fi
if [ ! -f "$SCRIPT" ] || [ ! -f "$ICON" ]; then
  exit 0
fi
if ! command -v osacompile >/dev/null 2>&1; then
  exit 0
fi

rm -rf "$OUT"
osacompile -o "$OUT" "$SCRIPT"
cp "$ICON" "$OUT/Contents/Resources/applet.icns"

PLIST="$OUT/Contents/Info.plist"
if [ -f "$PLIST" ] && command -v /usr/libexec/PlistBuddy >/dev/null 2>&1; then
  /usr/libexec/PlistBuddy -c 'Set :CFBundleDisplayName Blink Tracker' "$PLIST" 2>/dev/null || true
  /usr/libexec/PlistBuddy -c 'Set :CFBundleName Blink Tracker' "$PLIST" 2>/dev/null || true
fi
