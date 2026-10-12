# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path
from typing import Annotated

import typer

from saidby.errors import UsageError
from saidby.i18n import _

app = typer.Typer(
    help="Measure runs against a hand-corrected reference and arbitrate differences blind.",
    no_args_is_help=True,
)


def _need_extra() -> UsageError:
    return UsageError(_("this command needs the evaluation extra: pip install 'saidby[eval]'"))


@app.command("score")
def score(
    reference: Annotated[
        Path, typer.Argument(help="Hand-corrected reference file (see docs/evaluation.md).")
    ],
    run_dir: Annotated[Path, typer.Argument(help="Output folder of the run to score.")],
    directory: Annotated[Path | None, typer.Option(help="Directory for terms and dialect")] = None,
) -> None:
    """WER, directory terms spelled correctly and, if the reference names speakers, diarization."""
    try:
        from saidby.evaluation.score import score_run

        result = score_run(reference, run_dir, directory)
    except ImportError as exc:
        raise _need_extra() from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("arbitrate-build")
def arbitrate_build(
    name: Annotated[str, typer.Argument(help="Short name of this recording, used in clip ids.")],
    label: Annotated[str, typer.Argument(help="Human-readable name shown in the page.")],
    media: Annotated[Path, typer.Argument(help="The original recording (audio or video).")],
    reference: Annotated[Path, typer.Argument(help="Hand-corrected reference of a stretch of it.")],
    candidate: Annotated[Path, typer.Argument(help="Output folder of the system being evaluated.")],
    baseline: Annotated[
        Path, typer.Argument(help="Output folder of the system to compare against.")
    ],
    out: Annotated[Path, typer.Option(help="Where to write clips and keys")] = Path("arbitration"),
    directory: Annotated[
        Path | None, typer.Option(help="Directory, to unify dialect terms before comparing.")
    ] = None,
    seed: Annotated[int, typer.Option(help="Seed for the A/B shuffle.")] = 7,
) -> None:
    """Build clips of every span where two runs disagree, with A and B shuffled."""
    from saidby.evaluation.arbitrate import build

    typer.echo(
        json.dumps(build(out, name, label, media, reference, candidate, baseline, directory, seed))
    )


@app.command("arbitrate-serve")
def arbitrate_serve(
    out: Annotated[Path, typer.Option(help="Folder written by arbitrate-build.")] = Path(
        "arbitration"
    ),
    port: Annotated[int, typer.Option(help="Local port to listen on.")] = 8765,
) -> None:
    """Serve the arbitration page on 127.0.0.1 (the clips are private audio; never publish them)."""
    from saidby.evaluation.arbitrate import serve

    server = serve(out, port)
    typer.echo(f"http://127.0.0.1:{port}/", err=False)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


@app.command("arbitrate-score")
def arbitrate_score(
    out: Annotated[Path, typer.Option(help="Folder written by arbitrate-build.")] = Path(
        "arbitration"
    ),
    directory: Annotated[
        Path | None, typer.Option(help="Directory, to unify dialect terms before scoring.")
    ] = None,
    margin: Annotated[
        float | None, typer.Option(help="Pre-registered non-inferiority margin, in WER points")
    ] = None,
) -> None:
    """Estimate the WER difference (candidate minus baseline) with a 95% bootstrap interval."""
    from saidby.evaluation.arbitrate import score

    for row in score(out, directory, margin):
        typer.echo(json.dumps(row, ensure_ascii=False))
