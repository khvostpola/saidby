# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import release  # noqa: E402

CHANGELOG = """# Changelog

All notable changes are documented here.

## [Unreleased]

### Fixed
- A thing was broken.
- Another thing too.

## [0.7.0] - 2026-10-12

### Added
- Windows support.
"""

BUMPED = """# Changelog

All notable changes are documented here.

## [Unreleased]

## [0.7.1] - 2026-10-20

### Fixed
- A thing was broken.
- Another thing too.

## [0.7.0] - 2026-10-12

### Added
- Windows support.
"""


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    return result.stdout.strip()


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    config = tmp_path / "gitconfig"
    config.write_text(
        f"[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n"
        f"[core]\n\thooksPath = {hooks.as_posix()}\n",
        encoding="utf-8",
        newline="\n",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "t")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "t@example.com")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    work = tmp_path / "work"
    bare = tmp_path / "origin.git"
    work.mkdir()
    git(work, "init", "-b", "main")
    (work / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8", newline="\n")
    git(work, "add", ".")
    git(work, "commit", "-m", "init")
    git(tmp_path, "clone", "--bare", str(work), str(bare))
    git(work, "remote", "add", "origin", str(bare))
    git(work, "fetch", "origin")
    git(work, "branch", "--set-upstream-to=origin/main", "main")
    return work


def test_parse_version_valid() -> None:
    assert release.parse_version("0.7.10") == (0, 7, 10)


@pytest.mark.parametrize("text", ["1.2", "v1.2.3", "1.2.3.4", "1.2.x", "", "1.2.3-rc1"])
def test_parse_version_malformed(text: str) -> None:
    with pytest.raises(ValueError, match="not a version"):
        release.parse_version(text)


def test_versions_compare_as_integers() -> None:
    release.check_newer("0.9.0", "0.10.0")
    release.check_newer("0.7.0", "0.7.1")


@pytest.mark.parametrize("new", ["0.7.0", "0.6.9", "0.2.0"])
def test_version_not_greater_is_refused(new: str) -> None:
    with pytest.raises(release.ReleaseError, match="not greater"):
        release.check_newer("0.7.0", new)


def test_malformed_argument_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        release.main(["1.2", "--dry-run"])
    assert exit_info.value.code == 2
    assert "not a version" in capsys.readouterr().err


def test_bump_changelog_moves_the_unreleased_notes() -> None:
    assert release.bump_changelog(CHANGELOG, "0.7.1", "2026-10-20") == BUMPED


def test_bump_changelog_without_older_sections() -> None:
    text = "# Changelog\n\n## [Unreleased]\n\n### Added\n- One.\n"
    assert release.bump_changelog(text, "0.1.0", "2026-01-01") == (
        "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n### Added\n- One.\n"
    )


def test_unreleased_entries() -> None:
    assert release.unreleased_entries(CHANGELOG) == [
        "### Fixed",
        "- A thing was broken.",
        "- Another thing too.",
    ]


def test_empty_unreleased_is_refused() -> None:
    empty = CHANGELOG.replace("### Fixed\n- A thing was broken.\n- Another thing too.\n", "")
    with pytest.raises(release.ReleaseError, match="nothing under"):
        release.bump_changelog(empty, "0.7.1", "2026-10-20")


def test_missing_unreleased_heading_is_refused() -> None:
    with pytest.raises(release.ReleaseError, match="no ## \\[Unreleased\\]"):
        release.bump_changelog("# Changelog\n", "0.7.1", "2026-10-20")


def test_version_already_in_changelog_is_refused() -> None:
    with pytest.raises(release.ReleaseError, match="already has"):
        release.bump_changelog(CHANGELOG, "0.7.0", "2026-10-20")


def test_clean_main_in_sync_passes(repo: Path) -> None:
    release.check_branch(repo)
    release.check_clean(repo)
    release.check_synced(repo)
    release.check_tag_free(repo, "0.7.1")


def test_dirty_tree_is_refused(repo: Path) -> None:
    (repo / "stray.txt").write_text("x", encoding="utf-8", newline="\n")
    with pytest.raises(release.ReleaseError, match="not clean"):
        release.check_clean(repo)


def test_modified_tracked_file_is_refused(repo: Path) -> None:
    (repo / "CHANGELOG.md").write_text("changed", encoding="utf-8", newline="\n")
    with pytest.raises(release.ReleaseError, match="not clean"):
        release.check_clean(repo)


def test_wrong_branch_is_refused(repo: Path) -> None:
    git(repo, "checkout", "-b", "feature")
    with pytest.raises(release.ReleaseError, match="not main"):
        release.check_branch(repo)


def test_local_tag_is_refused(repo: Path) -> None:
    git(repo, "tag", "v0.7.1")
    with pytest.raises(release.ReleaseError, match="locally"):
        release.check_tag_free(repo, "0.7.1")


def test_remote_tag_is_refused(repo: Path) -> None:
    git(repo, "tag", "v0.7.1")
    git(repo, "push", "origin", "v0.7.1")
    git(repo, "tag", "-d", "v0.7.1")
    with pytest.raises(release.ReleaseError, match="on origin"):
        release.check_tag_free(repo, "0.7.1")


def test_main_ahead_of_origin_is_refused(repo: Path) -> None:
    (repo / "extra.txt").write_text("x", encoding="utf-8", newline="\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "extra")
    with pytest.raises(release.ReleaseError, match="differ"):
        release.check_synced(repo)


def test_main_behind_origin_is_refused(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    git(tmp_path, "clone", str(tmp_path / "origin.git"), str(other))
    (other / "extra.txt").write_text("x", encoding="utf-8", newline="\n")
    git(other, "add", ".")
    git(other, "commit", "-m", "extra")
    git(other, "push", "origin", "main")
    with pytest.raises(release.ReleaseError, match="differ"):
        release.check_synced(repo)
