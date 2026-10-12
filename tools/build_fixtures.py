# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
import hashlib
import io
import json
import random
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000
TURNS = (
    ("SPEAKER_00", 0.5, 3.0, 220.0),
    ("SPEAKER_01", 3.6, 6.0, 440.0),
    ("SPEAKER_00", 6.4, 8.2, 220.0),
    ("SPEAKER_01", 8.5, 9.8, 440.0),
)
DURATION_S = 10.0


def synthetic_audio(seed: int = 1234) -> np.ndarray:
    rng = np.random.default_rng(seed)
    audio = 0.002 * rng.standard_normal(int(DURATION_S * SAMPLE_RATE))
    for _, start, end, freq in TURNS:
        t = np.arange(int(start * SAMPLE_RATE), int(end * SAMPLE_RATE)) / SAMPLE_RATE
        audio[int(start * SAMPLE_RATE) : int(end * SAMPLE_RATE)] += 0.3 * np.sin(
            2 * np.pi * freq * t
        )
    return audio.astype(np.float32)


def synthetic_rttm(uri: str) -> str:
    return "".join(
        f"SPEAKER {uri} 1 {start:.3f} {end - start:.3f} <NA> <NA> {speaker} <NA> <NA>\n"
        for speaker, start, end, _ in TURNS
    )


def build_synthetic(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sf.write(
        out / "tones_2spk_10s.flac", synthetic_audio(), SAMPLE_RATE, format="FLAC", subtype="PCM_16"
    )
    (out / "tones_2spk_10s.rttm").write_text(
        synthetic_rttm("tones_2spk_10s"), encoding="utf-8", newline="\n"
    )


MLS_REPO = "facebook/multilingual_librispeech"
MLS_REVISION = "refs/convert/parquet"
PARTITIONS = {"dev": "dev", "test": "test"}
SPEAKERS_PER_PARTITION = 4
TURNS_PER_CONVERSATION = 4
MIN_CLIP_S, MAX_CLIP_S = 10.0, 12.5
BUDGET_BYTES = 10_000_000
SEED = 20261011
PROFILES = {
    "phone-pstn": (
        "wav",
        ["-af", "highpass=f=300,lowpass=f=3400", "-ar", "8000", "-c:a", "pcm_mulaw"],
    ),
    "phone-mobile": (
        "amr",
        ["-ar", "8000", "-ac", "1", "-c:a", "libopencore_amrnb", "-b:a", "7.4k"],
    ),
    "voip-app": ("opus", ["-c:a", "libopus", "-b:a", "12k", "-application", "voip"]),
}
ATTRIBUTION = (
    "Multilingual LibriSpeech (Pratap et al., 2020), derived from LibriVox public-domain "
    "recordings, licensed CC BY 4.0: https://huggingface.co/datasets/facebook/multilingual_librispeech"
)


def _usable(transcript: str) -> bool:
    return len(transcript.split()) >= 12 and not re.search(r"\d", transcript)


def load_candidates(cache: Path, split: str) -> dict[str, list[dict[str, Any]]]:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = hf_hub_download(
        MLS_REPO,
        f"spanish/{split}/0000.parquet",
        repo_type="dataset",
        revision=MLS_REVISION,
        local_dir=cache,
    )
    table = pq.read_table(
        path, columns=["audio", "speaker_id", "audio_duration", "transcript", "id"]
    )
    by_speaker: dict[str, list[dict[str, Any]]] = {}
    for row in table.to_pylist():
        if MIN_CLIP_S <= row["audio_duration"] <= MAX_CLIP_S and _usable(row["transcript"]):
            by_speaker.setdefault(str(row["speaker_id"]), []).append(row)
    need = TURNS_PER_CONVERSATION // 2
    return {
        s: sorted(rows, key=lambda r: r["id"])
        for s, rows in sorted(by_speaker.items())
        if len(rows) >= need
    }


def decode(row: dict[str, Any]) -> np.ndarray:
    data, rate = sf.read(io.BytesIO(row["audio"]["bytes"]), dtype="float32")
    if rate != SAMPLE_RATE:
        raise ValueError(f"unexpected sample rate {rate}")
    return np.asarray(data, dtype=np.float32)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_conversation(
    rng: random.Random,
    conv_id: str,
    speakers: tuple[str, str],
    pool: dict[str, list[dict[str, Any]]],
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    queues = {s: list(pool[s]) for s in speakers}
    for q in queues.values():
        rng.shuffle(q)
    timeline = np.zeros(0, dtype=np.float32)
    turns: list[dict[str, Any]] = []
    cursor = 0.0
    for i in range(TURNS_PER_CONVERSATION):
        speaker = speakers[i % 2]
        row = queues[speaker].pop()
        clip = decode(row) * 0.7
        overlap = 0.4 if i == 3 else 0.0
        gap = -overlap if overlap else rng.uniform(0.3, 1.2)
        start = max(0.0, cursor + gap)
        s0 = int(start * SAMPLE_RATE)
        needed = s0 + len(clip)
        if needed > len(timeline):
            timeline = np.pad(timeline, (0, needed - len(timeline)))
        timeline[s0 : s0 + len(clip)] += clip
        end = start + len(clip) / SAMPLE_RATE
        turns.append(
            {
                "speaker": f"spk_{speaker}",
                "start": round(start, 3),
                "end": round(end, 3),
                "text": row["transcript"],
                "source_id": row["id"],
            }
        )
        cursor = end
    peak = float(np.max(np.abs(timeline)))
    return (timeline * (0.89 / peak) if peak > 0.89 else timeline).astype(np.float32), turns


def ffmpeg(args: list[str]) -> None:
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


def apply_profiles(clean: Path, stem: Path, duration: float, seed: int) -> dict[str, Path]:
    outputs: dict[str, Path] = {}
    for name, (ext, args) in PROFILES.items():
        target = stem.with_suffix(f".{name}.{ext}")
        ffmpeg(["-i", str(clean), *args, str(target)])
        outputs[name] = target
    room = stem.with_suffix(".room-recorder.opus")
    graph = (
        "[0:a]aecho=0.8:0.6:40|75:0.25|0.15,highpass=f=80,lowpass=f=7000[a];"
        f"anoisesrc=c=pink:a=0.003:s={seed}:d={duration:.2f}:r={SAMPLE_RATE}[n];"
        "[a][n]amix=inputs=2:duration=first:normalize=0"
    )
    ffmpeg(
        ["-i", str(clean), "-filter_complex", graph, "-c:a", "libopus", "-b:a", "32k", str(room)]
    )
    outputs["room-recorder"] = room
    return outputs


def build_speech(out: Path, cache: Path) -> None:
    rng = random.Random(SEED)
    out_dir = out / "conversations"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema": "saidby.fixtures/1",
        "attribution": ATTRIBUTION,
        "license": "CC-BY-4.0",
        "conversations": [],
        "speakers": {},
    }
    for partition, split in PARTITIONS.items():
        pool = load_candidates(cache, split)
        speakers = sorted(pool)
        rng.shuffle(speakers)
        chosen = speakers[:SPEAKERS_PER_PARTITION]
        manifest["speakers"][partition] = chosen
        for n, pair in enumerate(zip(chosen[0::2], chosen[1::2], strict=True), 1):
            conv_id = f"{partition}-conv-{n:02d}"
            audio, turns = make_conversation(rng, conv_id, pair, pool)
            stem = out_dir / partition / conv_id
            stem.parent.mkdir(parents=True, exist_ok=True)
            clean = stem.with_suffix(".flac")
            sf.write(clean, audio, SAMPLE_RATE, format="FLAC", subtype="PCM_16")
            duration = len(audio) / SAMPLE_RATE
            variants = apply_profiles(clean, stem, duration, SEED + n)
            stem.with_suffix(".rttm").write_text(
                "".join(
                    f"SPEAKER {conv_id} 1 {t['start']:.3f} {t['end'] - t['start']:.3f} <NA> <NA> "
                    f"{t['speaker']} <NA> <NA>\n"
                    for t in turns
                ),
                encoding="utf-8",
                newline="\n",
            )
            expected = {
                "id": conv_id,
                "partition": partition,
                "duration_s": round(duration, 3),
                "turns": turns,
                "text": " ".join(t["text"] for t in turns),
            }
            stem.with_suffix(".expected.json").write_text(
                json.dumps(expected, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n"
            )
            files = [
                clean,
                *variants.values(),
                stem.with_suffix(".rttm"),
                stem.with_suffix(".expected.json"),
            ]
            manifest["conversations"].append(
                {
                    "id": conv_id,
                    "partition": partition,
                    "speakers": [f"spk_{s}" for s in pair],
                    "duration_s": round(duration, 3),
                    "files": {
                        str(f.relative_to(out)): {"sha256": sha256_of(f), "bytes": f.stat().st_size}
                        for f in files
                    },
                }
            )
    total = sum(v["bytes"] for c in manifest["conversations"] for v in c["files"].values())
    manifest["total_bytes"] = total
    if total > BUDGET_BYTES:
        raise SystemExit(f"fixtures use {total} bytes, over the {BUDGET_BYTES} budget")
    (out / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8", newline="\n"
    )
    (out / "ATTRIBUTION.md").write_text(
        "# Attribution\n\nThe speech in `conversations/` is built from clips of "
        f"{ATTRIBUTION}.\n\nModifications: utterances were concatenated into two-speaker "
        "conversations, mixed with a fixed seed, normalized and re-encoded with the channel "
        "profiles listed in `MANIFEST.json`.\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["synthetic", "speech"])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--cache", type=Path, default=Path(".work/fixtures-cache"))
    args = parser.parse_args()
    if args.command == "synthetic":
        build_synthetic(args.out or Path("fixtures/synthetic"))
    else:
        build_speech(args.out or Path("fixtures"), args.cache)


if __name__ == "__main__":
    main()
