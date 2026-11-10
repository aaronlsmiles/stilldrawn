"""Tests for analysis/rank_stats.py (shared by A10, A11 and A12). Synthetic data only.

    python -m pytest analysis/test_rank_stats.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import rankdata, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rank_stats as rs  # noqa: E402


def test_spearman_matches_scipy_with_ties():
    rng = np.random.default_rng(1)
    x = rng.integers(0, 5, 40).astype(float)
    y = x + rng.normal(0, 2, 40)
    assert rs.spearman(x, y) == pytest.approx(spearmanr(x, y).statistic, abs=1e-12)


def test_spearman_is_undefined_for_tiny_or_constant_samples():
    assert rs.spearman([1, 2, 3], [3, 2, 1]) is None
    assert rs.spearman([1, 1, 1, 1], [1, 2, 3, 4]) is None


def test_permutation_p_for_a_perfect_order_is_its_floor():
    x = np.arange(20.0)
    assert rs.perm_p(x, x, 1.0, seed=1, b=999) == pytest.approx(1 / 1000)
    assert rs.perm_p(x, -x, -1.0, seed=1, b=999) == pytest.approx(1.0)
    assert rs.perm_p(x, -x, -1.0, seed=1, b=999, alternative="two-sided") == pytest.approx(1 / 1000)


def test_permutation_p_is_roughly_uniform_under_the_null():
    rng = np.random.default_rng(5)
    ps = []
    for s in range(200):
        x, y = rng.random(30), rng.random(30)
        ps.append(rs.perm_p(x, y, rs.spearman(x, y), seed=s, b=199))
    assert 0.35 < float(np.mean(ps)) < 0.65


def test_bootstrap_is_deterministic_and_finite():
    rng = np.random.default_rng(2)
    x = rng.random(25)
    y = x + rng.normal(0, 0.3, 25)
    a, b = rs.bootstrap(x, y, seed=7, b=500), rs.bootstrap(x, y, seed=7, b=500)
    assert np.array_equal(a, b) and np.isfinite(a).all() and a.size <= 500
    lo, hi = rs.percentile_ci(a)
    assert lo < rs.spearman(x, y) < hi


def _strata(n_panels, k):
    return np.repeat([f"p{i:02d}" for i in range(n_panels)], k)


def test_within_strata_matches_a_hand_computation():
    rng = np.random.default_rng(3)
    s = _strata(12, 4)
    x, y = rng.random(48), rng.random(48)
    out = rs.within_strata(x, y, s, seed=1, b=99)
    wx = np.concatenate([rankdata(x[s == g]) - 2.5 for g in sorted(set(s))])
    wy = np.concatenate([rankdata(y[s == g]) - 2.5 for g in sorted(set(s))])
    assert out["rho_within"] == pytest.approx(float(np.corrcoef(wx, wy)[0, 1]), abs=1e-12)
    assert out["rho"] == pytest.approx(rs.spearman(x, y), abs=1e-12)
    assert out["n"] == 48 and out["strata"] == 12 and out["permutations"] == 99


def test_within_strata_separates_between_from_within():
    s = _strata(12, 4)
    level = np.tile(np.arange(4.0), 12)
    panel = np.repeat(np.arange(12.0), 4)
    x = 10 * panel + level                         # motion: panel and level
    y = panel + 0.01 * (3 - level)                 # drift: the panel only (slightly against level)
    out = rs.within_strata(x, y, s, seed=1, b=999)
    assert out["rho"] > 0.9 and out["rho_within"] == pytest.approx(-1.0)
    assert out["p_pooled_within_strata_perm"] > 0.5 and out["p_within"] == pytest.approx(1.0)
    y2 = panel + 0.01 * level                      # drift rises with level inside every panel
    out2 = rs.within_strata(x, y2, s, seed=1, b=999)
    assert out2["rho_within"] == pytest.approx(1.0) and out2["p_within"] == pytest.approx(1 / 1000)


def test_within_strata_is_deterministic_and_undefined_when_flat():
    rng = np.random.default_rng(4)
    s = _strata(6, 4)
    x, y = rng.random(24), rng.random(24)
    assert rs.within_strata(x, y, s, seed=9, b=200) == rs.within_strata(x, y, s, seed=9, b=200)
    flat = np.repeat(np.arange(6.0), 4)            # constant inside every stratum
    out = rs.within_strata(x, flat, s, seed=9, b=200)
    assert out["rho_within"] is None and out["p_within"] is None and out["rho"] is not None
