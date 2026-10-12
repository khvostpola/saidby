# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import argparse
from dataclasses import dataclass
from typing import Literal

from saidby.errors import UsageError
from saidby.i18n import _

Role = Literal["asr", "diarizer", "embedder", "llm"]


@dataclass(frozen=True)
class ModelSpec:
    key: str
    repo_id: str
    revision: str
    role: Role
    default: bool
    license_spdx: str
    gated: bool
    commercial_ok: bool
    attribution: str
    url: str
    accept_url: str | None = None
    filename: str | None = None

    def __post_init__(self) -> None:
        if self.default and not self.commercial_ok:
            raise ValueError(f"{self.key}: a default model must allow commercial use")


REGISTRY: tuple[ModelSpec, ...] = (
    ModelSpec(
        key="asr:large-v3",
        repo_id="Systran/faster-whisper-large-v3",
        revision="edaa852ec7e145841d8ffdb056a99866b5f0a478",
        role="asr",
        default=True,
        license_spdx="MIT",
        gated=False,
        commercial_ok=True,
        attribution="OpenAI Whisper large-v3, converted for CTranslate2 by Systran",
        url="https://huggingface.co/Systran/faster-whisper-large-v3",
    ),
    ModelSpec(
        key="asr:tiny",
        repo_id="Systran/faster-whisper-tiny",
        revision="d90ca5fe260221311c53c58e660288d3deb8d356",
        role="asr",
        default=False,
        license_spdx="MIT",
        gated=False,
        commercial_ok=True,
        attribution="OpenAI Whisper tiny, converted for CTranslate2 by Systran",
        url="https://huggingface.co/Systran/faster-whisper-tiny",
    ),
    ModelSpec(
        key="diarizer:nemotron3",
        repo_id="nvidia/Nemotron-3-Diarization",
        revision="f667ed73aee57d40cc39428eb768b4fd87a0a29e",
        role="diarizer",
        default=True,
        license_spdx="OpenMDW-1.1",
        gated=False,
        commercial_ok=True,
        attribution="NVIDIA Nemotron-3-Diarization",
        url="https://huggingface.co/nvidia/Nemotron-3-Diarization",
    ),
    ModelSpec(
        key="diarizer:pyannote-community1",
        repo_id="pyannote/speaker-diarization-community-1",
        revision="3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
        role="diarizer",
        default=False,
        license_spdx="CC-BY-4.0",
        gated=True,
        commercial_ok=True,
        attribution="pyannote.audio speaker-diarization community-1 (CC BY 4.0)",
        url="https://huggingface.co/pyannote/speaker-diarization-community-1",
        accept_url="https://hf.co/pyannote/speaker-diarization-community-1",
    ),
    ModelSpec(
        key="embedder:wespeaker-resnet34",
        repo_id="pyannote/wespeaker-voxceleb-resnet34-LM",
        revision="837717ddb9ff5507820346191109dc79c958d614",
        role="embedder",
        default=True,
        license_spdx="CC-BY-4.0",
        gated=False,
        commercial_ok=True,
        attribution="WeSpeaker ResNet34-LM as packaged by pyannote (CC BY 4.0)",
        url="https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM",
    ),
    ModelSpec(
        key="llm:qwen3.5-9b-q4",
        repo_id="unsloth/Qwen3.5-9B-GGUF",
        revision="3885219b6810b007914f3a7950a8d1b469d598a5",
        role="llm",
        default=False,
        license_spdx="Apache-2.0",
        gated=False,
        commercial_ok=True,
        attribution="Qwen3.5-9B Q4_K_M GGUF by Unsloth",
        url="https://huggingface.co/unsloth/Qwen3.5-9B-GGUF",
        filename="Qwen3.5-9B-Q4_K_M.gguf",
    ),
)


def get_spec(key: str) -> ModelSpec:
    for spec in REGISTRY:
        if spec.key == key:
            return spec
    valid = ", ".join(s.key for s in REGISTRY)
    raise UsageError(
        _("unknown model key {key!r}; valid keys: {valid}").format(key=key, valid=valid)
    )


def render_markdown() -> str:
    lines = [
        "# Model licenses",
        "",
        "saidby never ships model weights. This table is generated from "
        "`saidby.models.registry`; run `python -m saidby.models.registry --markdown` "
        "to refresh it.",
        "",
        "| Key | Repository | Revision | Role | Default | License | Gated | Attribution |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in REGISTRY:
        lines.append(
            f"| `{s.key}` | [{s.repo_id}]({s.url}) | `{s.revision[:8]}` | {s.role} "
            f"| {'yes' if s.default else 'no'} | {s.license_spdx} "
            f"| {'yes' if s.gated else 'no'} | {s.attribution} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", action="store_true")
    parser.parse_args()
    print(render_markdown(), end="")


if __name__ == "__main__":
    main()
