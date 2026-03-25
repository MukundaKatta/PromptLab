"""Statistics helpers, significance testing, and result formatting for PromptLab."""

from __future__ import annotations

import math
from typing import Any


# ---------------------------------------------------------------------------
# Basic statistics
# ---------------------------------------------------------------------------


def compute_mean(values: list[float]) -> float:
    """Return the arithmetic mean, or 0.0 for an empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def compute_variance(values: list[float], ddof: int = 1) -> float:
    """Return the sample variance with *ddof* degrees-of-freedom correction.

    Uses Bessel's correction (ddof=1) by default.
    """
    n = len(values)
    if n <= ddof:
        return 0.0
    mean = compute_mean(values)
    return sum((x - mean) ** 2 for x in values) / (n - ddof)


def compute_std(values: list[float], ddof: int = 1) -> float:
    """Return the sample standard deviation."""
    return math.sqrt(compute_variance(values, ddof=ddof))


# ---------------------------------------------------------------------------
# Significance testing  (pure-Python, no scipy needed)
# ---------------------------------------------------------------------------


def _beta_incomplete_cf(a: float, b: float, x: float) -> float:
    """Evaluate the regularised incomplete beta function I_x(a, b)
    using the Lentz continued-fraction algorithm.

    This is needed to convert F / t statistics into p-values without scipy.
    """
    max_iter = 200
    eps = 1e-14

    # Front factor
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - lbeta) / a

    # Lentz algorithm for the continued fraction
    f = 1.0
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < eps:
        d = eps
    d = 1.0 / d
    f = d

    for m in range(1, max_iter + 1):
        # Even step
        m2 = 2 * m
        numerator = m * (b - m) * x / ((a + m2 - 1) * (a + m2))
        d = 1.0 + numerator * d
        if abs(d) < eps:
            d = eps
        d = 1.0 / d
        c = 1.0 + numerator / c
        if abs(c) < eps:
            c = eps
        f *= c * d

        # Odd step
        numerator = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1))
        d = 1.0 + numerator * d
        if abs(d) < eps:
            d = eps
        d = 1.0 / d
        c = 1.0 + numerator / c
        if abs(c) < eps:
            c = eps
        delta = c * d
        f *= delta
        if abs(delta - 1.0) < eps:
            break

    return front * f


def _regularised_beta(x: float, a: float, b: float) -> float:
    """Regularised incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if x < (a + 1.0) / (a + b + 2.0):
        return _beta_incomplete_cf(a, b, x)
    return 1.0 - _beta_incomplete_cf(b, a, 1.0 - x)


def _f_cdf(f_val: float, dfn: float, dfd: float) -> float:
    """CDF of the F-distribution at *f_val*."""
    if f_val <= 0:
        return 0.0
    x = dfn * f_val / (dfn * f_val + dfd)
    return _regularised_beta(x, dfn / 2.0, dfd / 2.0)


def _t_cdf(t_val: float, df: float) -> float:
    """Two-tailed CDF of the t-distribution -- returns p-value."""
    x = df / (df + t_val ** 2)
    p = _regularised_beta(x, df / 2.0, 0.5)
    return p  # this is the two-tailed p-value


def welch_t_test(
    group_a: list[float], group_b: list[float]
) -> tuple[float, float]:
    """Perform Welch's t-test (two-tailed) between two groups.

    Returns ``(t_statistic, p_value)``.
    """
    n_a, n_b = len(group_a), len(group_b)
    if n_a < 2 or n_b < 2:
        return 0.0, 1.0

    mean_a = compute_mean(group_a)
    mean_b = compute_mean(group_b)
    var_a = compute_variance(group_a)
    var_b = compute_variance(group_b)

    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se == 0:
        return 0.0, 1.0

    t_stat = (mean_a - mean_b) / se

    # Welch-Satterthwaite degrees of freedom
    num = (var_a / n_a + var_b / n_b) ** 2
    denom = (var_a / n_a) ** 2 / (n_a - 1) + (var_b / n_b) ** 2 / (n_b - 1)
    if denom == 0:
        return 0.0, 1.0
    df = num / denom

    p_value = _t_cdf(t_stat, df)
    return round(t_stat, 6), round(p_value, 6)


def one_way_anova_f_test(
    groups: list[list[float]],
) -> tuple[float, float]:
    """One-way ANOVA F-test across multiple groups.

    Returns ``(f_statistic, p_value)``.
    """
    k = len(groups)
    if k < 2:
        return 0.0, 1.0

    ns = [len(g) for g in groups]
    n_total = sum(ns)
    if n_total <= k:
        return 0.0, 1.0

    grand_mean = sum(x for g in groups for x in g) / n_total

    # Between-group sum of squares
    ss_between = sum(n * (compute_mean(g) - grand_mean) ** 2 for g, n in zip(groups, ns))
    # Within-group sum of squares
    ss_within = sum(
        sum((x - compute_mean(g)) ** 2 for x in g) for g in groups
    )

    df_between = k - 1
    df_within = n_total - k

    if df_within <= 0 or ss_within == 0:
        return 0.0, 1.0

    ms_between = ss_between / df_between
    ms_within = ss_within / df_within
    f_stat = ms_between / ms_within

    p_value = 1.0 - _f_cdf(f_stat, float(df_between), float(df_within))
    return round(f_stat, 6), round(p_value, 6)


# ---------------------------------------------------------------------------
# Result formatting
# ---------------------------------------------------------------------------


def format_results_table(variant_stats: list[dict[str, Any]]) -> str:
    """Format variant statistics as an ASCII table."""
    header = f"{'Variant':>8} | {'Trials':>7} | {'Mean':>8} | {'Std':>8} | {'Min':>8} | {'Max':>8}"
    sep = "-" * len(header)
    lines = [header, sep]
    for vs in variant_stats:
        lines.append(
            f"{vs['variant']:>8} | {vs['num_trials']:>7} | "
            f"{vs['mean_score']:>8.4f} | {vs['std_score']:>8.4f} | "
            f"{vs['min_score']:>8.4f} | {vs['max_score']:>8.4f}"
        )
    return "\n".join(lines)


def format_comparison_table(comparisons: list[dict[str, Any]]) -> str:
    """Format pairwise comparison results as an ASCII table."""
    header = f"{'Pair':>10} | {'t-stat':>10} | {'p-value':>10} | {'Significant':>12}"
    sep = "-" * len(header)
    lines = [header, sep]
    for c in comparisons:
        pair = f"{c['variant_a']} vs {c['variant_b']}"
        sig = "YES" if c["is_significant"] else "no"
        lines.append(
            f"{pair:>10} | {c['t_statistic']:>10.4f} | "
            f"{c['p_value']:>10.6f} | {sig:>12}"
        )
    return "\n".join(lines)
