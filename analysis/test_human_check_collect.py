"""The A6 analysis, refactored into functions for A11, still writes the released
human_check_results.json byte for byte. About 10 s: B = 10,000, as A6.

    python -m pytest analysis/test_human_check_collect.py
"""
import importlib.util
from pathlib import Path

HC = Path(__file__).resolve().parent / "human_check"


def load_a6():
    spec = importlib.util.spec_from_file_location("a6_collect", HC / "collect.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_run_reproduces_the_released_results_byte_for_byte(tmp_path):
    a6 = load_a6()
    out = tmp_path / "human_check_results.json"
    a6.run(out=out)
    assert out.read_bytes() == (HC / "human_check_results.json").read_bytes()


def test_the_parts_are_importable_with_the_a6_seed():
    a6 = load_a6()
    for name in ("guard_strays", "load_matrices", "analyse", "run", "krippendorff_alpha_ordinal"):
        assert callable(getattr(a6, name)), name
    assert a6.SEED == 20260813
