#!/usr/bin/env bash
set -euo pipefail

if [[ ! -t 0 || ! -t 1 ]]; then
  echo "error: linux-0.01 requires an interactive TTY; use: docker run -it --rm linux-0.01" >&2
  exit 1
fi

export TERM="${TERM:-xterm}"

exec qemu-system-i386 \
  -display curses \
  -name linux-0.01 \
  -no-reboot \
  -snapshot \
  -boot a \
  -monitor none \
  -parallel none \
  -serial none \
  -net none \
  -drive format=raw,file=/opt/linux-0.01/Image.1440,if=floppy,index=0 \
  -drive format=raw,file=/opt/linux-0.01/hd_oldlinux.img,if=ide,index=1 \
  -m 8 \
  -machine pc-i440fx-2.5
