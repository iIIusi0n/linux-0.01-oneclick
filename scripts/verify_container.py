#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time
from pathlib import Path

try:
    import pyte
except ImportError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "pyte is required for verification; install it with `python3 -m pip install -r requirements-dev.txt`."
    ) from exc

PROMPT_RE = re.compile(r"^\s*#\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Strictly verify the Linux 0.01 container boots to a shell.")
    parser.add_argument("--runtime", choices=["docker", "podman"], help="Container runtime to use. Defaults to autodetect.")
    parser.add_argument("--image", default="linux-0.01:latest", help="Image reference to run.")
    parser.add_argument("--output-dir", default="artifacts/verify", help="Directory for logs and proof artifacts.")
    parser.add_argument("--boot-timeout", type=int, default=60, help="Seconds to wait for the initial shell prompt.")
    parser.add_argument("--command-timeout", type=int, default=20, help="Seconds to wait for guest command output.")
    parser.add_argument("--term", default="xterm", help="TERM value passed into the container.")
    return parser.parse_args()


def detect_runtime(requested: str | None) -> str:
    if requested:
        if not shutil.which(requested):
            raise SystemExit(f"Requested runtime `{requested}` is not installed.")
        return requested
    for candidate in ("docker", "podman"):
        if shutil.which(candidate):
            return candidate
    raise SystemExit("Neither docker nor podman is installed.")


def set_winsize(fd: int, rows: int = 40, cols: int = 120) -> None:
    winsz = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsz)


def screen_text(screen: pyte.Screen) -> str:
    return "\n".join(screen.display)


def has_shell_prompt(screen: pyte.Screen) -> bool:
    return any(PROMPT_RE.match(line or "") for line in screen.display)


def wait_for(predicate, *, deadline: float, reader) -> bool:
    while time.time() < deadline:
        reader(timeout=0.5)
        if predicate():
            return True
    return False


def render_png(text: str, destination: Path) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    lines = text.rstrip("\n").splitlines() or [""]
    font = ImageFont.load_default()
    line_height = max(font.getbbox("Ag")[3], 11) + 4
    width = max(font.getbbox(line)[2] for line in lines) + 40
    height = line_height * len(lines) + 30

    image = Image.new("RGB", (width, height), (10, 12, 16))
    draw = ImageDraw.Draw(image)
    y = 15
    for line in lines:
        draw.text((20, y), line, font=font, fill=(125, 255, 125))
        y += line_height
    image.save(destination)
    return True


def main() -> int:
    args = parse_args()
    runtime = detect_runtime(args.runtime)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_log_path = output_dir / "raw.log"
    transcript_path = output_dir / "transcript.txt"
    screen_path = output_dir / "final-screen.txt"
    png_path = output_dir / "final-screen.png"
    summary_path = output_dir / "summary.txt"

    run_cmd = [runtime, "run", "--rm", "-it", "-e", f"TERM={args.term}"]
    if runtime == "podman":
        run_cmd.append("--pull=never")
    run_cmd.append(args.image)

    master_fd, slave_fd = pty.openpty()
    set_winsize(slave_fd)

    env = os.environ.copy()
    env["TERM"] = args.term

    process = subprocess.Popen(
        run_cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    screen = pyte.Screen(120, 40)
    stream = pyte.Stream(screen)
    raw_chunks: list[bytes] = []
    transcript: list[str] = []

    def reader(timeout: float = 0.2) -> bytes:
        ready, _, _ = select.select([master_fd], [], [], timeout)
        if master_fd not in ready:
            return b""
        chunk = os.read(master_fd, 65536)
        if not chunk:
            return b""
        raw_chunks.append(chunk)
        text = chunk.decode("utf-8", "ignore")
        transcript.append(text)
        stream.feed(text)
        return chunk

    try:
        boot_ok = wait_for(lambda: has_shell_prompt(screen), deadline=time.time() + args.boot_timeout, reader=reader)
        if not boot_ok:
            raise RuntimeError("guest never reached a shell prompt")

        os.write(master_fd, b"/bin/ls /bin/sh\r")
        command_ok = wait_for(lambda: "/bin/sh" in screen_text(screen), deadline=time.time() + args.command_timeout, reader=reader)
        if not command_ok:
            raise RuntimeError("guest did not echo `/bin/sh` after the verification command")

        prompt_back = wait_for(lambda: has_shell_prompt(screen), deadline=time.time() + 5, reader=reader)
        if not prompt_back:
            raise RuntimeError("guest command completed, but the shell prompt did not return")

        for _ in range(5):
            reader(timeout=0.1)

        final_text = screen_text(screen) + "\n"
        raw_log_path.write_bytes(b"".join(raw_chunks))
        transcript_path.write_text("".join(transcript), encoding="utf-8", errors="ignore")
        screen_path.write_text(final_text, encoding="utf-8")
        rendered = render_png(final_text, png_path)
        summary_path.write_text(
            "\n".join(
                [
                    f"runtime={runtime}",
                    f"image={args.image}",
                    f"boot_prompt_verified={boot_ok}",
                    f"guest_command_verified={command_ok}",
                    f"prompt_return_verified={prompt_back}",
                    f"png_rendered={rendered}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print(summary_path)
        print(screen_path)
        if rendered:
            print(png_path)
        print("FINAL SCREEN:")
        print(final_text, end="")
        return 0
    finally:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=3)
        except Exception:
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
