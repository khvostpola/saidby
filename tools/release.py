# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

"""Prepare, check, commit, tag and push a release: steps 1 to 4 of docs/release.md."""

import argparse
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
UNRELEASED = "## [Unreleased]"
RELEASE_FILES = ("CHANGELOG.md", "pyproject.toml", "uv.lock")
ACTIONS_URL = "https://github.com/khvostpola/saidby/actions"
CHECKS = (
    ("uv", "run", "ruff", "check", "."),
    ("uv", "run", "ruff", "format", "--check", "."),
    ("uv", "run", "mypy"),
    ("uv", "run", "pytest", "-m", "not gpu", "-q"),
)


class ReleaseError(Exception):
    """A precondition or check failed; the message says why."""


def parse_version(text: str) -> tuple[int, int, int]:
    """Parse X.Y.Z into integers."""
    if not VERSION.match(text):
        raise ValueError(f"not a version X.Y.Z: {text!r}")
    major, minor, patch = (int(part) for part in text.split("."))
    return major, minor, patch


def _run(
    repo: Path, *command: str, capture: bool = True, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=repo,
        check=check,
        text=True,
        encoding="utf-8",
        capture_output=capture,
    )


def _git(repo: Path, *args: str) -> str:
    try:
        return _run(repo, "git", *args).stdout.strip()
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or "").strip() or f"exit {error.returncode}"
        raise ReleaseError(f"git {' '.join(args)} failed: {detail}") from error


def current_version(repo: Path) -> str:
    """The version `uv version --short` reports for the project."""
    try:
        return _run(repo, "uv", "version", "--short").stdout.strip()
    except subprocess.CalledProcessError as error:
        raise ReleaseError(f"uv version --short failed: {(error.stderr or '').strip()}") from error


def check_branch(repo: Path) -> None:
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        raise ReleaseError(f"branch is not main (on {branch})")


def check_clean(repo: Path) -> None:
    if _git(repo, "status", "--porcelain"):
        raise ReleaseError("working tree is not clean (tracked or untracked changes)")


def check_synced(repo: Path) -> None:
    _git(repo, "fetch", "origin")
    if _git(repo, "rev-parse", "main") != _git(repo, "rev-parse", "origin/main"):
        raise ReleaseError("main and origin/main differ; push or pull first")


def check_newer(current: str, new: str) -> None:
    if parse_version(new) <= parse_version(current):
        raise ReleaseError(f"{new} is not greater than the current version {current}")


def check_tag_free(repo: Path, version: str) -> None:
    tag = f"v{version}"
    if _git(repo, "tag", "--list", tag):
        raise ReleaseError(f"tag {tag} already exists locally")
    if _git(repo, "ls-remote", "--tags", "origin", f"refs/tags/{tag}"):
        raise ReleaseError(f"tag {tag} already exists on origin")


def _section_bounds(lines: list[str]) -> tuple[int, int]:
    try:
        start = lines.index(UNRELEASED)
    except ValueError:
        raise ReleaseError(f"CHANGELOG.md has no {UNRELEASED} heading") from None
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## [")), len(lines))
    return start, end


def unreleased_entries(text: str) -> list[str]:
    """The non-blank lines under `## [Unreleased]`."""
    lines = text.split("\n")
    start, end = _section_bounds(lines)
    return [line for line in lines[start + 1 : end] if line.strip()]


def check_changelog(text: str, version: str) -> None:
    if not unreleased_entries(text):
        raise ReleaseError("CHANGELOG.md has nothing under [Unreleased]")
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.MULTILINE):
        raise ReleaseError(f"CHANGELOG.md already has a [{version}] section")


def bump_changelog(text: str, version: str, date: str) -> str:
    """Move the Unreleased notes under a new dated version heading."""
    check_changelog(text, version)
    lines = text.split("\n")
    start, end = _section_bounds(lines)
    body = lines[start + 1 : end]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    moved = [UNRELEASED, "", f"## [{version}] - {date}", "", *body]
    return "\n".join([*lines[:start], *moved, "", *lines[end:]])


def check_preconditions(repo: Path, version: str) -> None:
    check_branch(repo)
    check_clean(repo)
    check_synced(repo)
    check_newer(current_version(repo), version)
    check_tag_free(repo, version)
    text = (repo / "CHANGELOG.md").read_text(encoding="utf-8")
    check_changelog(text, version)


def restore(repo: Path) -> None:
    _run(repo, "git", "checkout", "--", *RELEASE_FILES)


def run_checks(repo: Path, version: str) -> None:
    """Run the CI gates, build the wheel and smoke it; raise ReleaseError on any failure."""
    for command in CHECKS:
        print(f"$ {' '.join(command)}", flush=True)
        if _run(repo, *command, capture=False, check=False).returncode:
            raise ReleaseError(f"check failed: {' '.join(command)}")
    shutil.rmtree(repo / "dist", ignore_errors=True)
    print("$ uv build", flush=True)
    if _run(repo, "uv", "build", capture=False, check=False).returncode:
        raise ReleaseError("check failed: uv build")
    wheel = f"dist/saidby-{version}-py3-none-any.whl"
    smoke = _run(
        repo,
        "uv",
        "run",
        "--isolated",
        "--no-project",
        "--with",
        wheel,
        "--",
        "saidby",
        "--version",
        check=False,
    )
    if smoke.returncode or smoke.stdout.strip() != version:
        raise ReleaseError(
            f"wheel smoke failed: expected {version!r}, got {smoke.stdout.strip()!r}"
        )


def summary(rows: list[tuple[str, str]]) -> str:
    width = max(len(field) for field, _ in rows)
    return "\n".join(f"{field.ljust(width)}  {value}" for field, value in rows)


def summary_rows(repo: Path, previous: str, version: str, date: str) -> list[tuple[str, str]]:
    return [
        ("previous version", previous),
        ("new version", version),
        ("date", date),
        ("files changed", ", ".join(_git(repo, "status", "--short").splitlines())),
        ("commit title", f"chore: release {version}"),
        ("tag", f"v{version}"),
        ("push", "origin main --follow-tags"),
        ("remote", _git(repo, "remote", "get-url", "origin")),
    ]


def _fail(message: str, code: int = 1) -> int:
    print(f"error: {message}", file=sys.stderr)
    return code


def _abort(repo: Path, message: str) -> int:
    restore(repo)
    return _fail(f"{message}; nothing was committed")


def _publish(repo: Path, version: str) -> None:
    _run(repo, "git", "add", *RELEASE_FILES)
    _run(repo, "git", "commit", "-s", "-m", f"chore: release {version}", capture=False)
    _run(repo, "git", "tag", "-s", f"v{version}", "-m", f"saidby {version}", capture=False)
    _run(repo, "git", "push", "origin", "main", "--follow-tags", capture=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="release.py", description="Prepare, check, commit, tag and push a release."
    )
    parser.add_argument("version", help="new version, X.Y.Z")
    parser.add_argument("--dry-run", action="store_true", help="show the summary, change nothing")
    parser.add_argument("--skip-checks", action="store_true", help="skip lint, tests and the build")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    version: str = args.version
    try:
        parse_version(version)
    except ValueError as error:
        parser.error(str(error))
    if not (args.yes or args.dry_run or sys.stdin.isatty()):
        return _fail("stdin is not a terminal; pass --yes to release without asking", 2)

    return _release(ROOT, args)


def _prepare(repo: Path, args: argparse.Namespace, date: str) -> str | None:
    """Rewrite the three files and run the checks; return why it failed, if it did."""
    version: str = args.version
    changelog = repo / "CHANGELOG.md"
    text = changelog.read_text(encoding="utf-8")
    with changelog.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(bump_changelog(text, version, date))
    try:
        _run(repo, "uv", "version", version, "--no-sync")
        if not args.skip_checks:
            run_checks(repo, version)
    except subprocess.CalledProcessError as error:
        return f"{' '.join(error.cmd)} failed: {(error.stderr or '').strip()}"
    except ReleaseError as error:
        return str(error)
    return None


def _release(repo: Path, args: argparse.Namespace) -> int:
    version: str = args.version
    try:
        check_preconditions(repo, version)
    except ReleaseError as error:
        return _fail(str(error))

    previous = current_version(repo)
    date = datetime.date.today().isoformat()
    problem = _prepare(repo, args, date)
    if problem:
        return _abort(repo, problem)

    print(summary(summary_rows(repo, previous, version, date)))
    if args.dry_run:
        restore(repo)
        print("dry run: files restored")
        return 0
    if not args.yes and input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
        return _abort(repo, "aborted")

    try:
        _publish(repo, version)
    except subprocess.CalledProcessError as error:
        return _fail(f"{' '.join(error.cmd)} failed; inspect the repository before retrying")
    print(f"\nNext: approve the pypi deployment at {ACTIONS_URL}")
    print(f'Then: uv tool install --reinstall "saidby[cuda]=={version}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
