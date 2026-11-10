#!/usr/bin/env python3
"""Rank statistics shared by the A10, A11 and A12 analyses.

Spearman rho as the Pearson correlation of average ranks (ties shared, as scipy's
spearmanr); Monte Carlo permutation p-values, (k + 1) / (b + 1); percentile bootstrap
intervals over resampled pairs; within_strata splits rho into what lies between and
within strata (A10's panels), with p-values from permutations inside each stratum.
Resamples and permutations are vectorised and drawn from numpy.random.default_rng(seed),
fresh in every call, so each result depends only on its own inputs and seed.
"""
import numpy as np
from scipy.stats import rankdata


def pearson_rows(a, b):
    """Row-wise Pearson correlation of two 2-D arrays; nan where a row is constant."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a - a.mean(axis=1, keepdims=True)
    b = b - b.mean(axis=1, keepdims=True)
    den = np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return (a * b).sum(axis=1) / den


def spearman(x, y):
    """Spearman rho, or None with fewer than 4 pairs or a constant side (undefined, not zero)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    return float(np.corrcoef(rankdata(x), rankdata(y))[0, 1])


def perm_p(x, y, rho, seed, b, alternative="greater"):
    """(k + 1) / (b + 1): k permutations of y's ranks give a rho >= `rho` ('greater') or a
    |rho| >= |`rho`| ('two-sided')."""
    rx = rankdata(np.asarray(x, dtype=float))
    ry = rankdata(np.asarray(y, dtype=float))
    rng = np.random.default_rng(seed)
    null = pearson_rows(np.broadcast_to(rx, (b, rx.size)), rng.permuted(np.tile(ry, (b, 1)), axis=1))
    if alternative == "greater":
        k = int(np.sum(null >= rho - 1e-12))
    elif alternative == "two-sided":
        k = int(np.sum(np.abs(null) >= abs(rho) - 1e-12))
    else:
        raise ValueError(f"alternative {alternative!r}")
    return (k + 1) / (b + 1)


def bootstrap(x, y, seed, b):
    """The finite bootstrap rhos: b resamples of the pairs, rows of default_rng(seed).integers."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, x.size, size=(b, x.size))
    r = pearson_rows(rankdata(x[idx], axis=1), rankdata(y[idx], axis=1))
    return r[np.isfinite(r)]


def percentile_ci(r, lo=2.5, hi=97.5):
    """[lo, hi] percentiles (np.percentile, linear) of the bootstrap rhos, or None if there are none."""
    r = np.asarray(r, dtype=float)
    if r.size == 0:
        return None
    a, c = np.percentile(r, [lo, hi])
    return [float(a), float(c)]


def _within_ranks(v, groups):
    """Average ranks inside each stratum, centred on that stratum's mean rank."""
    out = np.zeros(v.size)
    for g in groups:
        r = rankdata(v[g])
        out[g] = r - r.mean()
    return out


def within_strata(x, y, strata, seed, b):
    """Spearman rho split into what lies between and within strata (e.g. panels).

    rho: the pooled Spearman rho (as spearman()). rho_within: the Pearson correlation of the
    within-stratum ranks centred on each stratum's mean (a pooled within-stratum Spearman;
    None when either side is constant inside every stratum, or fewer than 4 pairs). Both get
    a one-sided ('greater') Monte Carlo p, (k + 1) / (b + 1), from the same b permutations of
    y inside each stratum (strata in sorted order, each drawn from one
    numpy.random.default_rng(seed)): p_pooled_within_strata_perm asks whether the pooled rho
    exceeds what the strata alone produce; p_within asks the same of rho_within. rho_within
    pools the strata's rank covariances, so with unequal stratum sizes the larger strata
    weigh more in it (a stratum of one cell contributes nothing)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    s = np.asarray(strata)
    keys = sorted(set(s.tolist()))
    groups = [np.flatnonzero(s == k) for k in keys]
    rho = spearman(x, y)
    wx, wy = _within_ranks(x, groups), _within_ranks(y, groups)
    rho_w = None
    if x.size >= 4 and wx.any() and wy.any():
        rho_w = float(pearson_rows(wx[None, :], wy[None, :])[0])
    out = {"n": int(x.size), "strata": len(keys), "permutations": int(b), "rho": rho,
           "p_pooled_within_strata_perm": None, "rho_within": rho_w, "p_within": None}
    if rho is None and rho_w is None:
        return out
    rng = np.random.default_rng(seed)
    perm = np.tile(np.arange(x.size), (b, 1))
    for g in groups:
        if g.size > 1:
            perm[:, g] = rng.permuted(np.tile(g, (b, 1)), axis=1)
    if rho is not None:
        rx, ry = rankdata(x), rankdata(y)
        null = pearson_rows(np.broadcast_to(rx, perm.shape), ry[perm])
        out["p_pooled_within_strata_perm"] = (int(np.sum(null >= rho - 1e-12)) + 1) / (b + 1)
    if rho_w is not None:
        null_w = pearson_rows(np.broadcast_to(wx, perm.shape), wy[perm])
        out["p_within"] = (int(np.sum(null_w >= rho_w - 1e-12)) + 1) / (b + 1)
    return out
