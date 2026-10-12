# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

PALETTE = {
    "K": (0x1D, 0x2B, 0x53),
    "G": (0xC2, 0xC3, 0xC7),
    "S": (0x83, 0x76, 0x9C),
    "C": (0xFF, 0xF1, 0xE8),
    "R": (0xFF, 0x00, 0x4D),
    "B": (0x29, 0xAD, 0xFF),
    "Y": (0xFF, 0xEC, 0x27),
    "T": (0x7E, 0x25, 0x53),
    "E": (0x5F, 0x57, 0x4F),
    "W": (0xFF, 0xF1, 0xE8),
    "L": (0x34, 0x3A, 0x78),
}

CASSETTE = [
    "." + "K" * 22 + ".",
    "K" + "G" * 22 + "K",
    "KG" + "R" * 20 + "GK",
    "KG" + "B" * 20 + "GK",
    "KG" + "Y" * 20 + "GK",
    "KG" + "C" * 20 + "GK",
    "KG" + "C" * 20 + "GK",
    "K" + "G" * 22 + "K",
    "KGG" + "K" * 18 + "GGK",
    "KGGK" + "TTEEETTTTTTEEETT" + "KGGK",
    "KGGK" + "TTEWETTTTTTEWETT" + "KGGK",
    "KGGK" + "TTEEETTTTTTEEETT" + "KGGK",
    "KGG" + "K" * 18 + "GGK",
    "K" + "G" * 22 + "K",
    "K" + "S" * 22 + "K",
    "." + "K" * 22 + ".",
]

CASSETTE_MINI = [
    ".KKKKKKKK.",
    "KRRRRRRRRK",
    "KBBBBBBBBK",
    "KYYYYYYYYK",
    "KTWTTTTWTK",
    ".KKKKKKKK.",
]

FONT = {
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
}

WORDMARK = "SAIDBY"
LETTER_COLOR = "B"
SHADOW_COLOR = "L"
