itibar — PR 2: tighten the bounds, explain κ = 0, fix continuity, finish companions and layers
Paste as the first message of a session opened at the root of the `itibar` repo on `main` (after PR 1 is merged). Save this file as `docs/prompts/pr-2.md` in the PR.
Why this exists
PR 1 built the pipeline (see `docs/prompts/bucket-1.md`, `README.md`, `DECISIONS.md`). Review found four places where a number the paper will quote is either overstated, unexplained, or computed with a rule the data shows is wrong. Each is small. All four change records that bucket 2 builds on, so they ship together before bucket 2 starts.
The project rule still governs: the machinery computes structure and reports it with a receipt; it never issues a verdict and never uses "weak" or "fabricated" in outputs.
The task
Make four corrections to the bucket-1 pipeline — the κ_lower bound and its wording, a breakdown of why κ is zero, the continuity rule, and two definitional loose ends (companion labels, Taqrib-only width) — regenerate every report and figure, and keep all gates and gold tests green.
Definition of done
1. κ_lower: a third hypothesis, and honest wording
Today `kappa_lower = min(merged, unmerged)` over two identity hypotheses (same-(name, nickname) clusters merged / not merged, stubs dropped in both). The gold set shows the error that matters most is a third kind the merge cannot see: a different full name resolved to the wrong person (al-Qattan r8271 for al-Ansari r8272 in six chains of group 319; al-Bahrani r4796 for al-Qurashi r4797 in group 276; 'Umara b. 'Umayr r5885 for 'Umara b. al-Qa'qa' r5866 in group 2852). That error inflates κ.

* Add a third graph to the κ_lower minimum: incompatible links dropped — the bundle with every edge the continuity rule (as corrected in §3) marks `incompatible` removed, stubs dropped, no merging. Compute κ on it at every threshold.
* `kappa_lower_<θ>` = min over the three graphs. Add `kappa_lower_source_<θ>` ∈ {unmerged, merged, nocompat} naming which attained the minimum (ties: the first in that order), and store `kappa_nocompat_<θ>` as its own column so the paper can discuss it separately.
* Reword everywhere (`README.md`, `DECISIONS.md` D17, docstrings, `itibar show`): κ_lower is "the minimum of κ over three stated hypotheses — same-name clusters merged, unmerged, and continuity-incompatible links removed. It is a lower bound under those hypotheses, not a guarantee. Cross-name misresolution that the continuity rule does not catch remains an unquantified upward bias on κ; `tests/gold/gold.yaml` lists the instances found." Remove "bound by construction" and "guaranteed."
* Audit: a table showing, for the cross-name misresolutions documented in gold.yaml, whether the corrected year rule now flags each chain's bad link (`caught` / `not caught`, with the years or tabaka that decided it). The al-Qattan case (al-Taymi d. 120, al-Qattan b. 120) must be caught.

2. κ = 0: say why
14.6% of groups have `kappa_all = 0`. Add `kappa_zero_reason` to `records`, assigned by precedence:

1. `no_chains` — the group has no chains (today's `status = 'no_chains'`, 462 + 1 groups).
2. `no_companion_end` — no chain ends in a companion (every chain ends at an irsal marker, an unnamed person, a non-companion, or a stub).
3. `broken_only` — companion-ending chains exist but every one contains a break marker.
4. `other` — connected chains exist yet no PROPHET→book route survived. Assert in the gates that this count is 0; if it is not, find out why and document it before closing the PR.

Also add per-group counts `n_chains_companion_end`, `n_chains_broken`, `n_chains_connected`. Audit §9: counts and shares per reason; for `no_companion_end` and `broken_only`, the ten books contributing the most such groups; and a cross-table of `kappa_zero_reason` against the source's recorded group grade (`meaning_groups.matn_no`) — a sahih group with no connected chain is a data gap worth seeing. `itibar show` prints the reason when κ is zero. README states plainly that κ = 0 means "no unbroken companion-ending route in this data," not "no support."
3. Continuity: allow seniors-from-juniors, require an age of hearing
Two changes to `continuity` in `config/structure.yaml` and `structure.continuity` / `scope.link_continuity`:

* `tabaka_window: [-1, 0, 1, 2, 3, 4]`. A gap of −1 (a senior narrating from a junior, riwayat al-akabir 'an al-asaghir) is a real and accepted pattern; it is not incompatible. Gaps of −2 and below stay incompatible.
* Year rule: when both `death(teacher)` and `birth(student)` are known, compatible iff `death(teacher) − birth(student) ≥ min_hearing_age`, new config key, default 5. Below that (including negative) is incompatible. Today's `≥ 0` passes a student born the year his teacher died.
* Store the basis beside the verdict: `continuity_basis` ∈ {years, tabaka, unknown} per edge, and roll up to records as `n_edges_incompatible_years`, `n_edges_incompatible_tabaka` alongside the existing counts.
* Audit §8.5: regenerate the gap table and add a years-rule table (links with both years known; how many fall below 5; the distribution of `death − birth` in 5-year bins). Keep the comparison against the brief's original `{0,1,2}` window.

Gold tests must still pass unchanged — the deviation lists are keyed on narrators, not continuity — but re-run `make gold` and confirm; if any scoped expectation moves, stop and report rather than editing the expectation.
4. Two definitional loose ends

* Companion label overrides. `صحابي صغير` and `صحابية صغيرة` appear at `rank_no` 3 and 4 for nine narrators who today do not connect to PROPHET. Add `grades.yaml: companion.label_overrides` — labels that make a narrator a companion regardless of `rank_no` — containing exactly those two labels. Leave `مختلف في صحبته` (disputed companionship) to follow `rank_no` as now, and record that choice in DECISIONS. Re-run the companion band gate.
* Taqrib-only width. Add `width_taqrib` (layers 1–12 only) beside the full profile; layers 13–38 are later compilers and quoters and measure how many books carry the report, not how it was transmitted. Regenerate `fig2` restricted to layers 1–12 with the caption stating that 13+ are omitted for that reason; keep the CSV with all layers.
* One gold note. In `la-yuminu-ahadukum`, the data's second student of Qatada is Sa'id b. Bashir (r3306) where Ibn Hajar names Sa'id b. Abi 'Aruba. Add it to that entry's `notes` as a `candidate_misresolution` for the name-resolution work in a later bucket. No assertion change.

Housekeeping

* `config/structure.yaml`: add `structure.version: 2`; records carry it.
* New DECISIONS entries (D30–D34) for each change above, with the alternative not taken.
* Regenerate `reports/audit.md`, `reports/gold.md`, both figures and their CSVs, the fixture, and the README headline numbers. All 106+ tests pass locally on the full corpus and in CI on the fixture; the new `other = 0` gate is among them.
* Open a PR against `main`. Subagents are fine for reading; use cheaper models for them.

What's on the shelf

* `src/itibar/structure.py`: `lower_succ` (the two κ_lower graphs), `continuity`, `analyse`; `src/itibar/scope.py`: `link_continuity`, `chain_has_incompatible` (already implements "drop chains with an incompatible link" for scopes — the nocompat graph should drop edges, not chains, and share one continuity function with it).
* `src/itibar/bundle.py`: `ChainInfo.ends_companion`, `.gaps`, `.connected` — everything §2 needs is already computed per chain.
* `src/itibar/load.py`: `Narrators.is_companion` (built from `rank_no` and the denial labels) — the override list plugs in there.
* `src/itibar/audit.py`, `figures.py`, `pipeline.py`, `cli.py`: extend; do not restructure.
* `reports/audit.md` §6.1 and `tests/gold/gold.yaml`: the documented misresolutions for the §1 audit table.

Out of scope
Everything in bucket 2: text alignment and congruence, corroboration rules, the classical mutawatir lists, narrator-level statistics, any name-resolution model, the site.
How to work
The gates, the gold tests and the regenerated audit are the arbiter. Where something here under-specifies a case the data presents, choose, record it in DECISIONS with the alternative, and keep going.
