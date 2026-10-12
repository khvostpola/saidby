# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: CC0-1.0

from pathlib import Path

CELL = 6
W, H = 52, 36
INK, BODY, SHADE, CREAM = "#1d2b53", "#c2c3c7", "#83769c", "#fff1e8"
RED, BLUE, YELLOW, REEL, TAPE = "#ff004d", "#29adff", "#ffec27", "#5f574f", "#7e2553"

FONT = {
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
}


def build() -> str:
    cells: dict[tuple[int, int], str] = {}

    def fill(x0: int, y0: int, x1: int, y1: int, color: str) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                cells[(x, y)] = color

    fill(0, 0, W - 1, H - 1, INK)
    for corner in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        cells.pop(corner, None)
    fill(1, 1, W - 2, H - 2, BODY)
    fill(1, H - 4, W - 2, H - 2, SHADE)
    fill(4, 3, W - 5, 17, CREAM)
    fill(4, 3, W - 5, 4, RED)
    fill(4, 5, W - 5, 5, BLUE)
    fill(4, 6, W - 5, 6, YELLOW)
    text = "SAIDBY"
    width = sum(len(FONT[c][0]) for c in text) + len(text) - 1
    x = 4 + (W - 8 - width) // 2
    for ch in text:
        glyph = FONT[ch]
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "#":
                    cells[(x + gx, 9 + gy)] = INK
        x += len(glyph[0]) + 1
    fill(12, 20, W - 13, 29, INK)
    fill(13, 21, W - 14, 28, TAPE)
    for cx in (19, W - 20):
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                if dx * dx + dy * dy <= 11:
                    cells[(cx + dx, 24 + dy)] = REEL
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            cells[(cx + dx, 24 + dy)] = CREAM
        for dx, dy in ((0, -3), (0, 3), (-3, 0), (3, 0)):
            cells[(cx + dx, 24 + dy)] = CREAM
    fill(23, 26, W - 24, 28, INK)
    for sx, sy in ((2, 2), (W - 3, 2), (2, H - 3), (W - 3, H - 3)):
        cells[(sx, sy)] = INK
    for hx in (8, W - 9):
        fill(hx, H - 3, hx + 1, H - 3, INK)
    fill(18, H - 4, W - 19, H - 4, INK)
    rects = "".join(
        f'<rect x="{x * CELL}" y="{y * CELL}" width="{CELL}" height="{CELL}" fill="{c}"/>'
        for (x, y), c in sorted(cells.items(), key=lambda kv: (kv[1], kv[0]))
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W * CELL} {H * CELL}" '
        f'width="{W * CELL}" height="{H * CELL}" shape-rendering="crispEdges" role="img" '
        f'aria-label="A cassette tape labelled saidby"><title>saidby</title>{rects}</svg>\n'
    )


if __name__ == "__main__":
    Path("docs/img/logo.svg").write_text(build(), encoding="utf-8")
    print("wrote docs/img/logo.svg")
