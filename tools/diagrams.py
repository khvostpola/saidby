# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

STYLE = """
<style>
  .bg { fill: #ffffff; }
  .frame { fill: none; stroke: #d5dcdc; }
  .box { fill: #f6fafa; stroke: #0e6170; stroke-width: 1.6; }
  .plain { fill: #f1f3f3; stroke: #8a9799; stroke-width: 1.4; }
  .warm { fill: #fff7e8; stroke: #b7791f; stroke-width: 1.6; }
  .good { fill: #eef8f1; stroke: #17703f; stroke-width: 1.6; }
  .optional { stroke-dasharray: 7 5; }
  .band { fill: #eef3f4; stroke: #c3cfd1; }
  .t { font: 600 14.5px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #141819; }
  .s { font: 12px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #4f5f63; }
  .h { font: 700 16px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #141819; }
  .n { font: 12.5px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #3b4a4e; }
  .tag { font: 600 10.5px system-ui, -apple-system, 'Segoe UI', sans-serif; fill: #8a5a00; }
  .line { stroke: #0e6170; stroke-width: 1.8; fill: none; }
  .dash { stroke: #8a9799; stroke-width: 1.5; fill: none; stroke-dasharray: 5 5; }
  .head { fill: #0e6170; }
  .dhead { fill: #8a9799; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #12181b; }
    .frame { stroke: #2b373b; }
    .box { fill: #172327; stroke: #5cc3d1; }
    .plain { fill: #1b2225; stroke: #6c7b7e; }
    .warm { fill: #2a2314; stroke: #e0a93b; }
    .good { fill: #14261c; stroke: #5fd08e; }
    .band { fill: #182125; stroke: #2f3f44; }
    .t, .h { fill: #e8eceb; }
    .s { fill: #a3b1b4; }
    .n { fill: #c1ccce; }
    .tag { fill: #e0a93b; }
    .line { stroke: #5cc3d1; }
    .dash { stroke: #6c7b7e; }
    .head { fill: #5cc3d1; }
    .dhead { fill: #6c7b7e; }
  }
</style>
"""

DEFS = """<defs>
<marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="head"/></marker>
<marker id="d" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="dhead"/></marker>
</defs>"""


@dataclass
class Canvas:
    width: int
    height: int
    title: str
    parts: list[str] = field(default_factory=list)

    def box(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        title: str,
        lines: list[str],
        kind: str = "box",
        optional: bool = False,
        tag: str | None = None,
    ) -> tuple[int, int, int, int]:
        cls = f"{kind}{' optional' if optional else ''}"
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" class="{cls}"/>')
        top = y + 24
        if tag:
            self.parts.append(
                f'<text x="{x + w / 2}" y="{y + 14}" text-anchor="middle" class="tag">{escape(tag)}</text>'
            )
            top = y + 32
        self.parts.append(
            f'<text x="{x + w / 2}" y="{top}" text-anchor="middle" class="t">{escape(title)}</text>'
        )
        for i, line in enumerate(lines):
            self.parts.append(
                f'<text x="{x + w / 2}" y="{top + 19 + i * 16}" text-anchor="middle" class="s">{escape(line)}</text>'
            )
        return (x, y, w, h)

    def text(self, x: int, y: int, content: str, cls: str = "n", anchor: str = "start") -> None:
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" class="{cls}">{escape(content)}</text>'
        )

    def band(self, x: int, y: int, w: int, h: int, label: str | None = None) -> None:
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" class="band"/>')
        if label:
            self.text(x + 16, y + 22, label, "h")

    def arrow(self, points: list[tuple[float, float]], dashed: bool = False) -> None:
        path = " ".join(f"{'M' if i == 0 else 'L'}{px},{py}" for i, (px, py) in enumerate(points))
        cls, marker = ("dash", "d") if dashed else ("line", "a")
        self.parts.append(f'<path d="{path}" class="{cls}" marker-end="url(#{marker})"/>')

    def render(self) -> str:
        body = "\n".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
            f'width="{self.width}" height="{self.height}" role="img" aria-label="{escape(self.title)}">\n'
            f"<title>{escape(self.title)}</title>\n{STYLE}\n{DEFS}\n"
            f'<rect class="bg" width="{self.width}" height="{self.height}" rx="14"/>\n'
            f'<rect class="frame" x="0.5" y="0.5" width="{self.width - 1}" height="{self.height - 1}" rx="14"/>\n'
            f"{body}\n</svg>\n"
        )


def right(b: tuple[int, int, int, int]) -> tuple[float, float]:
    return (b[0] + b[2], b[1] + b[3] / 2)


def left(b: tuple[int, int, int, int]) -> tuple[float, float]:
    return (b[0], b[1] + b[3] / 2)


def bottom(b: tuple[int, int, int, int]) -> tuple[float, float]:
    return (b[0] + b[2] / 2, b[1] + b[3])


def top(b: tuple[int, int, int, int]) -> tuple[float, float]:
    return (b[0] + b[2] / 2, b[1])


def pipeline() -> str:
    c = Canvas(1080, 470, "saidby pipeline: from a recording to a folder of results")
    c.text(540, 34, "From a recording to a folder of results", "h", "middle")
    w, h, gap, x0 = 150, 92, 26, 28
    xs = [x0 + i * (w + gap) for i in range(6)]
    y1, y2 = 62, 196
    rec = c.box(xs[0], y1, w, h, "Recording", ["audio or video", "anything ffmpeg reads"], "plain")
    ing = c.box(xs[1], y1, w, h, "ingest", ["ffmpeg", "16 kHz mono WAV"])
    asr = c.box(xs[2], y1, w, h, "transcribe", ["faster-whisper large-v3", "words + timestamps"])
    bias = c.box(
        xs[3],
        y1,
        w,
        h,
        "bias + transplant",
        ["2nd pass: your terms", "keeps the plain text"],
        "box",
        True,
        "WITH A DIRECTORY",
    )
    dia = c.box(xs[4], y1, w, h, "diarize", ["Nemotron-3", "who spoke, and when"])
    cmp_ = c.box(
        xs[5],
        y1,
        w,
        h,
        "compare",
        ["a 2nd diarizer", "where the two differ"],
        "box",
        True,
        "WITH --compare",
    )
    ident = c.box(
        xs[0],
        y2,
        w,
        h,
        "identify",
        ["voiceprints + consent", "names the speakers"],
        "box",
        True,
        "WITH VOICEPRINTS",
    )
    cor = c.box(
        xs[1],
        y2,
        w,
        h,
        "correct",
        ["local LLM, strict limits", "every change logged"],
        "box",
        True,
        "WITH --correct",
    )
    aln = c.box(xs[2], y2, w, h, "align", ["each word gets", "its speaker"])
    trk = c.box(xs[3], y2, w, h, "tracks", ["one FLAC per speaker", "same length as the call"])
    res = c.box(
        xs[4],
        y2,
        w + 176,
        h,
        "Results folder",
        ["transcript.txt  .vtt  .words.json", "diarization.rttm  manifest.json  corrections.jsonl"],
        "good",
    )
    for a, b in (
        (rec, ing),
        (ing, asr),
        (asr, bias),
        (bias, dia),
        (dia, cmp_),
        (ident, cor),
        (cor, aln),
        (aln, trk),
        (trk, res),
    ):
        c.arrow([right(a), left(b)])
    c.arrow([bottom(cmp_), (bottom(cmp_)[0], 176), (bottom(ident)[0], 176), top(ident)])
    c.band(28, 326, 1024, 62, None)
    c.text(46, 352, "Directory", "h")
    c.text(150, 352, "people, voiceprints, terms and slang you maintain in one YAML file", "n")
    c.text(
        46,
        374,
        "The stages with a dashed border read it (or --compare, --correct). The rest needs no setup.",
        "s",
    )
    c.band(28, 404, 1024, 44, None)
    c.text(
        46,
        431,
        "Models are downloaded once with  saidby models pull  and processing never opens a network connection.",
        "n",
    )
    return c.render()


def glossary() -> str:
    c = Canvas(1080, 430, "How saidby gets your names and terms right")
    c.text(540, 34, "How your names and terms end up spelled right", "h", "middle")
    y = 70
    plain = c.box(
        28,
        y,
        190,
        96,
        "Plain pass",
        ["the recognizer as it is", "faithful to what is said", "but terms come out garbled"],
        "plain",
    )
    biased = c.box(
        28,
        y + 130,
        190,
        96,
        "Biased pass",
        ["same audio, with your terms", "as hotwords", "finds terms, can derail"],
        "warm",
    )
    trans = c.box(
        284,
        y + 56,
        190,
        96,
        "Transplant",
        ["keeps the plain text and", "takes only the spans where", "the biased pass wrote a term"],
    )
    dial = c.box(
        540,
        y + 56,
        170,
        96,
        "Slang unified",
        ["variants of dialect terms", "become one spelling"],
        "box",
    )
    llm = c.box(
        776,
        y,
        276,
        104,
        "Optional LLM pass",
        [
            "proposes replacing 1 to 3 words",
            "with a term from your directory",
            "a local llama-server, off by default",
        ],
        "box",
        True,
        "WITH --correct",
    )
    guard = c.box(
        776,
        y + 126,
        276,
        108,
        "Guardrails (in code)",
        [
            "only directory terms or variants",
            "the original must resemble the term",
            "overlaps and truncated replies dropped",
            "timestamps are never touched",
        ],
        "warm",
    )
    out = c.box(
        284,
        y + 190,
        426,
        76,
        "Final transcript + corrections.jsonl",
        [
            "every change: when, from, to, who made it",
            "(bias, dialect, llm, review) and why a proposal was rejected",
        ],
        "good",
    )
    c.arrow([right(plain), left(trans)])
    c.arrow([right(biased), left(trans)])
    c.arrow([right(trans), left(dial)])
    c.arrow([right(dial), left(llm)])
    c.arrow([bottom(llm), top(guard)])
    c.arrow(
        [left(guard), (730, guard[1] + guard[3] / 2), (730, out[1] + out[3] / 2), right(out)], False
    )
    c.arrow([bottom(dial), (bottom(dial)[0], out[1] - 0)], False)
    c.band(28, 352, 1024, 56, None)
    c.text(46, 376, "Measured on one 15-minute call:", "h")
    c.text(
        352,
        376,
        "terms spelled right 36% with the plain pass, 59% after the transplant (docs/benchmarks.md).",
        "n",
    )
    c.text(
        46,
        396,
        "Hotwords alone are fragile (they can make the recognizer skip passages), which is why saidby never trusts the biased pass for the text.",
        "s",
    )
    return c.render()


def people() -> str:
    c = Canvas(1080, 408, "How saidby learns who is speaking")
    c.text(540, 34, "Naming the speakers, with consent", "h", "middle")
    c.band(28, 56, 500, 196, "1. Enroll once")
    e1 = c.box(48, 100, 140, 80, "A finished run", ["SPEAKER_00,", "SPEAKER_01"], "plain")
    e2 = c.box(214, 100, 140, 80, "Consent", ["recorded in", "consent.yaml"], "warm")
    e3 = c.box(380, 100, 128, 80, "Voiceprint", ["a vector, never", "audio"], "good")
    c.arrow([right(e1), left(e2)])
    c.arrow([right(e2), left(e3)])
    c.text(
        48, 214, "saidby enroll out/call --speaker SPEAKER_00=ana --directory directory.yaml", "s"
    )
    c.text(48, 236, "No consent record, no voiceprint (exit code 5).", "s")
    c.band(552, 56, 500, 196, "2. Every later run")
    i1 = c.box(
        572,
        100,
        140,
        80,
        "Voice sample",
        ["longest clean turns,", "up to 60 s per speaker"],
        "plain",
    )
    i2 = c.box(738, 100, 128, 80, "Compare", ["cosine similarity", "to each voiceprint"])
    i3 = c.box(892, 100, 140, 80, "Names", ["one person per", "speaker, at most"], "good")
    c.arrow([right(i1), left(i2)])
    c.arrow([right(i2), left(i3)])
    c.text(572, 214, "A name is assigned only if the similarity is at least 0.5", "s")
    c.text(572, 236, "and the speaker has at least 3 s of speech. Otherwise: SPEAKER_nn.", "s")
    c.band(28, 272, 1024, 116, "Fixing what the machine got wrong, without reprocessing audio")
    c.text(46, 316, "saidby speakers map out/call --set SPEAKER_01=ben", "n")
    c.text(46, 336, "rename a speaker", "s")
    c.text(500, 316, "saidby speakers merge out/call SPEAKER_02 --into SPEAKER_00", "n")
    c.text(500, 336, "join a person the diarizer split in two", "s")
    c.text(
        46,
        366,
        "Both rewrite the transcript, subtitles, RTTM, tracks and manifest, and record the edit in manifest.json.",
        "s",
    )
    return c.render()


def loop() -> str:
    c = Canvas(1080, 420, "The improvement loop: run, review, teach the directory, run again")
    c.text(540, 34, "A loop that makes the next run better", "h", "middle")
    run = c.box(40, 80, 190, 96, "1. Run", ["saidby process", "--directory, --compare"], "box")
    rev = c.box(
        310,
        80,
        210,
        96,
        "2. Review",
        [
            "saidby review out/call",
            "disagreements, rejected LLM",
            "proposals, low-confidence words",
        ],
        "warm",
    )
    fix = c.box(
        600,
        80,
        200,
        96,
        "3. You fix it",
        ["type the right text or", "who spoke; Enter keeps"],
        "plain",
    )
    dirb = c.box(
        880,
        80,
        170,
        96,
        "4. Directory learns",
        ["new spellings become", "variants (with backup)"],
        "good",
    )
    c.arrow([right(run), left(rev)])
    c.arrow([right(rev), left(fix)])
    c.arrow([right(fix), left(dirb)])
    c.arrow([bottom(dirb), (bottom(dirb)[0], 206), (bottom(run)[0], 206), bottom(run)], False)
    c.text(540, 232, "the next run starts from a better directory", "s", "middle")
    c.band(28, 262, 1024, 130, "Measuring, when you want to know whether it is better")
    c.text(46, 312, "saidby eval score reference.txt out/call", "n")
    c.text(
        46,
        332,
        "WER, directory terms spelled right, diarization error and speaker confusion against a hand-corrected stretch.",
        "s",
    )
    c.text(46, 358, "saidby eval arbitrate-build / arbitrate-serve / arbitrate-score", "n")
    c.text(
        46,
        378,
        "Listen blind to the spans where two systems disagree; get the WER difference with a 95% interval and a pre-set margin.",
        "s",
    )
    return c.render()


DIAGRAMS = {"pipeline": pipeline, "glossary": glossary, "people": people, "loop": loop}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("docs/img"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, build in DIAGRAMS.items():
        (args.out / f"{name}.svg").write_text(build(), encoding="utf-8")
        print(f"wrote {args.out / f'{name}.svg'}")


if __name__ == "__main__":
    main()
