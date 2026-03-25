"""Core engine for PromptLab -- experiment management, trial tracking, and analysis."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .config import Config
from .utils import (
    compute_mean,
    compute_std,
    format_comparison_table,
    format_results_table,
    one_way_anova_f_test,
    welch_t_test,
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Experiment(BaseModel):
    """Represents a prompt experiment with multiple variants."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str
    variants: list[str]
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def num_variants(self) -> int:
        return len(self.variants)


class Trial(BaseModel):
    """A single trial result within an experiment."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    experiment_id: str
    variant: int
    result_score: float
    recorded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ExperimentResults(BaseModel):
    """Aggregated results for an experiment."""

    experiment_id: str
    experiment_name: str
    variant_stats: list[dict[str, Any]]
    total_trials: int


# ---------------------------------------------------------------------------
# PromptLab -- main class
# ---------------------------------------------------------------------------


class PromptLab:
    """Prompt experimentation workspace.

    Create experiments with prompt variants, record trial scores,
    analyse results, and export data.  All state is persisted in a
    SQLite database.
    """

    def __init__(
        self,
        db_path: str | None = None,
        significance_level: float | None = None,
    ) -> None:
        cfg = Config.from_env()
        self._db_path = db_path or cfg.db_path
        self._significance_level = significance_level or cfg.significance_level
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    # -- schema ------------------------------------------------------------

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                variants    TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS trials (
                id              TEXT PRIMARY KEY,
                experiment_id   TEXT NOT NULL,
                variant         INTEGER NOT NULL,
                result_score    REAL NOT NULL,
                recorded_at     TEXT NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
            """
        )
        self._conn.commit()

    # -- public API --------------------------------------------------------

    def create_experiment(
        self, name: str, variants: list[str]
    ) -> Experiment:
        """Register a new experiment with the given prompt *variants*."""
        if not variants:
            raise ValueError("An experiment must have at least one variant.")
        exp = Experiment(name=name, variants=variants)
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO experiments (id, name, variants, created_at) VALUES (?, ?, ?, ?)",
            (exp.id, exp.name, json.dumps(exp.variants), exp.created_at),
        )
        self._conn.commit()
        return exp

    def run_trial(
        self,
        experiment: Experiment | str,
        variant: int,
        result_score: float,
    ) -> Trial:
        """Record a trial result for *variant* in *experiment*.

        Parameters
        ----------
        experiment:
            An ``Experiment`` instance or an experiment id string.
        variant:
            Zero-based index of the variant being tested.
        result_score:
            Numeric quality score for this trial (e.g. 0.0 -- 1.0).
        """
        exp_id = experiment.id if isinstance(experiment, Experiment) else experiment
        # Validate variant index
        exp_row = self._conn.execute(
            "SELECT variants FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        if exp_row is None:
            raise ValueError(f"Experiment {exp_id!r} not found.")
        num_variants = len(json.loads(exp_row["variants"]))
        if variant < 0 or variant >= num_variants:
            raise IndexError(
                f"Variant index {variant} out of range [0, {num_variants})."
            )

        trial = Trial(
            experiment_id=exp_id,
            variant=variant,
            result_score=result_score,
        )
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO trials (id, experiment_id, variant, result_score, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (trial.id, trial.experiment_id, trial.variant, trial.result_score, trial.recorded_at),
        )
        self._conn.commit()
        return trial

    def get_results(self, experiment: Experiment | str) -> ExperimentResults:
        """Return aggregated per-variant statistics for an experiment."""
        exp_id = experiment.id if isinstance(experiment, Experiment) else experiment
        exp_row = self._conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        if exp_row is None:
            raise ValueError(f"Experiment {exp_id!r} not found.")

        variants = json.loads(exp_row["variants"])
        trials = self._conn.execute(
            "SELECT variant, result_score FROM trials WHERE experiment_id = ?",
            (exp_id,),
        ).fetchall()

        # Group scores by variant
        scores: dict[int, list[float]] = {i: [] for i in range(len(variants))}
        for t in trials:
            scores[t["variant"]].append(t["result_score"])

        variant_stats: list[dict[str, Any]] = []
        for idx in range(len(variants)):
            s = scores[idx]
            variant_stats.append(
                {
                    "variant": idx,
                    "prompt": variants[idx],
                    "num_trials": len(s),
                    "mean_score": compute_mean(s),
                    "std_score": compute_std(s),
                    "min_score": min(s) if s else 0.0,
                    "max_score": max(s) if s else 0.0,
                }
            )

        return ExperimentResults(
            experiment_id=exp_id,
            experiment_name=exp_row["name"],
            variant_stats=variant_stats,
            total_trials=len(trials),
        )

    def get_winner(self, experiment: Experiment | str) -> dict[str, Any]:
        """Return the variant with the highest mean score."""
        results = self.get_results(experiment)
        if not results.variant_stats:
            raise ValueError("No variants found.")
        best = max(results.variant_stats, key=lambda v: v["mean_score"])
        return {
            "variant": best["variant"],
            "prompt": best["prompt"],
            "mean_score": best["mean_score"],
            "num_trials": best["num_trials"],
        }

    def statistical_significance(
        self, experiment: Experiment | str
    ) -> dict[str, Any]:
        """Test whether variants differ significantly (one-way ANOVA F-test).

        Returns a dict with ``is_significant``, ``p_value``, ``f_statistic``,
        and the ``significance_level`` used.
        """
        exp_id = experiment.id if isinstance(experiment, Experiment) else experiment
        exp_row = self._conn.execute(
            "SELECT variants FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        if exp_row is None:
            raise ValueError(f"Experiment {exp_id!r} not found.")

        variants = json.loads(exp_row["variants"])
        trials = self._conn.execute(
            "SELECT variant, result_score FROM trials WHERE experiment_id = ?",
            (exp_id,),
        ).fetchall()

        groups: list[list[float]] = [[] for _ in range(len(variants))]
        for t in trials:
            groups[t["variant"]].append(t["result_score"])

        # Need at least 2 groups with data
        non_empty = [g for g in groups if len(g) >= 2]
        if len(non_empty) < 2:
            return {
                "is_significant": False,
                "p_value": 1.0,
                "f_statistic": 0.0,
                "significance_level": self._significance_level,
                "note": "Not enough data for significance testing (need >= 2 trials per variant in at least 2 variants).",
            }

        f_stat, p_value = one_way_anova_f_test(non_empty)
        return {
            "is_significant": p_value < self._significance_level,
            "p_value": p_value,
            "f_statistic": f_stat,
            "significance_level": self._significance_level,
        }

    def get_history(self) -> list[dict[str, Any]]:
        """Return a summary of all experiments."""
        rows = self._conn.execute(
            "SELECT e.id, e.name, e.variants, e.created_at, "
            "COUNT(t.id) AS total_trials "
            "FROM experiments e "
            "LEFT JOIN trials t ON e.id = t.experiment_id "
            "GROUP BY e.id ORDER BY e.created_at DESC"
        ).fetchall()

        history: list[dict[str, Any]] = []
        for r in rows:
            variants = json.loads(r["variants"])
            history.append(
                {
                    "id": r["id"],
                    "name": r["name"],
                    "num_variants": len(variants),
                    "total_trials": r["total_trials"],
                    "created_at": r["created_at"],
                }
            )
        return history

    def compare_variants(
        self, experiment: Experiment | str
    ) -> list[dict[str, Any]]:
        """Pairwise Welch t-tests between all variant pairs."""
        exp_id = experiment.id if isinstance(experiment, Experiment) else experiment
        exp_row = self._conn.execute(
            "SELECT variants FROM experiments WHERE id = ?", (exp_id,)
        ).fetchone()
        if exp_row is None:
            raise ValueError(f"Experiment {exp_id!r} not found.")

        variants = json.loads(exp_row["variants"])
        trials = self._conn.execute(
            "SELECT variant, result_score FROM trials WHERE experiment_id = ?",
            (exp_id,),
        ).fetchall()

        scores: dict[int, list[float]] = {i: [] for i in range(len(variants))}
        for t in trials:
            scores[t["variant"]].append(t["result_score"])

        comparisons: list[dict[str, Any]] = []
        for i in range(len(variants)):
            for j in range(i + 1, len(variants)):
                if len(scores[i]) < 2 or len(scores[j]) < 2:
                    comparisons.append(
                        {
                            "variant_a": i,
                            "variant_b": j,
                            "t_statistic": 0.0,
                            "p_value": 1.0,
                            "is_significant": False,
                            "note": "Insufficient data.",
                        }
                    )
                    continue
                t_stat, p_val = welch_t_test(scores[i], scores[j])
                comparisons.append(
                    {
                        "variant_a": i,
                        "variant_b": j,
                        "mean_a": compute_mean(scores[i]),
                        "mean_b": compute_mean(scores[j]),
                        "t_statistic": t_stat,
                        "p_value": p_val,
                        "is_significant": p_val < self._significance_level,
                    }
                )
        return comparisons

    def export(
        self,
        experiment: Experiment | str,
        format: str = "json",
        path: str | None = None,
    ) -> str:
        """Export experiment data as JSON or CSV.

        Returns the serialised string.  If *path* is given the output
        is also written to that file.
        """
        exp_id = experiment.id if isinstance(experiment, Experiment) else experiment
        results = self.get_results(exp_id)
        trials = self._conn.execute(
            "SELECT * FROM trials WHERE experiment_id = ? ORDER BY recorded_at",
            (exp_id,),
        ).fetchall()

        if format == "json":
            payload = {
                "experiment": {
                    "id": results.experiment_id,
                    "name": results.experiment_name,
                    "total_trials": results.total_trials,
                },
                "variant_stats": results.variant_stats,
                "trials": [dict(row) for row in trials],
            }
            output = json.dumps(payload, indent=2)
        elif format == "csv":
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf,
                fieldnames=["id", "experiment_id", "variant", "result_score", "recorded_at"],
            )
            writer.writeheader()
            for row in trials:
                writer.writerow(dict(row))
            output = buf.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format!r}. Use 'json' or 'csv'.")

        if path:
            with open(path, "w") as fh:
                fh.write(output)

        return output

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> "PromptLab":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"PromptLab(db_path={self._db_path!r})"
