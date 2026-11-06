"""A9 mask agreement, descriptive only (added 6 Nov 2026, after registration; see docs/A9-DEVIATIONS.md note 2).
Per row: raw IoU, IoU after dilating both masks by 8/16/32 px, and the share of each set lying within 32 px of the other.
Reads only the two mask sets; touches no clip and no rating. Run from the repo root."""
import sys, json, numpy as np
sys.path.insert(0, 'analysis'); sys.path.insert(0, '.')
import a9_eligibility as E
from scipy.ndimage import binary_dilation
from skimage.morphology import disk
A = json.load(open('dataset/masks/allowed-aaron.json'))['rows']
G = json.load(open('dataset/masks/allowed-agent.json'))['rows']
def iou(a,b):
    u=(a|b).sum(); return 1.0 if u==0 else (a&b).sum()/u
out=[]
for k in A:
    shape = E.grid_shape(A[k]['panel_px'])
    ma = E.rasterise(A[k]['allowed'], shape); mg = E.rasterise(G[k]['allowed'], shape)
    r = [k, ma.sum(), mg.sum(), iou(ma,mg)]
    for m in (8,16,32):
        se=disk(m); r.append(iou(binary_dilation(ma,se) if ma.any() else ma, binary_dilation(mg,se) if mg.any() else mg))
    # share of each set inside the other's 32px-dilated mask
    d32a = binary_dilation(ma,disk(32)) if ma.any() else ma; d32g = binary_dilation(mg,disk(32)) if mg.any() else mg
    r.append((ma & d32g).sum()/ma.sum() if ma.any() else float('nan'))
    r.append((mg & d32a).sum()/mg.sum() if mg.any() else float('nan'))
    out.append(r)
print(f"{'row':26} {'aaron_px':>9} {'blind_px':>9} {'iou':>5} {'d8':>5} {'d16':>5} {'d32':>5} {'A_in_B':>6} {'B_in_A':>6}")
for r in out: print(f"{r[0]:26} {int(r[1]):9d} {int(r[2]):9d} " + " ".join(f"{x:5.2f}" for x in r[3:7]) + f" {r[7]:6.2f} {r[8]:6.2f}")
for i,n in zip(range(3,7),('raw','d8','d16','d32')): print(n, 'median', round(float(np.median([r[i] for r in out])),3), 'mean', round(float(np.mean([r[i] for r in out])),3))
