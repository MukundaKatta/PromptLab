"""Tests for PromptLab core module -- uses in-memory SQLite."""

import json

import pytest

from promptlab import Experiment, PromptLab


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def lab():
    """Create a PromptLab instance backed by an in-memory SQLite database."""
    pl = PromptLab(db_path=":memory:")
    yield pl
    pl.close()


@pytest.fixture()
def experiment_with_data(lab: PromptLab):
    """Create an experiment and populate it with trial data."""
    exp = lab.create_experiment(
        "email-tone",
        variants=[
            "Write a professional email about {topic}",
            "Write a friendly email about {topic}",
        ],
    )
    # Variant 0 scores
    for score in [0.80, 0.82, 0.78, 0.85, 0.79]:
        lab.run_trial(exp, variant=0, result_score=score)
    # Variant 1 scores (higher on average)
    for score in [0.90, 0.92, 0.88, 0.95, 0.91]:
        lab.run_trial(exp, variant=1, result_score=score)
    return exp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateExperiment:
    def test_create_and_retrieve(self, lab: PromptLab):
        exp = lab.create_experiment(
            "test-exp",
            variants=["variant A", "variant B", "variant C"],
        )
        assert isinstance(exp, Experiment)
        assert exp.name == "test-exp"
        assert exp.num_variants == 3

    def test_empty_variants_raises(self, lab: PromptLab):
        with pytest.raises(ValueError, match="at least one variant"):
            lab.create_experiment("empty", variants=[])

    def test_experiment_appears_in_history(self, lab: PromptLab):
        lab.create_experiment("hist-test", variants=["a", "b"])
        history = lab.get_history()
        assert len(history) == 1
        assert history[0]["name"] == "hist-test"
        assert history[0]["num_variants"] == 2


class TestRunTrial:
    def test_record_trial(self, lab: PromptLab):
        exp = lab.create_experiment("trial-test", variants=["x", "y"])
        trial = lab.run_trial(exp, variant=0, result_score=0.75)
        assert trial.result_score == 0.75
        assert trial.variant == 0

    def test_invalid_variant_raises(self, lab: PromptLab):
        exp = lab.create_experiment("bounds", variants=["only-one"])
        with pytest.raises(IndexError):
            lab.run_trial(exp, variant=5, result_score=0.5)

    def test_negative_variant_raises(self, lab: PromptLab):
        exp = lab.create_experiment("neg", variants=["a", "b"])
        with pytest.raises(IndexError):
            lab.run_trial(exp, variant=-1, result_score=0.5)


class TestGetResults:
    def test_results_structure(self, lab: PromptLab, experiment_with_data: Experiment):
        results = lab.get_results(experiment_with_data)
        assert results.total_trials == 10
        assert len(results.variant_stats) == 2
        # Variant 1 should have higher mean
        assert results.variant_stats[1]["mean_score"] > results.variant_stats[0]["mean_score"]

    def test_winner_is_variant_1(self, lab: PromptLab, experiment_with_data: Experiment):
        winner = lab.get_winner(experiment_with_data)
        assert winner["variant"] == 1
        assert winner["mean_score"] > 0.85


class TestStatisticalSignificance:
    def test_significance_with_data(self, lab: PromptLab, experiment_with_data: Experiment):
        sig = lab.statistical_significance(experiment_with_data)
        assert "is_significant" in sig
        assert "p_value" in sig
        assert "f_statistic" in sig
        # With clearly different means, should be significant
        assert sig["is_significant"] is True
        assert sig["p_value"] < 0.05

    def test_insufficient_data(self, lab: PromptLab):
        exp = lab.create_experiment("sparse", variants=["a", "b"])
        lab.run_trial(exp, variant=0, result_score=0.5)
        sig = lab.statistical_significance(exp)
        assert sig["is_significant"] is False
        assert sig["p_value"] == 1.0


class TestCompareVariants:
    def test_pairwise_comparison(self, lab: PromptLab, experiment_with_data: Experiment):
        comparisons = lab.compare_variants(experiment_with_data)
        assert len(comparisons) == 1  # 2 variants -> 1 pair
        pair = comparisons[0]
        assert pair["variant_a"] == 0
        assert pair["variant_b"] == 1
        assert "p_value" in pair
        assert "t_statistic" in pair


class TestExport:
    def test_export_json(self, lab: PromptLab, experiment_with_data: Experiment):
        output = lab.export(experiment_with_data, format="json")
        data = json.loads(output)
        assert data["experiment"]["name"] == "email-tone"
        assert data["experiment"]["total_trials"] == 10
        assert len(data["trials"]) == 10

    def test_export_csv(self, lab: PromptLab, experiment_with_data: Experiment):
        output = lab.export(experiment_with_data, format="csv")
        lines = [l.rstrip("\r") for l in output.strip().split("\n")]
        assert lines[0] == "id,experiment_id,variant,result_score,recorded_at"
        assert len(lines) == 11  # header + 10 trials

    def test_export_invalid_format_raises(self, lab: PromptLab, experiment_with_data: Experiment):
        with pytest.raises(ValueError, match="Unsupported export format"):
            lab.export(experiment_with_data, format="xml")
