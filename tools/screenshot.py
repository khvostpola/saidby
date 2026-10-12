# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import fcntl
import os
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
from dataclasses import dataclass, replace
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures" / "conversations" / "test" / "test-conv-01.flac"
OUTPUT = ROOT / "docs" / "img" / "interactive.png"
COLUMNS, ROWS = 100, 60
PROMPT = "▸"
ANSWERS = ["es", "", "", "Ana Gómez", "Ben Ruiz", "", ""]
TITLE = "saidby process call.m4a"
CSI = re.compile(r"\x1b\[([0-?]*)([ -/]*)([@-~])")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
PALETTE = {
    30: "#45475a",
    31: "#f38ba8",
    32: "#a6e3a1",
    33: "#f9e2af",
    34: "#89b4fa",
    35: "#f5c2e7",
    36: "#94e2d5",
    37: "#bac2de",
}
PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body {{ margin: 0; background: transparent; }}
body {{ padding: 28px; width: max-content; }}
.window {{ background: #1e1e2e; border-radius: 12px; overflow: hidden; width: max-content;
  box-shadow: 0 18px 48px rgba(0, 0, 0, .45); }}
.bar {{ height: 40px; display: flex; align-items: center; padding: 0 16px; background: #181825;
  position: relative; }}
.dot {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
.title {{ position: absolute; left: 0; right: 0; text-align: center; color: #6c7086;
  font: 13px "Noto Sans Mono", "DM Mono", "Liberation Mono", monospace; }}
pre {{ margin: 0; padding: 18px 22px 22px; color: #cdd6f4; white-space: pre;
  font: 14px/1.36 "Noto Sans Mono", "DM Mono", "Liberation Mono", monospace; }}
.b {{ font-weight: 700; }}
.d {{ opacity: .62; }}
</style></head><body><div class="window"><div class="bar">
<span class="dot" style="background:#ff5f57"></span>
<span class="dot" style="background:#febc2e"></span>
<span class="dot" style="background:#28c840"></span>
<div class="title">{title}</div></div>
<pre>{body}</pre></div>
<script>
const r = document.documentElement;
r.dataset.size = r.scrollWidth + "x" + r.scrollHeight;
</script></body></html>
"""


@dataclass(frozen=True)
class Style:
    fg: str | None = None
    bg: str | None = None
    bold: bool = False
    dim: bool = False


Cell = tuple[str, Style]


class Screen:
    def __init__(self) -> None:
        self.rows: list[list[Cell]] = [[]]
        self.row = 0
        self.col = 0
        self.style = Style()

    def put(self, char: str) -> None:
        row = self.rows[self.row]
        while len(row) < self.col:
            row.append((" ", Style()))
        if self.col < len(row):
            row[self.col] = (char, self.style)
        else:
            row.append((char, self.style))
        self.col += 1

    def newline(self) -> None:
        self.row += 1
        while len(self.rows) <= self.row:
            self.rows.append([])

    def erase_to_end(self) -> None:
        del self.rows[self.row][self.col :]

    def sgr(self, params: str) -> None:
        codes = [int(p) if p else 0 for p in params.split(";")] if params else [0]
        i = 0
        while i < len(codes):
            code = codes[i]
            if code == 0:
                self.style = Style()
            elif code in (1, 2):
                self.style = replace(
                    self.style, bold=code == 1 or self.style.bold, dim=code == 2 or self.style.dim
                )
            elif code == 22:
                self.style = replace(self.style, bold=False, dim=False)
            elif code in PALETTE or code == 39:
                self.style = replace(self.style, fg=PALETTE.get(code))
            elif code - 10 in PALETTE or code == 49:
                self.style = replace(self.style, bg=PALETTE.get(code - 10))
            elif code in (38, 48) and codes[i + 1 : i + 2] == [2]:
                r, g, b = codes[i + 2 : i + 5]
                color = f"#{r:02x}{g:02x}{b:02x}"
                if code == 38:
                    self.style = replace(self.style, fg=color)
                else:
                    self.style = replace(self.style, bg=color)
                i += 4
            elif code in (38, 48):
                i += 2
            i += 1

    def feed(self, text: str) -> None:
        i = 0
        while i < len(text):
            char = text[i]
            if char == "\x1b":
                match = CSI.match(text, i)
                if match:
                    final, params = match.group(3), match.group(1)
                    if final == "m":
                        self.sgr(params)
                    elif final == "K" and params in ("", "0"):
                        self.erase_to_end()
                    i = match.end()
                else:
                    i += 2
                continue
            if char == "\r":
                self.col = 0
            elif char == "\n":
                self.newline()
            elif char == "\b":
                self.col = max(0, self.col - 1)
            elif char >= " ":
                self.put(char)
            i += 1

    def html(self) -> str:
        lines = []
        for row in self.rows:
            spans: list[tuple[str, Style]] = []
            for char, style in row:
                text = escape(char)
                if spans and spans[-1][1] == style:
                    spans[-1] = (spans[-1][0] + text, style)
                else:
                    spans.append((text, style))
            lines.append("".join(_span(text, style) for text, style in spans).rstrip())
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)


def _span(text: str, style: Style) -> str:
    classes = [name for name, on in (("b", style.bold), ("d", style.dim)) if on]
    css = [f"color:{style.fg}" if style.fg else "", f"background:{style.bg}" if style.bg else ""]
    attrs = (f' class="{" ".join(classes)}"' if classes else "") + (
        f' style="{";".join(c for c in css if c)}"' if any(css) else ""
    )
    return f"<span{attrs}>{text}</span>" if attrs else text


def record(command: list[str], answers: list[str], cwd: Path, timeout_s: float) -> bytes:
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvp(command[0], command)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", ROWS, COLUMNS, 0, 0))
    chunks: list[bytes] = []
    sent = 0
    deadline = time.monotonic() + timeout_s
    finished = False
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.3)
        if ready:
            try:
                data = os.read(fd, 65536)
            except OSError:
                break
            if not data:
                break
            chunks.append(data)
        if finished and not ready:
            break
        plain = ANSI.sub("", b"".join(chunks).decode("utf-8", "replace")).rstrip()
        if sent < len(answers) and plain.endswith(PROMPT) and plain.count(PROMPT) > sent:
            time.sleep(0.3)
            os.write(fd, (answers[sent] + "\n").encode())
            sent += 1
        if not finished and os.waitpid(pid, os.WNOHANG)[0]:
            finished = True
    else:
        os.kill(pid, 15)
        raise SystemExit("saidby did not finish in time")
    if sent < len(answers):
        raise SystemExit(f"saidby asked {sent} questions, expected {len(answers)}")
    return b"".join(chunks)


def chrome_command(chrome: str, flatpak: bool, folder: Path) -> list[str]:
    if flatpak:
        return ["flatpak", "run", f"--filesystem={folder}", "com.google.Chrome"]
    return [chrome]


def measure(chrome: list[str], page: Path) -> tuple[int, int]:
    dom = subprocess.run(
        [
            *chrome,
            "--headless=new",
            "--disable-gpu",
            "--window-size=200,200",
            "--dump-dom",
            str(page),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    match = re.search(r'data-size="(\d+)x(\d+)"', dom)
    if match is None:
        raise SystemExit("could not measure the page; is Chrome running scripts?")
    return int(match.group(1)), int(match.group(2))


def screenshot(chrome: list[str], page: Path, out: Path) -> None:
    width, height = measure(chrome, page)
    subprocess.run(
        [
            *chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            "--default-background-color=00000000",
            f"--window-size={width},{height}",
            f"--screenshot={out}",
            str(page),
        ],
        capture_output=True,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a guided `saidby process` on a public fixture in a real terminal and render "
            "what it printed as the README screenshot. Needs the default models and ffmpeg; "
            "Chrome draws the PNG."
        )
    )
    parser.add_argument("--out", type=Path, default=OUTPUT, help=f"PNG to write (default {OUTPUT})")
    parser.add_argument("--chrome", default="google-chrome", help="Chrome or Chromium command")
    parser.add_argument("--flatpak", action="store_true", help="Run the Flatpak build of Chrome")
    parser.add_argument("--keep-html", action="store_true", help="Leave the HTML next to the PNG")
    args = parser.parse_args(argv)
    saidby = Path(sys.executable).with_name("saidby")
    work = Path(tempfile.gettempdir()) / "saidby-screenshot"
    shutil.rmtree(work, ignore_errors=True)
    (work / "config").mkdir(parents=True)
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-v",
                "error",
                "-y",
                "-i",
                str(FIXTURE),
                "-c:a",
                "aac",
                "call.m4a",
            ],
            cwd=work,
            check=True,
        )
        os.environ.update(
            TERM="xterm-256color",
            COLORTERM="truecolor",
            COLUMNS=str(COLUMNS),
            LINES=str(ROWS),
            SAIDBY_UI_LANG="en",
            XDG_CONFIG_HOME=str(work / "config"),
        )
        raw = record([str(saidby), "process", "call.m4a"], ANSWERS, work, timeout_s=900)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    screen = Screen()
    screen.feed(raw.decode("utf-8", "replace"))
    page = args.out.with_suffix(".html")
    page.write_text(PAGE.format(title=TITLE, body=screen.html()), encoding="utf-8")
    try:
        screenshot(chrome_command(args.chrome, args.flatpak, args.out.parent), page, args.out)
    finally:
        if not args.keep_html:
            page.unlink(missing_ok=True)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
