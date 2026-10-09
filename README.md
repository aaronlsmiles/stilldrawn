# StillDrawn

**When an image-to-video model animates an inked comic or manga panel, does the
result still look drawn?** StillDrawn is a benchmark for that question: a
controlled dataset of inked panels, five automatic line-stability metrics, a
pre-registered study of five video engines, a failure-mode taxonomy, and a human
check of the metrics.

- **Paper:** *StillDrawn: Measuring the Stability of Inked Line Art under
  Image-to-Video Generation*, Aaron Smiles, arXiv preprint, 2026 (the arXiv
  identifier is listed on the Zenodo record and in the GitHub repository).
- **Data archive:** Zenodo, [doi:10.5281/zenodo.23072784](https://doi.org/10.5281/zenodo.23072784) (version 1.0.0; versioned, and this repository mirrors it).
- **Name:** developed under the working name InkBench; renamed before release
  after a name collision. Historical records in `docs/` and `LEDGER.md` keep the
  old name.

## What is here

| Path | Contents |
|---|---|
| `dataset/` | 29 benchmark panels + 5 ground-series variants, their line-art layers and recipes, and the datasheet (`dataset/DATASHEET.md`, **start here**) |
| `runs/` | All 373 generated clips, the per-clip manifest, and metric outputs (`runs/README.md` explains the manifest). **The GitHub repository omits the 1.7 GB of clips; they are in the Zenodo archive** (`stilldrawn-clips-*.zip`), which unpacks into the same paths |
| `metrics/` | The stability metric suite (`inkstab.py`) and the motion channel (`motion.py`) |
| `harness/` | The generation code (`harness/README.md`) |
| `analysis/` | Scripts that regenerate every table and figure, their outputs, the frame strips behind the taxonomy, and the human check (pseudonymised ratings) |
| `docs/` | The frozen pre-registration and its amendments, the failure-mode taxonomy, the pre-generation terms review, the redaction record, known errata, and the freeze provenance |
| `paper/` | Manuscript source |
| `LEDGER.md` | The append-only budget ledger: one row per paid batch, logged before the next batch was submitted (see `docs/ERRATA.md` for its running-total correction) |
| `NOTICE-PROVIDERS.md` | Which items came from commercial services, and what their terms say |

## Reproduce the tables and figures

The analysis needs Python 3.10+ with `numpy`, `scipy` and `matplotlib`:

```bash
python3 analysis/build_table.py      # per-cell table from runs/metrics/
python3 analysis/prereg_stats.py     # the frozen §8 test
python3 analysis/figures.py          # supplementary figures fig1–fig5
```

`repeat_stability.py`, `ground_response.py`, `motion_confound.py` and
`motion_figure.py` produce the repeat, ground-series and motion analyses in the
same way. The paper's two figures come from `panel_grid.py` (Figure 1, every
panel, drawn from `dataset/panels/`) and `motion_figure.py` (Figure 2).

Re-scoring clips with `metrics/inkstab.py` additionally needs PyTorch (DINOv2 via
`torch.hub`), `imageio` and the AnimeLineArt weights; see `metrics/README.md`,
which also records the DINOv2 checkpoint hash.

## Licences

| Component | Licence |
|---|---|
| Data and documents (`dataset/`, `runs/`, `analysis/out/`, the human-check tables, `docs/`, `LEDGER.md`) | CC BY 4.0 (`LICENSE-DATA`) |
| Code (`metrics/`, `harness/`, `analysis/*.py`, `tools/`, `zenodo/pack.sh`) | MIT (`LICENSE-CODE`) |
| Paper (`paper/`) | CC BY 4.0 (the licence of the arXiv posting) |

Some items were generated through commercial services whose terms restrict
using outputs to build competing products. **Please read `NOTICE-PROVIDERS.md`
before reusing the clips**, and do not re-encode the signed clips.

## Citing

See `CITATION.cff` (the GitHub repository's copy adds the arXiv identifier), or
cite the paper as: Aaron Smiles, *StillDrawn: Measuring the Stability of Inked
Line Art under Image-to-Video Generation*, arXiv preprint, 2026; and the data as:
doi:10.5281/zenodo.23072784.
