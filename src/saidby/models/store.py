# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path

from saidby.errors import ModelUnavailableError
from saidby.models.registry import ModelSpec


def _hub_cache() -> Path:
    from huggingface_hub import constants

    return Path(constants.HF_HUB_CACHE)


def _snapshot_dir(spec: ModelSpec) -> Path:
    folder = "models--" + spec.repo_id.replace("/", "--")
    return _hub_cache() / folder / "snapshots" / spec.revision


def is_installed(spec: ModelSpec) -> bool:
    snapshot = _snapshot_dir(spec)
    if not snapshot.is_dir():
        return False
    if spec.filename is not None:
        return (snapshot / spec.filename).exists()
    return any(snapshot.iterdir())


def local_path(spec: ModelSpec) -> Path:
    if not is_installed(spec):
        raise ModelUnavailableError(
            f"model {spec.key} is not installed; run: saidby models pull {spec.key}"
        )
    snapshot = _snapshot_dir(spec)
    return snapshot / spec.filename if spec.filename else snapshot


def local_revision(spec: ModelSpec) -> str:
    return _snapshot_dir(spec).name if is_installed(spec) else spec.revision


def size_bytes(spec: ModelSpec) -> int | None:
    if not is_installed(spec):
        return None
    total = 0
    for root, _, files in os.walk(_snapshot_dir(spec)):
        for name in files:
            total += (Path(root) / name).stat().st_size
    return total


def pull(spec: ModelSpec, *, token: str | None = None) -> Path:
    from huggingface_hub import hf_hub_download, snapshot_download
    from huggingface_hub.errors import GatedRepoError, RepositoryNotFoundError

    try:
        if spec.filename:
            path = hf_hub_download(spec.repo_id, spec.filename, revision=spec.revision, token=token)
            return Path(path)
        return Path(snapshot_download(spec.repo_id, revision=spec.revision, token=token))
    except (GatedRepoError, RepositoryNotFoundError) as exc:
        if spec.gated:
            raise ModelUnavailableError(
                f"{spec.repo_id} is gated: accept its conditions at {spec.accept_url} "
                "and provide your token with HF_TOKEN"
            ) from exc
        raise ModelUnavailableError(f"cannot download {spec.repo_id}: {exc}") from exc
