"""Command-line interface for PromptLab.

Usage:

    promptlab new      "landing-page" -v "Hook A" -v "Hook B" -v "Hook C"
    promptlab trial    exp_abc123 1 0.87
    promptlab results  exp_abc123
    promptlab winner   exp_abc123
    promptlab export   exp_abc123 --format json --out results.json
    promptlab list

Every command works against the shared SQLite DB configured by
``PROMPTLAB_DB_PATH`` (or ``--db`` as an explicit override).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .core import PromptLab


def _lab(args: argparse.Namespace) -> PromptLab:
    return PromptLab(db_path=args.db) if args.db else PromptLab()


def _cmd_new(args: argparse.Namespace) -> int:
    if not args.variants:
        print("error: at least one -v/--variant is required", file=sys.stderr)
        return 2
    lab = _lab(args)
    exp = lab.create_experiment(args.name, args.variants)
    print(exp.id)
    return 0


def _cmd_trial(args: argparse.Namespace) -> int:
    lab = _lab(args)
    try:
        trial = lab.run_trial(args.experiment_id, args.variant, args.score)
    except (ValueError, IndexError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(trial.id)
    return 0


def _cmd_results(args: argparse.Namespace) -> int:
    lab = _lab(args)
    try:
        results = lab.get_results(args.experiment_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(results.model_dump_json(indent=2))
        return 0

    print(f"{results.experiment_name}  ({results.total_trials} trials)")
    header = f"{'#':>2}  {'n':>4}  {'mean':>7}  {'std':>7}  {'min':>6}  {'max':>6}  prompt"
    print(header)
    print("-" * len(header))
    for v in results.variant_stats:
        prompt = v["prompt"][:48] + ("…" if len(v["prompt"]) > 48 else "")
        print(
            f"{v['variant']:>2}  {v['num_trials']:>4}  "
            f"{v['mean_score']:>7.3f}  {v['std_score']:>7.3f}  "
            f"{v['min_score']:>6.3f}  {v['max_score']:>6.3f}  {prompt}"
        )
    return 0


def _cmd_winner(args: argparse.Namespace) -> int:
    lab = _lab(args)
    try:
        winner = lab.get_winner(args.experiment_id)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(winner, indent=2, default=str))
    else:
        print(f"winner: variant #{winner['variant']}  mean={winner['mean_score']:.3f}  n={winner['num_trials']}")
        print(f"prompt: {winner['prompt']}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    lab = _lab(args)
    try:
        payload = lab.export(args.experiment_id, format=args.format, path=args.out)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.out is None:
        print(payload)
    else:
        print(f"wrote {args.out}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    lab = _lab(args)
    rows = lab._conn.execute(
        "SELECT id, name, created_at, "
        "(SELECT COUNT(*) FROM trials t WHERE t.experiment_id = e.id) AS trials "
        "FROM experiments e ORDER BY created_at DESC"
    ).fetchall()
    if not rows:
        print("(no experiments)")
        return 0
    print(f"{'id':<14} {'trials':>6}  {'created':<25}  name")
    for r in rows:
        print(f"{r['id']:<14} {r['trials']:>6}  {r['created_at']:<25}  {r['name']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="promptlab",
        description="Prompt A/B testing workspace with statistical significance.",
    )
    parser.add_argument(
        "--db",
        help="SQLite path (overrides $PROMPTLAB_DB_PATH).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create an experiment with N prompt variants.")
    p_new.add_argument("name")
    p_new.add_argument(
        "-v", "--variant", dest="variants", action="append", default=[],
        help="Prompt variant (repeat for each).",
    )
    p_new.set_defaults(func=_cmd_new)

    p_trial = sub.add_parser("trial", help="Record a trial score for a variant.")
    p_trial.add_argument("experiment_id")
    p_trial.add_argument("variant", type=int)
    p_trial.add_argument("score", type=float)
    p_trial.set_defaults(func=_cmd_trial)

    p_res = sub.add_parser("results", help="Show aggregated per-variant statistics.")
    p_res.add_argument("experiment_id")
    p_res.add_argument("--json", action="store_true")
    p_res.set_defaults(func=_cmd_results)

    p_win = sub.add_parser("winner", help="Show the best-performing variant.")
    p_win.add_argument("experiment_id")
    p_win.add_argument("--json", action="store_true")
    p_win.set_defaults(func=_cmd_winner)

    p_exp = sub.add_parser("export", help="Export trials to JSON or CSV.")
    p_exp.add_argument("experiment_id")
    p_exp.add_argument("--format", choices=["json", "csv"], default="json")
    p_exp.add_argument("--out", help="Write to file instead of stdout.")
    p_exp.set_defaults(func=_cmd_export)

    p_ls = sub.add_parser("list", help="List all experiments in the store.")
    p_ls.set_defaults(func=_cmd_list)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
