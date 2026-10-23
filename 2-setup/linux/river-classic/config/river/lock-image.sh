#!/bin/sh
# Build the swaylock background: the session wallpaper, blurred and darkened,
# with the current time and date drawn on it.
#
# swaylock 1.8 dropped its built-in clock (1.7 had --clock/--timestr), and the
# lock surface is opaque, so a live overlay is not possible under
# ext-session-lock-v1.  Generating one image at lock time is the simple
# equivalent: the clock shows the time the session was locked, which is also
# what tells you "how long have I been away?" at a glance.
#
# Usage: lock-image.sh WALLPAPER OUTPUT
# Env:   RIVER_LOCK_SIZE=1920x1200   override the target size
#        RIVER_LOCK_CLOCK_FORMAT=%H:%M
#        RIVER_LOCK_DATE_FORMAT=%A, %d %B
#        RIVER_LOCK_HINT="Enter password to unlock" (empty disables)
set -u

wall="${1:-}"
out="${2:-}"
[ -n "$wall" ] && [ -f "$wall" ] || exit 1
[ -n "$out" ] || exit 1

# Target size: the first connected DRM output's preferred mode, so the image
# matches the screen aspect (fill-scaling then has nothing to crop).
size="${RIVER_LOCK_SIZE:-}"
if [ -z "$size" ]; then
    for m in /sys/class/drm/card*-*/modes; do
        [ -r "$m" ] || continue
        d="${m%/modes}"
        [ "$(cat "$d/status" 2>/dev/null)" = "connected" ] || continue
        read -r first <"$m" 2>/dev/null || true
        if [ -n "${first:-}" ]; then
            size="$first"
            break
        fi
    done
fi
[ -n "$size" ] || size=1920x1200

LOCK_WALL="$wall" LOCK_OUT="$out" LOCK_SIZE="$size" \
LOCK_CLOCK="${RIVER_LOCK_CLOCK_FORMAT:-%H:%M}" \
LOCK_DATE="${RIVER_LOCK_DATE_FORMAT:-%A, %d %B}" \
LOCK_HINT="${RIVER_LOCK_HINT-Enter password to unlock}" \
python3 - <<'PY'
import os
import sys
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
except ImportError:
    sys.exit(1)

wall = os.environ["LOCK_WALL"]
out = os.environ["LOCK_OUT"]
try:
    width, height = (int(v) for v in os.environ["LOCK_SIZE"].lower().split("x", 1))
except (KeyError, ValueError):
    sys.exit(1)
if width < 320 or height < 240:
    sys.exit(1)

# Cover-fit, then soften: a blurred/darkened wallpaper keeps the lock surface
# readable and hides the (possibly private) desktop behind the locker's own
# solid fill.
img = Image.open(wall).convert("RGB")
img = ImageOps.fit(img, (width, height), method=Image.Resampling.LANCZOS)
img = img.filter(ImageFilter.GaussianBlur(radius=max(4, height // 160)))
shade = Image.new("RGBA", img.size, (0, 0, 0, 135))
img = Image.alpha_composite(img.convert("RGBA"), shade)

draw = ImageDraw.Draw(img)

def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()

bold = font("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(height * 0.165))
regular = font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(height * 0.045))
small = font("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(height * 0.026))

time_text = datetime.now().strftime(os.environ.get("LOCK_CLOCK", "%H:%M"))
date_text = datetime.now().strftime(os.environ.get("LOCK_DATE", "%A, %d %B"))

def centered(text, f, y, fill=(255, 255, 255, 255), shadow=(0, 0, 0, 170)):
    box = draw.textbbox((0, 0), text, font=f)
    x = (width - (box[2] - box[0])) // 2 - box[0]
    # 2 px offset shadow for legibility on any wallpaper
    draw.text((x + 2, y + 2), text, font=f, fill=shadow)
    draw.text((x, y), text, font=f, fill=fill)

# Clock slightly above centre, date underneath, hint near the bottom.
clock_h = int(height * 0.165)
centered(time_text, bold, int(height * 0.34))
centered(date_text, regular, int(height * 0.34) + clock_h + int(height * 0.04),
         fill=(235, 240, 245, 255))

hint = os.environ.get("LOCK_HINT", "")
if hint:
    box = draw.textbbox((0, 0), hint, font=small)
    draw.text(((width - (box[2] - box[0])) // 2 - box[0], int(height * 0.90)),
              hint, font=small, fill=(220, 225, 230, 170))

img.convert("RGB").save(out, "PNG")
PY
