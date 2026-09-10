#!/usr/bin/env sh

COUNT="$(yabai -m query --windows --space | jq 'map(select(."is-floating" == false)) | length')"

if [ "${COUNT:-0}" -le 1 ]; then
  pkill -x borders >/dev/null 2>&1 || true
else
  if ! pgrep -x borders >/dev/null 2>&1; then
    borders active_color=0xffe35d6a inactive_color=0xff3a3f4b width=8.0 hidpi=on &
  fi
fi
