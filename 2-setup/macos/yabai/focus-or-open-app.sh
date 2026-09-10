#!/usr/bin/env sh

APP_NAME="$1"

if [ -z "$APP_NAME" ]; then
  exit 1
fi

WIN_JSON="$(yabai -m query --windows | jq -c --arg app "$APP_NAME" 'map(select(.app == $app and ."is-minimized" == false)) | .[0]')"

if [ "$WIN_JSON" = "null" ] || [ -z "$WIN_JSON" ]; then
  open -a "$APP_NAME"
  exit 0
fi

SPACE_INDEX="$(printf '%s' "$WIN_JSON" | jq -r '.space')"
WIN_ID="$(printf '%s' "$WIN_JSON" | jq -r '.id')"

yabai -m space --focus "$SPACE_INDEX"
yabai -m window --focus "$WIN_ID"
