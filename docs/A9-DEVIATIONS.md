# A9: deviations and post-registration notes

Amendment A9 was registered on 2026-11-03 (tag `a9-registered`). The registered files, the mask sets among them, are never edited after registration (`dataset/masks/RULES.md`). Anything learned or decided after that is recorded here, dated, with its reason. The results record lists every item.

## 1. 2026-11-06: Aaron's mask for `est-tone-1_burst` reflects a primed judgement

**Row.** `est-tone-1_burst`: an empty subway platform at night, the tracks running into a dark tunnel mouth, no people and no train. Aaron's set allows motion over the tunnel and the track bed (286,627 px at 1280×720, status `drawn`). The blind set marks the row `nothing-allowed`. Their overlap is 0.

**What Aaron says (6 Nov 2026).** He drew round the tunnel and tracks because a train could come out of the darkness. He thought so because he had seen a generated clip from this panel, the Gen-4.5 one shown on the front page of his portfolio site, in which a train does come out of the tunnel. That expectation came from a generated clip, not from the drawing. Nothing in the drawing is about to move, and his unprimed answer would have been "nothing can move".

**Why the mask stays as registered.** RULES.md allows only slips to be fixed, and only before registration. Redrawing because the judgement has changed is not allowed. The row was drawn as intended, so this is a change of judgement, not a slip. The registered set is analysed as it stands.

**What changes.** Nothing in the registered analysis. The results record reports this note, and gives one extra, clearly labelled sensitivity line: Test 2 recomputed with Aaron's `est-tone-1_burst` set to `nothing-allowed`. That line does not decide the verdict.

**Timing.** Written before any masked value or adherence rating exists for A9. No AARON or R7 session was stored when this was written, and `masked.py a9-run` had never been run.

**Already covered by the design.** A9 asks for Test 2 to hold under both mask sets. The blind set, drawn without having seen any clip, already treats this row as `nothing-allowed`. This note puts on record that the author-drawn set carries this kind of priming, which is the risk the blind set was there to check.

## 2. 2026-11-06: an extra, descriptive measure of mask agreement

**Question (Aaron).** The two sets look alike on the contact sheet, yet the registered IoU is low (median 0.346). Is that because a mouse-drawn edge is rougher than a computed polygon?

**What was checked.** `analysis/a9_mask_agreement.py` reads only the two mask sets. It computes IoU after both masks are widened by 8, 16 and 32 px, and the share of each set lying within 32 px of the other. No clip and no rating is involved.

**Finding.** Edge roughness explains little: the median IoU goes from 0.346 raw to 0.366, 0.384 and 0.403 at 8, 16 and 32 px. The sets mostly agree on *where* motion is allowed and disagree on *how much*. On the idle rows the blind set marks far more area: on `cu-tone-3_idle` it covers 304,590 px against Aaron's 13,571. Aaron's regions often lie wholly inside it (share within 32 px of the blind mask = 1.00 on `act-line-1_idle`, `act-tone-3_idle`, `cu-tone-3_idle` and `est-tone-3_idle`). IoU scores a small mask nested inside one twenty times larger as about 0.05, however clean its edges.

**Status.** The results record reports this alongside the registered IoU, labelled as added after registration. It changes no registered number and no test. The mask IoU decides nothing in A9: Test 2 is computed under each set separately and must hold under both. It also measures only outside each mask widened by 32 px, which already absorbs rough edges.
