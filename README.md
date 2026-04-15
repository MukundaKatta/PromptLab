# PromptLab

**A/B test your prompts, with real statistics.**

```
$ promptlab new "landing-hook" -v "Build your pipeline in minutes." -v "Ship features, not tickets." -v "One tool. Every agent."
exp_8c1f0a7dffaa

$ promptlab trial exp_8c1f0a7dffaa 0 0.72
$ promptlab trial exp_8c1f0a7dffaa 1 0.91
$ promptlab trial exp_8c1f0a7dffaa 2 0.68
# ... record the rest of your trials ...

$ promptlab results exp_8c1f0a7dffaa
landing-hook  (120 trials)
 #     n     mean     std     min     max  prompt
--------------------------------------------------------------
 0    40    0.720   0.112   0.510   0.920  Build your pipeline in minutes.
 1    40    0.910   0.084   0.740   1.000  Ship features, not tickets.
 2    40    0.680   0.131   0.480   0.940  One tool. Every agent.

$ promptlab winner exp_8c1f0a7dffaa
winner: variant #1  mean=0.910  n=40
prompt: Ship features, not tickets.
```

PromptLab is a small, opinionated workspace for **running real A/B tests on
prompt variants**. Variants go in, trial scores come back, and you get
proper statistics — Welch's t-test, one-way ANOVA, mean/std/min/max per
variant — instead of eyeballing a handful of example outputs.

Everything lives in a single SQLite file, so experiments are portable,
inspectable, and easy to diff.

## Why

"This prompt feels better" is not how engineering decisions get made.
PromptLab makes prompt evaluation **reproducible**:

- **Deterministic storage.** Experiments and trials are rows in SQLite.
  Copy the `.db` file, share it, check it in — exact same state.
- **Statistical significance, not vibes.** `get_winner()` is backed by
  Welch's t-test between the top two variants; `ExperimentResults`
  exposes ANOVA F-stat across all variants.
- **No LLM dependencies at runtime.** PromptLab doesn't call any model
  — it's the bookkeeping layer. You score with whatever you like
  (human ratings, classifier, reward model, BLEU, cost-per-success)
  and hand the number to `run_trial`.

## Install

```bash
pip install -e .
# or
pip install promptlab   # once published
```

Python ≥ 3.10. One runtime dep: `pydantic`.

## Quick start

### CLI

```bash
# 1. Create an experiment
promptlab new "summary-style" \
    -v "Summarise in 3 bullets." \
    -v "Write a TL;DR in one sentence." \
    -v "Give me a structured summary."

# 2. Record scores
promptlab trial exp_8c1f0a7dffaa 0 0.81
promptlab trial exp_8c1f0a7dffaa 1 0.93
promptlab trial exp_8c1f0a7dffaa 2 0.77

# 3. Analyze
promptlab results  exp_8c1f0a7dffaa      # per-variant table
promptlab winner   exp_8c1f0a7dffaa      # best variant + mean
promptlab export   exp_8c1f0a7dffaa --format csv --out results.csv
promptlab list                            # every experiment in the store
```

### Python

```python
from promptlab import PromptLab

lab = PromptLab(db_path="experiments.db")
exp = lab.create_experiment(
    name="summary-style",
    variants=[
        "Summarise in 3 bullets.",
        "Write a TL;DR in one sentence.",
        "Give me a structured summary.",
    ],
)

# Score each variant against your eval set
for variant_idx in range(exp.num_variants):
    for sample in eval_set:
        output = your_model(exp.variants[variant_idx], sample)
        score  = your_rater(output, sample)
        lab.run_trial(exp, variant_idx, score)

results = lab.get_results(exp)
for v in results.variant_stats:
    print(f"  variant {v['variant']}: mean={v['mean_score']:.3f}  n={v['num_trials']}")

winner = lab.get_winner(exp)
print("best variant:", winner["prompt"])
```

## Storage

PromptLab writes to the path in `$PROMPTLAB_DB_PATH` (or `--db`, or
explicit constructor arg). The schema is two tables:

```sql
CREATE TABLE experiments (id TEXT PRIMARY KEY, name TEXT, variants TEXT, created_at TEXT);
CREATE TABLE trials      (id TEXT PRIMARY KEY, experiment_id TEXT, variant INT, result_score REAL, recorded_at TEXT);
```

That's it. Back it up like any SQLite file. Inspect it with `sqlite3`. Diff
it with `sqldiff`. Sync it to S3 with whatever you already use.

## When it's not the right tool

- **Multi-arm bandits / adaptive testing.** PromptLab is a fixed-design
  A/B testbed. If you need Thompson sampling or epsilon-greedy rollout,
  use a bandit library and reach for PromptLab only for the offline
  eval slice.
- **Per-prompt cost tracking.** Not built in. Record cost as a second
  score column by running parallel experiments, or open an issue if
  you want first-class cost support.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest           # runs in < 1s
ruff check .
```

## License

MIT. See [LICENSE](LICENSE) (if not present yet, same terms as our other
repos: permissive, attribution-only).
