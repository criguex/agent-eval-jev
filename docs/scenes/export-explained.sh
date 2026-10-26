#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
FPS=12
DUR=$(grep -m1 -o '"duration": [0-9.]*' explained.html | awk '{print $2}')
N=$(awk -v d="$DUR" -v f="$FPS" 'BEGIN{printf "%d", d*f}')
for LANG_CODE in en es; do
  SUFFIX=""; [ "$LANG_CODE" = es ] && SUFFIX=".es"
  rm -rf frames && mkdir frames
  for i in $(seq 0 $((N - 1))); do
    t=$(awk -v i="$i" -v f="$FPS" 'BEGIN{printf "%.3f", i/f}')
    "$CHROME" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=960,540 \
      --virtual-time-budget=3000 --screenshot="frames/f$(printf %03d "$i").png" \
      "file://$PWD/explained.html?lang=$LANG_CODE&t=$t" >/dev/null 2>&1
  done
  ffmpeg -y -loglevel error -framerate "$FPS" -i frames/f%03d.png \
    -vf "split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5" \
    -loop 0 "../assets/explained$SUFFIX.gif"
  ffmpeg -y -loglevel error -framerate "$FPS" -i frames/f%03d.png -pix_fmt yuv420p -vf scale=960:-2 \
    -movflags +faststart "../assets/explained$SUFFIX.mp4"
done
rm -rf frames
ls -l ../assets/explained*
