# Releasing

1. Move the `Unreleased` notes in `CHANGELOG.md` under `## [X.Y.Z] - date`.
2. `uv version X.Y.Z`
3. `git commit -s -m "chore: release X.Y.Z"`
4. `git tag -s vX.Y.Z -m "saidby X.Y.Z"` and `git push origin main --follow-tags`.
5. Approve the `pypi` environment deployment. The workflow publishes with PyPI trusted
   publishing; no tokens are stored.

One-time setup: a pending trusted publisher on PyPI for project `saidby`, owner `khvostpola`,
repository `saidby`, workflow `release.yml`, environment `pypi`.
