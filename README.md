# itibar

**The transmission network behind the hadith, computed.**

A hadith is a report of something the Prophet Muhammad said or did. Each one comes with its
*isnad*: the chain of people who passed it down, from the Prophet's companions to the scholars
who wrote it into the hadith collections. Most reports survive through many chains. Classical
hadith critics judged a report partly by gathering all of its chains side by side, a step they
called *i'tibar*, to see whether it reached the books through many independent lines or hung on
a single person. They did this by hand, one report at a time.

itibar does it for the whole corpus: 715,790 narrations with 577,024 recorded chains through
49,844 narrators. For each of the 20,745 reports it merges every chain into one graph and measures it:

- **Independent routes (κ).** How many lines of transmission share no narrator at all, computed
  exactly as a minimum vertex cut (Menger's theorem). It is recomputed at each level of the
  classical narrator ratings, from everyone down to only those rated trustworthy.
- **Bottlenecks.** The narrators that every route passes through.
- **Common links.** The narrator at which a report first fans out to many students.
- **A derived grade with a receipt.** The grade the classical narrator ratings imply, with every
  step written out.

The machinery issues no verdicts of its own and uses no machine learning. Every number traces to
the source data. The whole corpus runs in about 25 seconds on a laptop, deterministically, from
open data.

### Checked against the classical scholars

The textbook example, used as such by Ibn al-Salah, is *"Actions are only by intentions"*
(إنما الأعمال بالنيات). Ibn Hajar records that, through 'Umar, it passed through exactly one person
per generation for four generations, 'Umar → 'Alqama → Muhammad b. Ibrahim al-Taymi → Yahya b. Sa'id al-Ansari
(d. 143 AH), and only then spread to many students. On its chains through 'Umar, itibar finds
those same four narrators as the bottleneck on every route (κ = 1), with at least 25 students
below Yahya. The 14 chains in the data that break the pattern are each listed with the reason.

The gold set holds 22 cases like this from the classical literature: narrow reports that classical
works trace through specific narrators, and *mutawatir* reports carried by ten or more
companions. The test suite asserts every one, the narrow cases down to the exact narrators.

### What it finds

Of the 20,282 reports with chains, 55% pass through a single person somewhere on every route
(κ = 1). 505 have ten or more fully independent routes; keeping only narrators rated *thiqa*
(trustworthy), 102 still do. Full results are [below](#results-at-a-glance-full-corpus).

**Next:** corroboration (how independent supporting routes strengthen a report) and aligning each
report's text variants against its chains. The end products are an open dataset, a paper, and a
queryable site.

## Technical summary

Corpus-scale isnad-bundle analysis. For every report (meaning group) in a 715,790-hadith corpus,
itibar overlays every chain into one graph from the Prophet to the books — the *isnad bundle* —
and computes its structure (width by generation, vertex connectivity at narrator-grade
thresholds, cut vertices, single strands, partial and common links, continuity) and a
mechanically derived grade with a receipt. The name is the classical term for this operation:
gathering all the chains of a report to see what corroborates what.

**Design rule.** The machinery computes structure and derives grades mechanically from the
classical narrator verdicts, with a receipt for every number. It never issues a verdict of its
own, uses no ML, and its own outputs never use verdict words. Source labels (صحيح, ضعيف …) are
quoted in Arabic as the source's.

The build briefs are [docs/prompts/bucket-1.md](docs/prompts/bucket-1.md) and its corrections in
[docs/prompts/pr-2.md](docs/prompts/pr-2.md); records carry `structure_version` (now 2,
`config/structure.yaml: structure.version`). Every choice the data forced that the briefs did not
settle is in [DECISIONS.md](DECISIONS.md); the source audit is
[reports/audit.md](reports/audit.md); gold-set results are [reports/gold.md](reports/gold.md).

## Reproduce from scratch

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is fetched by uv) and Graphviz (`dot`) for rendering.

```bash
make data      # download hadith-kg.db (pinned revision, sha256-checked) -> data/; Parquet + DuckDB -> data/parquet/
make audit     # reports/audit.md; regenerates the label listing in config/grades.yaml
make bundles   # out/words.parquet, out/bundles/, out/records.parquet, out/chains.parquet  (~25 s on an M-series laptop)
make gold      # reports/gold.md + gold tests
make test      # unit tests, gold set, corpus gates
make figures   # figures/fig1_kappa.*, figures/fig2_width_by_tabaka.* (+ CSV of every plotted number)
uv run itibar show 319     # a record as a readable card (Arabic text, names, numbers, receipt)
uv run itibar render 319   # figures/bundles/group_319.svg
```

`make ci` runs the whole pipeline and test suite on the committed fixture
(`tests/fixture/parquet`, 333 groups, 6.6 MB; regenerate with `make fixture`) — what GitHub
Actions runs, with no download. On the fixture's groups the records are identical to the full run.
Outputs are deterministic (identical across processes and hash seeds).

The source database is read-only input: opened `mode=ro&immutable=1`, never modified, never
committed. Revision and digest are pinned in `config/source.yaml`.

## Data and provenance

Input: [emadjumaah/hadith-kg](https://huggingface.co/datasets/emadjumaah/hadith-kg), file
`hadith-kg.db` (CC-BY-4.0), built by [emadjumaah/hadith](https://github.com/emadjumaah/hadith)
(`build_hkg.py`, `clean_hkg.py`, `finalize_hkg.py`, `DATA_REPORT.md`). **Known limitation:** the
upstream build reads a 2017 MongoDB dump of an Arabic hadith project it does not name, plus a
meaning-groups CSV; narrator resolution, meaning grouping, the narrator grades and the recorded
hadith grades are that project's, not ours. itibar redistributes only its derived outputs
(`out/`, `figures/`, `reports/`), under CC-BY-4.0 with attribution to hadith-kg
([DATA_LICENSE.md](DATA_LICENSE.md)). Code is MIT.

Tables converted (`data/parquet/`): meta, books, rawis, alems, aqwal, meaning_groups, tarafs,
hadiths, hadith_rawis, hadith_ayas, sanads, sanad_rawis, topics; plus the derived
`book_compilers`. Not converted: `group_embedding` (ML vectors) and `sqlite_stat1`.
`data/parquet/hkg.duckdb` holds a view per table for ad-hoc SQL.

## Definitions

All parameters live in `config/` (`grades.yaml`, `structure.yaml`, `source.yaml`).

### Narrator grade ordinal — `config/grades.yaml`
`rawis.rank_no` is Ibn Hajar's twelve-level scale from *Taqrib al-Tahdhib* (verified in the
audit): 1 companions, 2 `ثقة ثقة`/`حافظ`, 3 `ثقة`, 4 `صدوق`, 5 `صدوق يهم`…, 6 `مقبول`, 7 `مجهول الحال`,
8 `ضعيف`, 9 `مجهول`, 10 `متروك`, 11 `متهم بالكذب`, 12 `كذاب`/`وضاع`. Higher is weaker.

    ordinal(narrator) = 13 − rank_no        (1 ≤ rank_no ≤ 12; companions = 12 at the top)
    ordinal = 0                              (stubs, rank_no 0; the unnamed-person placeholder)

Break markers are not narrators and have no ordinal. Every observed label (499) is listed with
its count and ordinal under `labels:`. Each level also carries a **code** on the source's own
grade scale (0 صحيح, 1 حسن, 2 ضعيف, 3 شديد الضعف, 4 متهم بالوضع, 5 موضوع): levels 1–3 → 0, 4 → 1,
5–9 → 2, 10 → 3, 11 → 4, 12 → 5; unknown → 2.

**Companion** = rank_no 1, minus the labels that deny companionship (`لم تثبت له صحبة`, `له إدراك`, `لها إدراك`),
plus any narrator carrying a label in `companion.label_overrides` (`صحابي صغير`, `صحابية صغيرة`) whatever
its rank_no — 11 young companions the source puts at rank_no 3–4. Companionship only: their ordinal
still follows rank_no. Disputed companionship (`مختلف في صحبته`) follows rank_no (DECISIONS D33).

### Bundle B(g) — `itibar.bundle`
For meaning group *g*, every chain (`sanads`) of every hadith with `hadiths.group_id = g`.

| node | meaning |
|---|---|
| `P` | PROPHET, virtual source |
| `r<id>` | a narrator (`rawis.id`) |
| `m<student>\|<teacher>` | an unnamed person (`اسم مبهم`, id 1131): one node per (student, teacher) context |
| `g<sanad>.<pos>` | a break marker (`موضع إرسال` irsal, `موضع انقطاع` inqita', `موضع تعليق` ta'liq): one per chain occurrence, **never traversable** |
| `c<author_no>` | the book's compiler (`books.author_no`) |
| `b<book_id>` | a book record (sink, never cut) |

Edges run teacher → student: `sanad_rawis` pos+1 → pos; pos 0 → compiler → book; and P → the
last narrator only when it is a companion. Chains not ending in a companion are kept and flagged
**mursal**; they get no P edge. Self-loops (same narrator at adjacent positions) are dropped and
counted. Each edge stores its `(sanad_id, book_id)` occurrences and, per occurrence, the
transmission word (below). Output: `out/bundles/{nodes,edges}/bucket=<group_id // 1000>/`.

### Layers
`layer(v) = rawis.tabaka` when usable. Fallback (recorded per node in `layer_source`): when tabaka
is missing (0), or when it puts the narrator more than one layer *before every one* of his
resolved teachers (`max_backward = 1`), `layer(v) = 1 + max(layer of resolved teachers)` — depth
propagated from P at layer 0 in topological order. `tabaka` runs 0–38 (the audit shows 1–12 follow
Taqrib's layering and 13–38 extend it, about 25 years per layer).

### On path, width profile
A node is **on path** if it lies on at least one P → book route (reachable from P and co-reachable
to a book, at threshold *everyone*).

    width(L) = |{ narrators v on path : layer(v) = L }|

`width_profile` keeps every layer; `width_taqrib` keeps layers 1–12 only (`layers.taqrib_max_layer`).
Layers 13–38 are later compilers and quoters: their width counts how many books carry a report,
not how it was transmitted (DECISIONS D34).

### κ (kappa) and thresholds
Node-split max flow from P to a super-sink T joined to every book; every narrator, unnamed person
and compiler node has capacity 1; P, books and T are never cut. By Menger's theorem

    κ = min |C| over node sets C separating P from T = max number of internally vertex-disjoint P→T routes

Stored: κ, one minimum cut (`cut_set_*`) and one maximum set of disjoint routes
(`disjoint_routes_all`); the routine asserts |cut| = number of routes. `kappa_θ` is κ on the subgraph
of narrators with ordinal ≥ θ:

| column | θ (ordinal) | keeps Taqrib levels |
|---|---|---|
| `kappa_all` | 0 | everyone, including undescribed and unnamed narrators |
| `kappa_above_matruk` | 4 | 1–9 (drops matruk, muttaham, kadhdhab/wadda') |
| `kappa_saduq_up` | 9 | 1–4 |
| `kappa_thiqa_up` | 10 | 1–3 |

A compiler is kept at every threshold *in his compiler role only*: if he fails θ, his edges into
his books survive and his edges as a teacher in other chains are removed.

### κ_lower
κ_lower is the minimum of κ over three stated hypotheses — same-name clusters merged, unmerged,
and continuity-incompatible links removed. It is a lower bound under those hypotheses, not a
guarantee. Cross-name misresolution that the continuity rule does not catch remains an
unquantified upward bias on κ; `tests/gold/gold.yaml` lists the instances found.

    κ_unmerged_θ = κ_θ on the bundle with stubs dropped
    κ_merged_θ   = κ_θ with stubs dropped, each same-name cluster (same name + nickname, the 421
                   clusters) merged into one node of min ordinal, unnamed persons merged per student
    κ_nocompat_θ = κ_θ with stubs dropped and every edge the continuity rule marks incompatible removed
    κ_lower_θ    = min(κ_unmerged_θ, κ_merged_θ, κ_nocompat_θ)

`kappa_nocompat_θ` is stored as its own column; `kappa_lower_source_θ` ∈ {unmerged, merged,
nocompat} names the first hypothesis attaining the minimum in that order. Removing edges never
raises κ, so `nocompat` there means removing incompatible links lowered κ below both other graphs.
Merging is not monotone — it can splice a dead-end half-route of one person onto a half-route of
another — which is why the unmerged graph is in the minimum; `kappa_lower_splice` names thresholds
where merging raised κ (none in the current data). At *everyone*, κ_lower < κ in 2,436 groups
(nocompat in 2,432 of them, merging in 1); 1,020 groups with κ ≥ 1 have κ_lower = 0.

### κ = 0 and `kappa_zero_reason`
κ = 0 means **no unbroken companion-ending route in this data**, not no support. Every group with
κ_everyone = 0 (or no chains) gets one reason, by precedence:

| `kappa_zero_reason` | meaning | groups |
|---|---|---|
| `no_chains` | the group has no chains | 463 |
| `no_companion_end` | no chain ends in a companion (irsal marker, unnamed person, non-companion, stub) | 2,531 |
| `broken_only` | companion-ending chains exist, every one containing a break marker | 427 |
| `other` | a continuous chain exists yet no P → book route survived (gated at 0) | 0 |

Per group: `n_chains_companion_end`, `n_chains_broken` (any break marker), `n_chains_connected`
(companion end, no break marker). A route can exist without a continuous chain when chains broken
at different places cover each other (13 groups; DECISIONS D31). The audit (§9) lists the books
behind each reason and cross-tabulates reasons against the source's recorded group grade.

### Cut vertices
Narrator (or compiler) nodes on **every** P → book route: the dominators of T in the on-path graph,
ordered from P down (`cut_vertices`, and `cut_vertices_<θ>` per threshold). Non-empty iff κ = 1.

### Single strand
A narrator on path with exactly one on-path in-neighbour and one on-path out-neighbour.

### Partial common link (k), common link
A branch of *v* (an on-path out-neighbour *w*) *qualifies* if *w* is a compiler or book (the
student compiled it himself), or the sub-bundle reachable from *w* contains a narrator that is not
a single strand (compilers in their compiler role count as terminals, not as such narrators).

    PCL_k = { v : #qualifying branches(v) ≥ k }          (k = 2, 3)
    CL    = { v ∈ PCL_2 : no other PCL_2 node can reach v }   (all reported; cl_in_cycle flags ties in a cycle)

### Bypass paths
Number of P → book paths in the on-path graph that avoid every common link (DP over a topological
order; on the 322 cyclic bundles over a deterministic acyclic reduction, flagged
`paths_on_acyclic_reduction`; saturating). Zero iff the common links form a cut. `bypass_chains`
counts attested continuous chains avoiding them; `paths_total` is the unrestricted count.

### Terminus
`death_year` of each common link and each cut vertex, with `death_year_raw` beside it (ranges such
as `130 - 121` are kept raw, never parsed by us).

### Continuity (per edge u teacher → v student) — `structure.link_continuity`
    years    when death(u) and birth(v) are both known:
             compatible iff death(u) − birth(v) ≥ min_hearing_age (5), else incompatible
    tabaka   otherwise, when both tabakas are known:
             compatible iff tabaka(v) − tabaka(u) ∈ {−1, 0, 1, 2, 3, 4}, else incompatible
    unknown  otherwise
The basis is stored beside the verdict (`continuity_basis` per edge; `n_edges_incompatible_years`,
`n_edges_incompatible_tabaka` per group). −1 is a senior narrating from a junior (*riwayat al-akabir
'an al-asaghir*). The keys are `config/structure.yaml: continuity.min_hearing_age, tabaka_window`;
the brief's {0,1,2} window is reported in the audit (it flags 36% of all links, including canonical
ones — DECISIONS D9, D32). Of 3.74M chain links, 1.6% are incompatible (0.9% by tabaka, 0.7% by
years). One function serves bundle edges, the nocompat graph and the `drop_incompatible` scope.
Continuity enters only κ_nocompat (hence κ_lower), never κ itself or the derived grade.

### Transmission words and mu'an'an by a mudallis — `itibar.words`
For a chain whose narrators can be matched to the hadith's inline mentions (`hadith_rawis`, sanad
part only; *exact* for single-chain hadith, *in-order subsequence* otherwise), the word before
each narrator's mention is recorded: `word_raw` (the one or two tokens before the mention, as
written) and `word` (the last recognised transmission token in the text between the previous
mention and this one, diacritics stripped — normalization v1). The word before the **teacher's**
mention is how the student received from him, so for edge u → v:

    muanan_mudallis = has_tadlis(v) = 1 and word(before u's mention) ∈ {عن, أن, قال}

per occurrence; per edge `yes` if any occurrence qualifies, `unknown_word` if *v* is a mudallis and
no occurrence has a word. 85.8% of narrator links get a word.

### Derived grade v1 — `itibar.derive`
    chain ordinal  = min ordinal over the chain's narrators, excluding pos 0 when it is the book's compiler
    chain code     = code(chain ordinal); if the chain does not reach P through a companion or contains a
                     break marker, code = max(code, 2)                       (structure.yaml: derive.discontinuity_cap_code)
    best chain     = max chain ordinal among continuous companion-ending chains (all chains if none; flagged)
    group grade    = best chain's ordinal, Taqrib level and code
No corroboration upgrades in v1 (`derive.corroboration`, a stub for bucket 2). `receipt` is an
ordered JSON list of `{check, rule, data, result}` steps. `widest_path_ordinal` (the best threshold
with any route, which may splice chains) is stored beside the attested best chain.

### Comparisons (never overwriting a recorded value)
Per chain (`out/chains.parquet`): `agree_full` = our weakest link over the whole stored chain equals
`sanads.max_rank` (which includes pos 0); `agree_derived` = the same excluding the compiler, with
`disagreement_class`. Per group: `agree_derived_vs_group` (vs `meaning_groups.matn_no`),
`agree_derived_vs_hadith_mode` (vs the modal `hadiths.matn_no`).

### Companions
`companions` = companions narrating directly from P on an unbroken route to a book;
`companions_chain_end` = distinct companions ending any chain (comparable to the source's
`sahaba_qty`, stored beside it); `companions_upstream_def` = upstream audit's rule (label exactly
`صحابي`); `companions_on_path` = every companion on a route, including one narrating from another.

## Outputs

| file | content |
|---|---|
| `out/records.parquet` | one row per meaning group (20,745; `status = no_chains` for the 463 without chains) |
| `out/chains.parquet` | one row per chain: flags, chain grade, weakest link, max_rank comparison |
| `out/bundles/nodes`, `out/bundles/edges` | the bundle graphs, Hive-partitioned by `bucket` |
| `out/words.parquet` | transmission word per aligned (sanad, teacher pos) |
| `reports/audit.md`, `reports/gold.md` | source audit; gold-set results |
| `figures/` | fig1 (κ distribution by threshold), fig2 (width by Taqrib layer 1–12, Sahihayn vs rest; CSV keeps every layer), with CSVs |

## Gates and gold set

- **Gold set** (`tests/gold/gold.yaml`, 22 entries): 15 mutawatir topics from al-Kattani's *Nazm
  al-Mutanathir* (κ_everyone > 1 and ≥ 10 companions asserted; κ at every threshold recorded), and
  7 gharib / 'aziz / mashhur / mutaba'at cases from Ibn al-Salah, Ibn Hajar, Muslim and al-Tirmidhi,
  asserted down to the exact cut vertices (e.g. *innama al-a'mal* through 'Umar: cut vertices
  'Umar → 'Alqama → al-Taymi → Yahya b. Sa'id al-Ansari (d. 143), κ = 1, ≥ 25 students below Yahya).
  Every chain in the data that contradicts a documented structure is listed by sanad id with its
  reason; the test asserts that list is exact.
- **max_rank gate**: weakest link = `sanads.max_rank` for 100% of chains (577,020/577,020); with the
  compiler excluded as the derived grade does, 98.68%, and every difference is a chain whose compiler
  is strictly its weakest narrator (7,641) — the only class, asserted.
- **Companion band**: for the ten most-narrated groups, upstream's recount ≤ ours ≤ declared
  `sahaba_qty`; corpus-wide (declared ≥ 10) our median ratio to declared is 0.846, inside upstream's
  0.795–0.966; ours exceeds declared in 0.7% of groups.
- **κ = 0 explained**: every group with κ_everyone = 0 has a `kappa_zero_reason`, and `other`
  (a continuous chain but no route) occurs 0 times.
- Also asserted: one record per group; κ_lower = min of the three hypotheses, ≤ κ_nocompat ≤ κ, and
  nested thresholds; cut vertices iff κ = 1; bypass = 0 iff the common link is a cut vertex;
  recorded values untouched; no verdict words.

## Results at a glance (full corpus)

![κ across 20,282 meaning groups by narrator-grade threshold, and the share of groups by κ](figures/fig1_kappa.png)

20,282 groups with chains. κ_everyone: 0 in 14.6% (no unbroken companion-ending route in this
data: 2,531 groups with no companion-ending chain, 427 where every such chain is broken), 1 in
55.1%, 2–4 in 22.1%, 5–9 in 5.7%, ≥ 10 in 2.5% (505 groups); at thiqa and above, ≥ 10 in 102 groups.
κ_lower_everyone ≥ 10 in 451 groups (94 at thiqa and above); κ_lower < κ in 2,436 groups, almost all
through removed incompatible links. Derived code agrees
with the group's recorded grade in 72.3% of groups; the largest disagreement (2,573 groups: derived
code 2, recorded حسن) is the class corroboration upgrades address in bucket 2.

## Layout

    config/          grades.yaml, structure.yaml, source.yaml
    src/itibar/      data, audit, grades, load, words, bundle, flow, structure, derive, pipeline,
                     scope, gold, fixture, figures, cli
    tests/           unit (flow vs networkx, synthetic bundles), gold, gates; fixture/ (committed sample)
    reports/         audit.md, gold.md
    figures/         fig1, fig2
