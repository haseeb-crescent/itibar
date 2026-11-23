# itibar

**Computing the transmission network behind the hadith.**

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

The gold set holds 22 structural cases like this from the classical literature: narrow reports that
classical works trace through specific narrators, and *mutawatir* reports carried by ten or more
companions; 22 more test the corroborated grade, the number class, the classical lists, the rules
on tadlīs, the unnamed companion and narrators whose standing depends on the link. The test suite asserts every one, the narrow cases down to the exact narrators.

### What it finds

Of the 20,282 reports with chains, 55% pass through a single person somewhere on every route
(κ = 1). 511 have ten or more fully independent routes; keeping only narrators rated *thiqa*
(trustworthy), 108 still do. Full results are [below](#results-at-a-glance-full-corpus).

Corroboration, the classical number class and the corpus checks of the mutawātir lists and the common
links are in; PR 5 made the corroborated grade follow the classical rules more exactly (attested
witnesses, Ibn Hajar's tiers of tadlīs, shawāhid filed as other reports, every weak narrator
covered); PR 6 reads an unnamed companion («a man of the Prophet's companions») as a companion, applies
narrators' standing on the link where the books make it conditional (a teacher, a student, the time of
hearing), and decomposes the remaining disagreement with the recorded grades by cause
([reports/residue.md](reports/residue.md)). **Next:** aligning each report's text variants against its chains. The end products are
an open dataset, a paper, and a queryable site.

## Technical summary

Corpus-scale isnad-bundle analysis. For every report (meaning group) in a 715,790-hadith corpus,
itibar overlays every chain into one graph from the Prophet to the books — the *isnad bundle* —
and computes its structure (width by generation, vertex connectivity at narrator-grade
thresholds, cut vertices, single strands, partial and common links, continuity), a mechanically
derived grade with a receipt — the best single chain (v1) and the classical ladder with
corroboration under two rulesets (v2) — the classical number class, Ibn Hajar's indicators
(qarāʾin), and corpus-wide checks of the classical mutawātir lists, the common links and the
chapters of the law. The name is the classical term for this operation: gathering all the chains
of a report to see what corroborates what.

**Design rule.** The machinery computes structure and derives grades mechanically from the
classical narrator verdicts, with a receipt for every number. It never issues a verdict of its
own, uses no ML, and its own outputs never use verdict words. Source labels (صحيح, ضعيف …) are
quoted in Arabic as the source's. Where the tradition has two readings, both are implemented as
selectable rulesets and both are reported. Knowledge yield (certainty vs probability) is not
computed: the qarāʾin are reported as flags and the conclusion is left to the reader.

The build briefs are [docs/prompts/bucket-1.md](docs/prompts/bucket-1.md), its corrections in
[docs/prompts/pr-2.md](docs/prompts/pr-2.md), [docs/prompts/bucket-2.md](docs/prompts/bucket-2.md), its
corrections in [docs/prompts/pr-5.md](docs/prompts/pr-5.md), and [docs/prompts/pr-6.md](docs/prompts/pr-6.md) (the
unnamed companion, conditional narrators, the residue); records carry `structure_version` (now 5) and
`derive_version` (now 4), both in `config/structure.yaml`. Every choice the data or the sources forced that the briefs did not settle
is in [DECISIONS.md](DECISIONS.md); the source audit is [reports/audit.md](reports/audit.md);
gold-set results are [reports/gold.md](reports/gold.md); the disagreement with the recorded grades, tagged by
mechanical cause, is [reports/residue.md](reports/residue.md); the bucket-2 reports are
[reports/lists.md](reports/lists.md), [reports/common_links.md](reports/common_links.md),
[reports/chapters.md](reports/chapters.md) and [reports/pools/](reports/pools/); the reading behind the
shāhid overlap floor is [reports/shahid_inspection.md](reports/shahid_inspection.md).

## Reproduce from scratch

Requires [uv](https://docs.astral.sh/uv/) (Python 3.12 is fetched by uv) and Graphviz (`dot`) for rendering.

```bash
make data      # download hadith-kg.db (pinned revision, sha256-checked) -> data/; Parquet + DuckDB -> data/parquet/
make audit     # reports/audit.md; regenerates the label listing in config/grades.yaml
make bundles   # out/words.parquet, out/matn_*.parquet, out/bundles/, out/records.parquet, out/chains.parquet (~2 min)
make stages    # out/stages/: the PR 5 and PR 6 changes applied cumulatively, for audit §11.1 (~15 min)
make narrators # out/narrators.parquet, reports/common_links.md, figures/fig4_cl_death_years.*
make lists     # lists/*.yaml from lists/source/, lists/candidates.csv, lists/confirmed.csv, reports/lists.md, fig3
make mudallisin  # lists/mudallisin.yaml, lists/mudallisin_candidates.csv, lists/mudallisin_confirmed.csv
make conditional # lists/conditional.yaml, lists/conditional_candidates.csv, lists/conditional_confirmed.csv (PR 6)
make chapters  # reports/chapters.md, figures/fig5_chapter_census.*
make pools     # reports/pools/mahdi.*, reports/pools/dajjal.* (the two topic-subtree case studies)
make residue   # reports/residue.md, figures/fig6_residue.* (PR 6)
make gold      # reports/gold.md + gold tests
make test      # unit tests, gold set, corpus gates
make figures   # figures/fig1_kappa.*, figures/fig2_width_by_tabaka.* (+ CSV of every plotted number)
uv run itibar show 319     # a record as a readable card (Arabic text, names, numbers, receipts v1 and v2)
uv run itibar render 319   # figures/bundles/group_319.svg
uv run itibar pool --topic 28661          # pooled bundle: --groups g1 g2 …, --topic <topics.id>, --entry kattani:2
```

`make ci` runs the whole pipeline and test suite on the committed fixture
(`tests/fixture/parquet`, 351 groups with the topic nodes above them and the full corpus's matn idf, 7.1 MB; regenerate with
`make fixture`) — what GitHub Actions runs, with no download. `make lists-fetch` re-downloads the
al-Kattānī text from Shamela's public read-only MCP server (`https://mcp.shamela.ws`); its output,
`lists/source/kattani_7016.jsonl`, is committed so `make lists` needs no network; likewise `make
mudallisin-fetch` (Ibn Hajar's *Ṭabaqāt al-Mudallisīn*, `lists/source/mudallisin_1186.jsonl`) and `make
provenance-fetch` (the Taqrīb sample, `lists/source/taqrib_sample.jsonl`). `make book-compilers` recomputes the
derived `book_compilers` table after a config change. `make shahid-inspection` regenerates
`reports/shahid_inspection.md` from the committed labels. On the fixture's groups the records are identical to the full run, except where a v2 grade rests on a
witness from a sibling group the fixture does not carry — since PR 6 only the `siblings` variants, on 12 of its 347 groups with chains (it carries the siblings of the gold entries that
assert one, and the full corpus's idf for its matns; DECISIONS D58).
Outputs are deterministic (identical across processes and hash seeds).

The source database is read-only input: opened `mode=ro&immutable=1`, never modified, never
committed. Revision and digest are pinned in `config/source.yaml`.

## Data and provenance

Input: [emadjumaah/hadith-kg](https://huggingface.co/datasets/emadjumaah/hadith-kg), file
`hadith-kg.db` (CC-BY-4.0), built by [emadjumaah/hadith](https://github.com/emadjumaah/hadith)
(`build_hkg.py`, `clean_hkg.py`, `finalize_hkg.py`, `DATA_REPORT.md`). **Known limitation:** the
upstream build reads a 2017 MongoDB dump of an Arabic hadith project it does not name, plus a
meaning-groups CSV; narrator resolution, meaning grouping, the narrator grades and the recorded
hadith grades are that project's, not ours.

**Whose verdicts the narrator labels are** (PR 5, audit §11.7). A sample of 40 narrators of
al-Bukhārī or Muslim, checked against Shamela's *Taqrīb al-Tahdhīb* and *Taḥrīr Taqrīb al-Tahdhīb*
(Bashshār ʿAwwād Maʿrūf and Shuʿayb al-Arnaʾūṭ, 1997, which reprints each Taqrīb entry and adds its own
verdict after «بل:»), 29 of them read whole in both: where Taḥrīr revises Ibn Hajar the label is
Taḥrīr's revision (7 of 7; e.g. Muḥammad b. ʿAmr b. ʿAlqama, Taqrīb «محمد ابن عمرو ابن علقمة ابن وقاص الليثي المدني صدوق له أوهام», p. 499,
[8609/425](https://shamela.ws/book/8609/425), Taḥrīr «بل: صدوقٌ حسن الحديث، كما قال الذهبيُّ», 3/299,
[127715/1173](https://shamela.ws/book/127715/1173)); where it does not, labels other than the ṣadūq
level reproduce Ibn Hajar's wording (12 of 13); and the level-4 label «صدوق حسن الحديث» (5,649
narrators) is Taḥrīr's formula, written also where Taḥrīr kept Ibn Hajar's plain «صدوق» (5) or a
qualified «صدوق» (2), and twice for a verdict of another level («ثقة ورمي بالإرجاء», «لا بأس به»).
So for the Six Books' narrators the labels are **Taḥrīr al-Taqrīb's reading, normalized by the source's
editors** (not Ibn Hajar's Taqrīb as such); for the rest — the source grades 49,844 narrators, the
Taqrīb some 8,800 — they are **the source's own editors' verdicts**. No reliable per-narrator Taqrīb
membership test exists here (name matching only), so `in_taqrib` is not stored (D65). itibar redistributes only its derived outputs
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
**mursal**; they get no P edge. **Book roles** (per chain): the book's compiler at pos 0 — or its
**book transmitter** at pos 0 and, after him, the compiler at pos 1 (D62) — is exempt from grade
thresholds on his edges into the book and excluded from the chain grade; his other occurrences are
ordinary narrator occurrences. Self-loops (same narrator at adjacent positions) are dropped and
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
where merging raised κ (none in the current data). At *everyone*, κ_lower < κ in 2,447 groups
(nocompat in 2,443 of them, merging in 1); 1,022 groups with κ ≥ 1 have κ_lower = 0.

### κ = 0 and `kappa_zero_reason`
κ = 0 means **no unbroken companion-ending route in this data**, not no support. Every group with
κ_everyone = 0 (or no chains) gets one reason, by precedence:

| `kappa_zero_reason` | meaning | groups |
|---|---|---|
| `no_chains` | the group has no chains | 463 |
| `no_companion_end` | no chain ends in a companion (irsal marker, unnamed person not designated a companion, non-companion, stub) | 2,448 |
| `broken_only` | companion-ending chains exist, every one containing a break marker | 426 |
| `other` | a continuous chain exists yet no P → book route survived (gated at 0) | 0 |

Per group: `n_chains_companion_end`, `n_chains_broken` (any break marker), `n_chains_connected`
(companion end, no break marker). A route can exist without a continuous chain when chains broken
at different places cover each other (13 groups; DECISIONS D31). The audit (§9) lists the books
behind each reason and cross-tabulates reasons against the source's recorded group grade.

### Cut vertices
Narrator (or compiler) nodes on **every** P → book route: the dominators of T in the on-path graph,
ordered from P down (`cut_vertices`, and `cut_vertices_<θ>` per threshold). Non-empty iff κ = 1.

### Single strand
A narrator on path with a narrator-role occurrence, exactly one on-path in-neighbour through his
narrator-role occurrences, and exactly one on-path out-neighbour (his edge into his own book counts as
one). A narrator present only as compiler or book transmitter is neither a single strand nor a
branching point.

### Partial common link (k), common link
Compiler roles are per edge (structure version 4, D61). A branch of *v* (an on-path out-neighbour *w*)
*qualifies* if *w* is a compiler or book node, or *w* compiled (or transmitted) the report from *v* in
that occurrence (`role_in`), or the sub-bundle reachable from *w* contains a narrator with a narrator
role that is not a single strand.

    PCL_k = { v : #qualifying branches(v) ≥ k }          (k = 2, 3)
    CL    = { v ∈ PCL_2 : no other PCL_2 node can reach v }   (all reported; cl_in_cycle flags ties in a cycle)

So Mālik with the *Muwaṭṭaʾ* and one student who carries the report into another book has two
qualifying branches. Structure version 3 made a compiler's whole node terminal (D14, D51).

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
    chain ordinal  = min ordinal over the chain's narrators, excluding the positions in a book role (the
                     compiler at pos 0; or the book transmitter at pos 0 and the compiler at pos 1)
    chain code     = code(chain ordinal); if the chain does not reach P through a companion or contains a
                     break marker, code = max(code, 2)                       (structure.yaml: derive.discontinuity_cap_code)
    best chain     = max chain ordinal among continuous companion-ending chains (all chains if none; flagged)
    group grade    = best chain's ordinal, Taqrib level and code
v1 ignores corroboration; derived grade v2 (below) applies it and keeps every v1 column. `receipt` is an
ordered JSON list of `{check, rule, data, result}` steps. `widest_path_ordinal` (the best threshold
with any route, which may splice chains) is stored beside the attested best chain.

### Comparisons (never overwriting a recorded value)
Per chain (`out/chains.parquet`): `agree_full` = our weakest link over the whole stored chain equals
`sanads.max_rank` (which includes pos 0); `agree_derived` = the same excluding the book-role positions, with
`disagreement_class` (`compiler_strictly_weakest`, `book_role_strictly_weakest`). Per group: `agree_derived_vs_group` (vs `meaning_groups.matn_no`),
`agree_derived_vs_hadith_mode` (vs the modal `hadiths.matn_no`).

### Companions
`companions` = companions narrating directly from P on an unbroken route to a book;
`companions_chain_end` = distinct companions ending any chain (comparable to the source's
`sahaba_qty`, stored beside it); `companions_upstream_def` = upstream audit's rule (label exactly
`صحابي`); `companions_on_path` = every companion on a route, including one narrating from another.

## Definitions added in bucket 2

Every rule below is quoted from the classical text it encodes, with the Shamela page, so the
README can be checked against the books (the excerpts were fetched from Shamela and matched
character for character against the page text; editors' footnote numbers are dropped). Where a
source differs from the brief's attribution, the difference is stated and recorded in DECISIONS.

### Narrator levels (Taqrīb al-Tahdhīb) — `config/grades.yaml`
`rawis.rank_no` is Ibn Hajar's twelve levels (the labels on them are Taḥrīr al-Taqrīb's reading for the
Six Books' narrators and the source's editors' for the rest: *Data and provenance*). His introduction, as reproduced in *Taḥrīr Taqrīb
al-Tahdhīb* 1/52 ([127715/52](https://shamela.ws/book/127715/52); Shamela's copy of the *Taqrīb*
itself, book 8609, begins after the introduction):

> الخامسة: من قَصُرَ عن الرابعة قليلا، وإليه الإشارة: بصَدُوق سيء الحفظ، أو صدوق يَهِم، أو له أوهام، أو يُخطِئ، أو تَغيَّر بأخَرةٍ …
> السادسة: مَن ليس له من الحديث إلا القليل، ولم يثْبُت فيه ما يُترك حديثه من أجله، وإليه الإشارة بلفظ: مقبول، حيث يتابع، وإلا فَليِّنُ الحديث.
> السابعة: مَن رَوَى عنه أكثرُ من واحد ولم يُوثّقْ، وإليه الإشارة بلفظ: مستور، أو مجهول الحال.

### Weakness classes — `config/grades.yaml: weakness`

| class | members | why |
|---|---|---|
| light (repairable) | levels 5, 6, 7, 8; mursal; a tier-3 (or untiered) mudallis's uncovered muʿanʿan link | Nuzhat al-Naẓar's corroboration sentence (below) |
| unrepairable | level 9 (majhūl al-ʿayn); undescribed narrators, and unnamed persons below the companion slot not named elsewhere in the report; a tier-4/5 mudallis's uncovered muʿanʿan link (code ≥ 2) | Ibn Hajar: majhūl al-ʿayn is «كالمبهم», and «لا يُقْبَلُ حَديثُ المُبْهَم ما لم يُسَمَّ»; *Ṭabaqāt al-Mudallisīn* (PR 5, below) |
| fatal | levels 10, 11, 12; inqiṭāʿ and taʿlīq markers (an irsal marker anywhere but the top) | Ibn al-Ṣalāḥ: not every weakness is removed by other routes |

`light_includes_level_8: true` (switch: level 8 → unrepairable). Levels 1 to the ruleset's
`hasan_max_level` are not defects. *Nuzhat al-Naẓar* (ed. ʿItr, p. 105,
[1565/101](https://shamela.ws/book/1565/101)):

> ومتى تُوبعَ السَّيِّئُ الحِفْظِ بمُعْتَبَرٍ، كأَنْ يكونَ فوقَه أو مِثلَه لا دُونَه، وكذا المُخْتَلِطُ الذي لم يتميَّزْ والمستورُ والإسناد المُرسَلُ وكذا المُدَلَّس إذا لم يُعْرَفْ المحذوفُ منه: صار حديثُهم حَسَنًا لا لِذَاتِهِ، بَلْ وَصْفُه بذلك باعتبار المجموع من المَتابعِ والمتابَعِ

(the edition reads «باعتبار المجموع», not «بالمجموع» as the brief quotes). On the unknowns
(p. 101–102, [1565/97](https://shamela.ws/book/1565/97), [1565/98](https://shamela.ws/book/1565/98)):

> فإنْ سُمِّيَ الراوي وانفردَ راوٍ واحدٌ بالرِّواية عنه فهو مجهولُ العَيْن كالمُبْهَم … أو إِنْ روى عنه اثنانِ فصاعدًا ولم يُوَثَّقْ فهو مجهولُ الحال، وهو المَستُور … بَلْ يُقالُ: هي موقوفةٌ إلى اسْتِبانَةِ حَاله

The *Nuzha* does not say in so many words that the majhūl al-ʿayn is not repaired; it names the
mastūr, not him, among those repaired, and likens him to the mubham. Ibn al-Ṣalāḥ, *Muqaddima*
(ed. ʿItr, p. 34, [22870/31](https://shamela.ws/book/22870/31)):

> لَيْسَ كُلُّ ضَعْفٍ فِي الْحَدِيثِ يَزُولُ بِمَجِيئِهِ مِنْ وُجُوهٍ، بَلْ ذَلِكَ يَتَفَاوَتُ: فَمِنْهُ ضَعْفٌ يُزِيلُهُ ذَلِكَ بِأَنْ يَكُونَ ضَعْفُهُ نَاشِئًا مِنْ ضَعْفِ حِفْظِ رَاوِيهِ … وَكَذَلِكَ إِذَا كَانَ ضَعْفُهُ مِنْ حَيْثُ الْإِرْسَالُ زَالَ بِنَحْوِ ذَلِكَ … وَمِنْ ذَلِكَ ضَعْفٌ لَا يَزُولُ بِنَحْوِ ذَلِكَ

### Derived grade v2 (corroboration) — `itibar.corroborate`, `config/structure.yaml: derive`
Per chain c (derive version 3; each rule below is defined with its classical source in *Definitions
added in PR 5*):

    targets(c)      avoid: each_defect — one per light-defect position (a narrator of a light level, a
                    tier-3 mudallis's uncovered ʿan, an undescribed narrator when unknown = light) and one
                    for the mursal defect (mursal_rule ibn_hajar: nothing to avoid, any continuous witness
                    repairs it; shafii: the mursil); weakest | all_light_defects: one target, PR 4's set W
    witness(T)      an attested chain (one sanads row) other than c: continuous, light-or-better (no fatal
                    or unrepairable defect), carrying no node of T; from c's meaning group, else
                    (shahid_scope siblings) from a sibling group with matn overlap ≥ shahid_min_overlap
    corroborated(c) = every target has a witness
    witness_route_exists = the union graph at the light floor has a PROPHET -> book route avoiding each target
                    (PR 4's test, kept for the record)

    rule                                                          code
    a fatal defect                                                v1 code, never upgraded   fatal
    an unrepairable defect                                        max(v1 code, 2)           not_repairable
    light defects, every one covered                              1                         hasan_li_ghayrihi
    light defects, one uncovered                                  2                         daif
    no defect, weakest level <= sahih_max_level (3)               0                         sahih_li_dhatihi
    no defect, weakest level <= hasan_max_level                   1                         hasan_li_dhatihi
      + a ḥasan-or-better witness (defect-free, continuous) avoiding
        each of the chain's ḥasan-level narrators                  0                         sahih_li_ghayrihi

    rulesets        ibn_hajar: hasan_max_level 4;  ibn_al_salah: hasan_max_level 5
    group v2 code   = the lowest v2 code over all chains; ties: continuous, higher chain grade, lower sanad_id

**Divergence class** of a witness, read off the deepest node it shares with c above the position it
covers (the group's summary witness is the one covering the topmost position; a witness from another
group is always a shāhid): c's own teacher there and the same companion → `mutabaa_tamma`; the same
companion higher up → `mutabaa_qasira`; another companion → `shahid`; for a mursal chain, a witness
through the mursil himself → `wasl`, else `shahid`. *Nuzha* (pp. 73–75,
[1565/70](https://shamela.ws/book/1565/70), [1565/71](https://shamela.ws/book/1565/71)):

> إنْ حَصَلَتْ للراوي نَفْسِه فهي التامَّةُ. وإنْ حَصَلَتْ لِشَيْخِهِ فَمَنْ فَوْقَه فهي القَاصِرَة … وإنْ وُجِدَ مَتْنٌ يُرْوَى مِن حديثِ صحابيٍّ آخَرَ يُشْبِهُه في اللفظ والمعنى أو في المعنى فقط فهو الشاهِد

On ṣaḥīḥ li-ghayrihi (p. 66, [1565/62](https://shamela.ws/book/1565/62)):
«وبكثرة طُرُقِه يُصَحَّح … ومِنْ ثَمَّ تُطْلَقُ الصِّحَّةُ على الإسناد الذي يكون حسنًا لذاته لو تفرَّدَ إذا تعدَّد».
Ibn al-Ṣalāḥ's siwāk example, the reason for the `ibn_al_salah` ruleset (p. 35,
[22870/32](https://shamela.ws/book/22870/32)):

> فَمُحَمَّدُ بْنُ عَمْرِو بْنِ عَلْقَمَةَ مِنَ الْمَشْهُورِينَ بِالصِّدْقِ وَالصِّيَانَةِ، لَكِنَّهُ لَمْ يَكُنْ مِنْ أَهْلِ الْإِتْقَانِ … فَحَدِيثُهُ مِنْ هَذِهِ الْجِهَةِ حَسَنٌ

He continues that, being narrated by other routes as well, the chain «صح … والتحق بدرجة الصحيح».
Al-Shāfiʿī's conditions on the mursal, the `shafii` switch (*al-Risāla* §§1265–1268, p. 462,
[8180/547](https://shamela.ws/book/8180/547)):

> فإن شَرِكَه فيه الحفاظ المأمونون فأسندوه الى رسول الله بمثل معنى ما روى كانت هذه دلالةً على صحة مَن قبل عنه وحفظه … ويعتبر عليه بأن ينظر هل يوافقه مرسِل غيره ممن قُبل العلم عنه من غير رجاله الذين قُبل عنهم

Records carry `code_v2_<ruleset>`, `rule_v2_`, `best_sanad_v2_`, `witness_sanad_v2_`,
`witness_attested_v2_`, `divergence_v2_`, `witness_route_exists_v2_`, `witness_cross_group_v2_`,
`witness_group_v2_`, `n_witnesses_v2_`, `agree_v2_<ruleset>_vs_group`, and `receipt_v2` (the rule that
fired, the positions to cover, every witness with its divergence and, for a cross-group one, the
sibling group and the overlap, per ruleset); `v2_differs_from_v1`, `v2_by_corroboration`. Sensitivity
runs on `ibn_hajar` with one switch changed are stored as `code_v2_alt_<name>` (`derive.variants`:
`weakest`, `all_light_defects`, `shahid_group`, `shahid_strict`, `tasrih_corpus`, `mudallis_union`,
`unknown_none`, `mursal_shafii`, `no_level_8`, `witness_not_below`). Chains carry the per-chain
verdicts, positions to cover, defect reasons and `notes_v2_` (why a would-be defect is not one: a
tier-1/2 or Ṣaḥīḥayn ʿan, a link heard elsewhere, an unnamed person named elsewhere). Nothing is
tuned to the recorded grades; agreement is reported in the audit (§11), **never gated** (D63).

### Number class — `config/structure.yaml: number_class`

    number_class       = the cut points on kappa_all: 1 gharib, 2 aziz, 3 .. N-1 mashhur, >= N mutawatir_count;
                         N = tawatur_n = 10; gharib_mutlaq when a companion is among the cut vertices (the
                         tafarrud is at the root, where the companion is), else gharib_nisbi
    gharib_cut_kind    = companion | narrator | compiler: the topmost cut vertex of a gharib group
    number_class_width = the width reading (diagnostic): width_number(L) = on-path narrators with a narrator
                         role at layer L, Taqrib layers 1..12; min_width = min over the layers that have any;
                         gharib_mutlaq when layer 1 has width 1

Tafarrud is one man through whom every route passes — a cut vertex — so the class is read on κ
(structure version 4, D60); the width reading treats every Taqrīb layer as a cut although routes
skip layers (D43) and is kept beside it. *Nuzha* (pp. 42–57, [1565/38](https://shamela.ws/book/1565/38) ff.): on the mutawātir,
«فلا معنى لتعيين العدد على الصحيح. ومِنْهم مَنْ عَيَّنه في الأربعة، وقيل في الخمسة، وقيل في السبعة، وقيل
في العشرة، وقيل في الاثني عشر، وقيل في الأربعين، وقيل في السبعين»; the mashhūr «ما لَهُ طرقٌ محصورةٌ
بأكثرَ من اثنين»; «العَزِيز: وهو ألّا يروِيَه أقلُّ من اثنين عن اثنين», with his example «لا يؤمنُ
أحدُكم حتى أكونَ أحبَّ إليه من والده وولده» (p. 50, [1565/46](https://shamela.ws/book/1565/46)); the
gharīb «ما يتفَرَّدُ بروايته شخصٌ واحدٌ في أيِّ موضِعٍ وَقَعَ التفرُّدُ به من السَّنَد», muṭlaq when the
tafarrud is at the root, «وهو طَرَفُهُ الذي فيه الصحابي», nisbī when in the middle. N = 10 is al-Suyūṭī's
criterion; his own statement is known here only through others: al-Kattānī quotes al-Azhār as «أن
كل حديث رواه عشرة من الصحابة فهو متواتر عندنا معشر أهل الحديث» (*Naẓm*, p. 16,
[7016/15](https://shamela.ws/book/7016/15)), and *Kashf al-Ẓunūn* describes his larger book as
«ما رَواهُ من الصَّحابةِ عَشَرةٌ فصاعدًا» (5/306, [259/3091](https://shamela.ws/book/259/3091));
al-Suyūṭī's *Tadrīb* gives only al-Iṣṭakhrī's «أَقَلُّهُ عَشَرَةٌ» (2/627). The other values
(4, 5, 12, 40, 70) are in `tawatur_n_alternatives` and in the audit's sensitivity table.

### Qarāʾin — flags only
`in_sahihayn` (a chain in al-Bukhārī or Muslim, `books.id` 1, 2), `in_sahih_class` (a chain in a
`tasnif_no = 1` book), `sound_distinct_routes` (κ_saduq_up ≥ 3), `huffaz_chain` (a continuous chain
whose every graded narrator is level ≤ 2, and `number_class` — on κ since PR 5 — not gharīb). *Nuzha* (pp. 52–55,
[1565/48](https://shamela.ws/book/1565/48)–[51](https://shamela.ws/book/1565/51)):

> وقد يَقَعُ فيها أيْ في أخبارِ الآحادِ … ما يفيد العِلْمَ النظريَّ بالقرائنِ على المُختار … منها: ما أخرجه الشيخانِ في صحيحيهما ممّا لم يبلغِ التواتُرَ … ومنها: المشهورُ إذا كانت له طرقٌ متباينةٌ سالمةٌ من ضَعْفِ الرُّواةِ والعِلَلِ … ومنها: المُسَلْسَلُ بالأئمةِ الحُفَّاظِ المتقنين، حيث لا يكونُ غريبًا

**Knowledge yield is not computed.** The schools disagree, and itibar reports the indicators only:
Ibn Ḥazm, «أن خبر الواحد العدل عن مثله إلى رسول الله صلى الله عليه وسلم يوجب العلم والعمل معا وبهذا
نقول» (*al-Iḥkām* 1/119, [10432/117](https://shamela.ws/book/10432/117)); Ibn Hajar, inferential
knowledge with the qarāʾin, as above; al-Nawawī against Ibn al-Ṣalāḥ, «أحاديث الصحيحين التي ليست
بمتواترة انما تفيد الظن» (*Sharḥ Muslim* 1/20, [1711/20](https://shamela.ws/book/1711/20)).

### The classical lists — `itibar.lists`, `lists/`
- **al-Kattānī**, *Naẓm al-Mutanāthir min al-Ḥadīth al-Mutawātir*, Shamela book 7016 (the Fez print
  of 1328 AH), fetched page by page into `lists/source/` and parsed into `lists/kattani.yaml`:
  308 entries (numbers 1–310 as printed; 84, 187, 265 absent; 238 and 267 printed twice, the second
  keyed `238b`, `267b`), 231 quoted wordings, 75 topics, 2 cross-references; per entry the page,
  URL, his numbered narrators, the names, and the works he cites (a fixed vocabulary).
- **al-Suyūṭī**, *al-Azhār al-Mutanāthira*: not in Shamela's catalogue or on usul.ai. al-Kattānī states
  he included every hadith of al-Azhār, marked «أورده في الأزهار من حديث فلان», with the companions
  al-Suyūṭī counted and without al-Suyūṭī's citations. `lists/suyuti.yaml` is reconstructed from those
  markers (111 entries; al-Kattānī counted 112) and says SECONDARY on every line of its header; a
  scan of a printed edition can replace it.
- **Matching** (`lists.NORMALIZE_VERSION` 1: diacritics, tatweel, alif/yā'/tā' marbūṭa and hamza
  carriers normalized): for each entry and each meaning group, containment = max over the member
  matns (`hadiths.nass[matn_start:matn_end]`) and the group's `nass` of the idf-weighted share of
  the entry's tokens present; opening = the entry's first 4 tokens occur contiguously; support =
  member matns with containment ≥ 0.8, relative to the largest among the candidates.
  score = 0.5·containment + 0.2·opening + 0.3·support. `lists/candidates.csv` keeps the top 5.
  **Auto-confirmed** only for a quoted wording of ≥ 4 tokens with score ≥ 0.85, margin ≥ 0.25 over
  the second candidate and ≥ 3 supporting matns; everything else is `needs_review`.
  `lists/confirmed.csv` is the mapping the report reads; `human` rows are the reviewer's and are kept
  untouched by `make lists`.
- **Bins** (κ at `all`, tawatur_n): `wording` (a single matched group reaches it), `meaning_only` (only
  the pooled bundle of the matched groups does), `below_threshold_in_this_data`, `unmatched` (no
  confirmed group yet).

### Pooled bundles — `itibar.pool`, `itibar pool`
The bundle builder over the union of the chains of several groups (a list, a topic subtree via the
nested set, or a list entry's confirmed groups), with κ at every threshold, the width profile, the
number class and the companions. **A pool mixes distinct reports, so pooled κ measures tawātur in
meaning at the granularity of the pool, not of a wording.**

### Common-link census — `itibar.narrators`
`out/narrators.parquet`, per narrator: groups on path; as cut vertex at `all` and at `thiqa_up`;
as common link; as partial common link (k = 2); on a route that bypasses the group's common links
(`in_bypass` on the bundle nodes); in a compiler role; as a book transmitter only
(`groups_book_transmitter_role`; those groups are left out of his other counts); and, for a mudallis,
the share of his incoming links with a recovered word that are muʿanʿan. Compiler roles are per edge
(D61). Distributions of the common links' death
years and tabaka by collection class (groups with a chain in the Ṣaḥīḥayn / in a `tasnif_no = 1`
book / all) and the sanity check on al-Zuhrī, Qatāda, al-Aʿmash, Shuʿba and Mālik are in
`reports/common_links.md`.

### Chapter census — `itibar.chapters`
For every level-1 (13) and level-2 (362) node of `topics`: the distinct groups under it; the share
with κ_all = 1 and with κ_thiqa_up ≤ 1; median κ_all; shares by number class; the share whose v2
grade differs from v1.

### κ with only the years-incompatible links removed
`kappa_nocompat_years_θ`: as `kappa_nocompat_θ` but removing only links the years rule marks
incompatible (both dates known). κ_lower still uses the all-incompatible graph; both are reported.

## Definitions added in PR 5

Each correction is a switch in `config/structure.yaml` whose PR 4 value is kept; `make stages` reruns the
pipeline with them switched on one at a time, cumulatively, and audit §11 tabulates what each moved.
The passages below were fetched from Shamela and matched byte for byte against the page text (edition
separators «(٠)» and footnote numbers dropped).

### 1. A witness is one attested chain — `derive.corroboration.witness: attested`
A mutābaʿa or shāhid is a narration recorded in a chain (*Nuzha* p. 75,
[1565/71](https://shamela.ws/book/1565/71): «وإنْ وُجِدَ مَتْنٌ يُرْوَى مِن حديثِ صحابيٍّ آخَرَ يُشْبِهُه في اللفظ والمعنى أو في المعنى فقط فهو الشاهِد»). A witness is therefore one `sanads` row,
continuous and light-or-better, carrying none of the positions it covers; a route spliced from
several chains in the union graph, accepted in PR 4, is not. Whether the graph had such a route is
still stored (`witness_route_exists`), so the paper can say how often it had a route but no chain
(D56).

### 2. Tadlīs in tiers — `derive.tadlis`, `lists/mudallisin*`
Ibn Hajar's *Ṭabaqāt al-Mudallisīn* (*Taʿrīf Ahl al-Taqdīs bi-Marātib al-Mawṣūfīn bi-l-Tadlīs*),
Shamela book 1186 (ed. al-Qaryūtī), is digitized into `lists/mudallisin.yaml` (number, tier, name as
printed, his note, page): «فجمله ما في كتابي هذا مائة واثنان وخمسون نفسا» (p. 15, [1186/11](https://shamela.ws/book/1186/11)). His five tiers
(pp. 13–14, [1186/9](https://shamela.ws/book/1186/9), [1186/10](https://shamela.ws/book/1186/10)):

> الاولى من لم يوصف بذلك الا نادرا كيحيى بن سعيد الانصاري … الثانية من احتمل الائمة تدليسه وأخرجوا له في الصحيح لامامته وقلة تدليسه في جنب ما روى كالثوري أو كان لا يدلس الا عن ثقة كإبن عيينة … الثالثة من أكثر من التدليس فلم يحتج الائمة من أحاديثهم الا بما صرحوا فيه بالسماع ومنهم من رد حديثهم مطلقا ومنهم من قبلهم كأبي الزبير المكي … الرابعة من اتفق على أنه لا يحتج بشئ من حديثهم الا بما صرحوا فيه بالسماع لكثرة تدليسهم على الضعفاء والمجاهيل كبقية بن الوليد … الخامسة من ضعف بأمر آخر سوى التدليس فحديثهم مردود ولو صرحوا بالسماع الا أن يوثق من كان ضعفه يسيرا كابن لهيعة

His ruling on the mudallis (*Nuzha* p. 85, [1565/81](https://shamela.ws/book/1565/81)): «وحكم مَنْ ثَبَتَ عنه التدليسُ إذا كان عَدْلًا ألَّا يُقْبَلَ منه إلا ما صَرَّحَ فيه بالتحديث على الأصح.»; a
contemporary's ʿan counts as hearing, «وعَنْعَنَةُ المُعاصِرِ مَحمُولَةٌ على السَّماعِ» (p. 125, [1565/121](https://shamela.ws/book/1565/121)),
«إِلَّا من المُدَلِّس فإنها ليسَتْ محمولةً على السَّماعِ. وقيل: يُشتَرَطُ في حَمْلِ عَنْعَنَةِ المُعاصِرِ على السَّماعِ ثُبوتُ لِقَائِهما أي الشيخِ والراوي عنه ولو مرَّةً واحدةً» (p. 126, [1565/122](https://shamela.ws/book/1565/122)).

    mudallis        a narrator the source flags (rawis.has_tadlis; mudallis_set: union adds every narrator
                    matched to the book); tier = his tier in the book, untiered_tadlis (3) when not matched
    his ʿan         the word before his teacher's mention in continuity.muanan_words (عن, أن, قال)
    tier 1–2        no defect
    in a Ṣaḥīḥ      a chain of al-Bukhārī or Muslim: no defect, whatever the tier
    covered         the same teacher -> student link carries a hearing word (حدثنا, أخبرنا, أنبأنا, سمعت and
                    their forms: words.py classes haddathana, akhbarana, anbaana, samitu) in another chain of
                    the report (tasrih_scope: group), or stands in a chain of the Ṣaḥīḥayn there; anywhere in
                    the corpus with tasrih_scope: corpus (variant, «ثبت سماعه منه»)
    tier 3          a light defect unless covered
    tier 4–5        a defect unless covered, not lifted by corroboration (tier_4_5: not_repairable)

The Ṣaḥīḥayn convention, al-Nawawī, *Sharḥ Muslim* 1/33 ([1711/33](https://shamela.ws/book/1711/33)):
«واعلم أن ما كان فى الصحيحين عند المدلسين بعن ونحوها فمحمول على ثبوت السماع من جهة أخرى وقد جاء كثير منه فى الصحيح بالطريقتين جميعا فيذكر رواية المدلس بعن ثم يذكرها بالسماع», and on al-Aʿmash in Muslim (1/175, [1711/175](https://shamela.ws/book/1711/175)): «وَالْمُدَلِّسُ إِذَا قَالَ عَنْ لَا يُحْتَجُّ بِهِ إلا أن يَثْبُتَ سَمَاعُهُ مِنْ جِهَةٍ أُخْرَى وَقَدْ قَدَّمْنَا فِي الْفُصُولِ وَفِي شَرْحِ الْمُقَدِّمَةِ أَنَّ مَا كَانَ فِي الصَّحِيحَيْنِ عَنِ الْمُدَلِّسِينَ بِعَنْ فَمَحْمُولٌ عَلَى ثُبُوتِ سَمَاعِهِمْ مِنْ جِهَةٍ أُخْرَى». The
hearing words, the same page 1/33: «وما بينه فيه كسمعت وحدثنا وأخبرنا وشبهها فهو صحيح مقبول يحتج به»; anbaʾanā is ikhbār in the early usage (*Nuzha* p. 125):
«والإنباءُ مِنْ حَيْثُ اللُّغةُ واصطلاحُ المُتقدِّمين بمعنى الإخبارِ، إلَّا في عُرْفِ المُتأخِّرين فهو للإِجَازة». Tier 5 is rejected «ولو صرحوا بالسماع» for a weakness other than tadlīs, which itibar carries
as the narrator's level; its ʿan is treated as tier 4's (D57). The book is joined to `rawis` by
deterministic name matching (idf-weighted name tokens, article-insensitive, ism and father as units,
the nickname in the entry's head, a prolific-narrator tie-break): **auto** when ism and father agree and
either the score ≥ 0.7 with a margin ≥ 0.15, or the source's own `has_tadlis` flag marks the candidate
and no namesake, with score ≥ 0.6 and margin ≥ 0.1; everything else is `needs_review` in
`lists/mudallisin_confirmed.csv`, whose `human` rows are the reviewer's and are kept untouched.

### 3. Shawāhid from sibling groups — `shahid_scope: siblings`, `shahid_min_overlap: 0.32`
A shāhid is another companion's report of the same meaning (§1's sentence). The source files many as
separate meaning groups under one topic: the siblings of g are the other groups whose leaf rows in
`topics` share a parent with g's. When no witness in g covers a position, an attested chain of a
sibling group may, if it is light-or-better in its own group's classification, avoids the position, and
its matn (lists.normalize tokens) overlaps the chain's matn:

    overlap(A, B) = 2 · Σ idf(t), t ∈ A ∩ B  /  (Σ idf(t), t ∈ A  +  Σ idf(t), t ∈ B)     (idf over the corpus's matns)

The floor is the lowest band in which at least four in five of 50 inspected candidate pairs carry the
chain's content in whole or in part ([reports/shahid_inspection.md](reports/shahid_inspection.md),
D58). A cross-group witness is always a shāhid and is flagged with its group.

### 4. Every light defect covered — `avoid: each_defect`
«ومتى تُوبعَ السَّيِّئُ الحِفْظِ بمُعْتَبَرٍ» (above) is read for each defective narrator: every
light-defect position, and every structural light defect, needs a witness of its own; witnesses may
differ. `weakest` (PR 4) and `all_light_defects` (one witness avoiding all) are variants (D59). The
agreement gate is gone: agreement with the source's grades is reported, never tested (D63).

### 5. Book transmitters and compiler roles — `bundle.book_transmitters`, `structure.compiler_terminal: edge`
A narrator at pos 0 while the book's author (death year = `books.author_death_year` ± 1) sits at pos 1,
in ≥ 20% of the book's chains, is the book's **transmitter**; `book_compilers` names the author as
compiler (`compiler_rawi_id`; PR 4's reading kept as `compiler_rawi_id_pos0`). Two books qualify (audit
§11.6). Compiler terminal-ness is per edge (*Single strand*, *Partial common link* above; D61).

### 6. Number class on κ — `number_class.basis: kappa`
See *Number class* above (D60).

### 7. Whose verdicts the labels are
See *Data and provenance* and audit §11.7 (D65).

### 8. The unnamed person named elsewhere — `unknown_repair: named_elsewhere`
Ibn Hajar (*Nuzha* p. 101, [1565/97](https://shamela.ws/book/1565/97)): «ويُستدَلُّ على معرفةِ اسمِ المُبْهَم بورودِه من طريقٍ أُخرى مُسَمًّى.»; Ibn al-Ṣalāḥ
(*Muqaddima*, naw' 59, p. 375, [22870/372](https://shamela.ws/book/22870/372)): «وَيُعْرَفُ ذَلِكَ بِوُرُودِهِ مُسَمًّى فِي بَعْضِ الرِّوَايَاتِ». An unnamed
person below the companion slot is covered when another chain of the same report has a named narrator
between the same teacher and student; the position then takes that narrator's level (the weakest if
several) and is graded like him (D64).

## Definitions added in PR 6

Every change is a switch in `config/structure.yaml` whose PR 5 value is kept; `make stages` adds stages 8–11
(`config/stages/`), applied cumulatively in the brief's order, and audit §11.9–§11.12 tabulates what each moved. The
passages below were fetched from Shamela and checked byte for byte against the page text by a separate pass
(footnote numbers dropped).

### 1. The unnamed companion — `unnamed_companion` (structure version 5), `src/itibar/unnamed.py`
A chain whose top narrator is the unnamed person (`rawis` 1131, «اسم مبهم») was read as mursal (D36). The
tradition distinguishes a Successor's *ʿan rajul min aṣḥāb al-nabī* ("from a man of the Prophet's companions") from
a bare *ʿan rajul* ("from a man"). Ibn al-Ṣalāḥ, at the end of
the mursal (*Muqaddima* naw' 9, p. 56, [22870/53](https://shamela.ws/book/22870/53)):

> لِأَنَّ ذَلِكَ فِي حُكْمِ الْمَوْصُولِ الْمُسْنَدِ، لِأَنَّ رِوَايَتَهُمْ عَنِ الصَّحَابَةِ، وَالْجَهَالَةَ بِالصَّحَابِيِّ غَيْرُ قَادِحَةٍ، لِأَنَّ الصَّحَابَةَ كُلَّهُمْ عُدُولٌ

al-Khaṭīb, *al-Kifāya* (p. 415, [13055/1487](https://shamela.ws/book/13055/1487)–[1489](https://shamela.ws/book/13055/1489)), under
«بَابٌ فِي قَوْلِ التَّابِعِيِّ: حَدَّثَنِي رَجُلٌ مِنْ أَصْحَابِ النَّبِيِّ صَلَّى اللهُ عَلَيْهِ وَسَلَّمَ، هَلْ يَكُونُ ذَلِكَ حُجَّةً؟», reports Aḥmad's answer
«نَعَمْ» and Ibn ʿAmmār's «نَعَمْ , وَإِنْ لَمْ يُسَمِّهِ , فَإِنَّ جَمِيعَ أَصْحَابِ النَّبِيِّ صَلَّى اللهُ عَلَيْهِ وَسَلَّمَ كُلُّهُمْ حَجَّةٌ». Ibn Hajar,
on Ḥumayd al-Ḥimyarī's «لَقِيتُ رَجُلًا صَحِبَ النَّبِيَّ ﷺ» (*Fatḥ al-Bārī* 1/300, [1673/786](https://shamela.ws/book/1673/786)):

> رِجَالُهُ ثِقَاتٌ، وَلَمْ أَقِفْ لِمَنْ أَعَلَّهُ عَلَى حُجَّةٍ قَوِيَّةٍ، وَدَعْوَى الْبَيْهَقِيُّ أَنَّهُ فِي مَعْنَى الْمُرْسَلِ مَرْدُودَةٌ؛ لِأَنَّ إِبْهَامَ الصَّحَابِيِّ لَا يَضُرُّ، وَقَدْ صَرَّحَ التَّابِعِيُّ بِأَنَّهُ لَقِيَهُ

and, in *al-Nukat* (2/562–563, [8316/536](https://shamela.ws/book/8316/536)–[537](https://shamela.ws/book/8316/537)), the condition: a
Successor's «عن رجل» not described as a companion «فلا يكون ذلك متصلا لاحتمال أن يكون تابعيا آخر، بل هو مرسل على
بابه»; described as one, his ʿan is hearing provided he is free of tadlīs: «قلت: سلامته من التدليس كافية في ذلك».
(The brief expected a companion exception beside the *Nuzha*'s «ولا يُقْبَلُ حَديثُ المُبْهَم ما لم يُسَمَّ»
(p. 101, [1565/97](https://shamela.ws/book/1565/97)); there is none: that sentence is unqualified. In *al-Nukat* Ibn Hajar
does not reject al-Bayhaqī's reading as the brief has it; the rejection is in *Fatḥ al-Bārī*.) Who counts as a
companion is Ibn Hajar's definition (*Nuzha* p. 111, [1565/107](https://shamela.ws/book/1565/107)): «وهو مَنْ لَقِيَ النبيَّ -صَلَّى اللهُ عَلَيْهِ وَسَلَّمَ- مُؤمِنًا به وماتَ على الإسلامِ».

    designation   the mention text (hadith_rawis offsets; the chain aligned to the sanad-part mentions as in
                  words.py) plus the words after it up to the next mention, a delimiter or a transmission
                  word, at most 80 characters; unaligned: the hadith's last unnamed-person mention in the
                  sanad part (sanad_fallback_mention), or nothing (sanad_fallback_text: class none_text)
    class         the first of companion, ansar_muhajir, none whose phrase (unnamed_companion.phrases,
                  whole words, lists.normalize) occurs; none matched: unclassified (read as none)
    companion     «أصحاب النبي», «أصحاب رسول الله», «أصحاب محمد», «من الصحابة», «صحب النبي», «رأى النبي»,
                  «سمع النبي», «صلى مع النبي», «من أهل بدر», «أزواج النبي», «أمهات المؤمنين», «خادم النبي»,
                  «مصدق النبي», «من المبايعات», «رديف النبي» … (the Prophet's community; «أدرك النبي» is none)
    ansar_muhajir «من الأنصار», «من المهاجرين», «الأنصاري»: read as companion (ansar_muhajir: companion;
                  variant ansar_muhajir_mursal)
    unnamed companion  a PROPHET edge, Taqrīb level 1 (v1 and v2), no defect in v2 except the tadlīs rule on
                  the Successor's ʿan from him (al-Nukat); every unnamed companion of a group is one node
                  u<group_id>, never identified with a named companion (D70); kappa_unnamed_split = κ_all
                  with that node split per student; the census skips it; it is reported as a cut vertex
                  where it is one, and it is a companion for the number class

Records carry `kappa_unnamed_split`, `unnamed_companion_node`, `n_unnamed_companion_chains`,
`unnamed_top_classes`; chains `top_unnamed`, `unnamed_companion`; `out/unnamed_tops.parquet` keeps each chain top's
mention, designation, method, class and phrase. Variant `unnamed_top_mursal` reads every unnamed companion as PR 5 did.

### 2. Conditional narrators — `derive.conditional`, `lists/conditional*`, `src/itibar/conditional.py`
A narrator's standing can be conditional on the link: weak from one teacher, sound from the people of his own
land, sound through some students, sound before his memory failed. The rulings are read from the books, one row
per (narrator, kind, condition ids, effect, book, page, quoted sentence) in `lists/conditional_confirmed.csv`;
`lists/conditional.yaml` holds those in force (auto and the reviewer's human rows).

    seed          PR 5's residue table, every conditional label («إلا في», «روايته عن», «اختلط», «تغير», «بأخرة»,
                  «أهل بلده» …), the source's has_ikhtilat flag, the brief's named cases, and every entry of
                  al-Kawākib al-Nayyirāt (Shamela 309), al-ʿAlāʾī's al-Mukhtaliṭīn (25846), Sibṭ Ibn
                  al-ʿAjamī's al-Ightibāṭ (130) and Ibn Rajab's «القسم الثاني» (9552) matched to rawis
    entries       each seed's Taqrīb (8609) and Taḥrīr (127715) entry, accepted after an identity check
                  (four name words in order, or three with a nisba or the label in the entry)
    from_shaykh   «إلا في روايته عن X», «روايته عن X خاصة مضطربة», «في حديثه عن X ضعف», «ثقة في غير X»,
                  «تكلموا في روايته عن X» -> defect:light from X;  «أثبت الناس في X» -> accepted
    region        «صدوق في روايته عن أهل بلده» -> the verdict's level from teachers of his region (nisba in
                  rawis.nasab or residence in rawis.iqama against conditional_rules.regions)
    via_student   «ورواية X وY عنه أعدل» (Taqrīb) -> the verdict's level; «وحديثه صحيح إذا روى عنه» (Taḥrīr) -> 3
    ikhtilat      stated in his own entry («اختلط», «خلط», «تغير»), not as minor («قليلا», «لم يفحش», «فلم
                  يحدث» …), not disputed by Taḥrīr, not in al-ʿAlāʾī's first category, and at least one
                  student documented as hearing before; students placed by explicit list phrases («وممن سمع
                  منه قبل الاختلاط: …») in his entry, then in the ikhtilāṭ books (the entry wins; a student
                  on both sides is left out); before -> the level of Taḥrīr's «بل:» verdict, else of the
                  Taqrīb's without the qualifier; after -> defect:light; unknown: after; a link in a chain of
                  the Ṣaḥīḥayn, or the same student -> narrator link standing in one in the report, is before
    unobservable  from his book vs memory, the place of hearing, after his books burned, material put to
                  him: recorded with observable: false, applied nowhere
    names         teachers and students resolved among the narrators actually adjacent to him in the
                  chains (sanad_rawis): ism + father, «ابن» + father, kunya, a nisba, a lone ism; a name
                  several fit resolves by the nisba after it, or to the one with ≥ 95% of their links
                  (conditional_rules.dominance)
    auto          stated in the narrator's own Taqrīb or Taḥrīr entry, every id matched uniquely, nothing
                  unmatched, not disputed by Taḥrīr; else needs_review. Human rows are the reviewer's.

Applied in `corroborate.py` on the link, before the chain grade: the position's effective level is the ruling's
where its condition holds (the narrator's otherwise); defect:light adds a light defect there; the receipt names
the ruling, its source sentence and the ids that satisfied it. The chain grade stays weakest-link. **κ thresholds
are node-level and are not changed by link rulings**, and v1 (the narrators' levels as recorded) is not either.

Ibn al-Ṣalāḥ on the mukhtaliṭūn (*Muqaddima* naw' 62, p. 392, [22870/389](https://shamela.ws/book/22870/389)):

> وَالْحُكْمُ فِيهِمْ أَنَّهُ يُقْبَلُ حَدِيثُ مَنْ أُخِذَ عَنْهُمْ قَبْلَ الِاخْتِلَاطِ، وَلَا يُقْبَلُ حَدِيثُ مَنْ أُخِذَ عَنْهُ بَعْدَ الِاخْتِلَاطِ، أَوْ أُشْكِلَ أَمْرُهُ فَلَمْ يُدْرَ هَلْ أُخِذَ عَنْهُ قَبْلَ الِاخْتِلَاطِ أَوْ بَعْدَهُ

and on the Ṣaḥīḥayn (p. 397–398, [22870/394](https://shamela.ws/book/22870/394)–[395](https://shamela.ws/book/22870/395)):
«وَاعْلَمْ أَنَّ مَنْ كَانَ مِنْ هَذَا الْقَبِيلِ مُحْتَجًّا بِرِوَايَتِهِ فِي الصَّحِيحَيْنِ أَوْ أَحَدِهِمَا فَإِنَّا نَعْرِفُ عَلَى الْجُمْلَةِ أَنَّ ذَلِكَ مِمَّا تَمَيَّزَ، وَكَانَ مَأْخُوذًا عَنْهُ قَبْلَ الِاخْتِلَاطِ».
The defect is light: the *Nuzha*'s corroboration sentence (above) names «المُخْتَلِطُ الذي لم يتميَّزْ» with the
poor-memory narrator; its ruling (p. 104–105, [1565/100](https://shamela.ws/book/1565/100)–[101](https://shamela.ws/book/1565/101)):
«والحُكْمُ فيه أنَّ ما حَدَّثَ به قَبْلَ الاختلاطِ إذا تَمَيَّزَ قُبِلَ، وإذا لم يَتميزْ تُوُقِّفَ فيه، وكذا من اشْتَبَهَ الأمرُ فيه، وإنما يُعرَفُ ذلك باعتبارِ الآخِذينَ عنه».
al-ʿAlāʾī's three categories (*al-Mukhtaliṭīn* p. 3, [25846/1](https://shamela.ws/book/25846/1)): «أحدها: من لم يوجب ذلك
له ضعفا أصلا ولم يحط من مرتبته … والثاني: من كان متكلما فيه قبل الاختلاط … والثالث: من كان محتجا به ثم اختلط …
فيتوقف الاحتجاج به على التمييز». The Taqrīb sentences the brief names (each in `lists/conditional_confirmed.csv`
with its page): Ismāʿīl b. ʿAyyāsh «صدوق في روايته عن أهل بلده مخلط في غيرهم» (p. 109,
[8609/35](https://shamela.ws/book/8609/35)); Simāk «صدوق وروايته عن عكرمة خاصة مضطربة وقد تغير بأخرة» (p. 255,
[8609/181](https://shamela.ws/book/8609/181)); Ibn Lahīʿa «صدوق من السابعة خلط بعد احتراق كتبه ورواية ابن المبارك وابن وهب عنه أعدل من غيرهما»
(p. 319, [8609/245](https://shamela.ws/book/8609/245)), which Taḥrīr revises to «ضعيفٌ يُعتَبر به، وحديثه صحيح إذا روى
عنه العبادلة: ابن المبارك، وابن وهب، وابن يزيد المقرئ، وابن مسلمة القعنبي» (2/258,
[127715/686](https://shamela.ws/book/127715/686)).

### The hearing check on tier 4 — `tadlis.tasrih_tiers: [3, 4, 5]`
Tier 4 is accepted «بما صرحوا فيه بالسماع» (*Ṭabaqāt al-Mudallisīn*, above). PR 5's code already lifted a tier-4
(and tier-5) ʿan covered by a hearing word on the same link elsewhere in the report; the switch makes it explicit
and the variant `tasrih_tier_3_only` measures it (D73).

### 3. The residue — `src/itibar/residue.py`, `reports/residue.md`, `figures/fig6_residue.*`
Every group whose v2 grade (`ibn_hajar`) differs from `meaning_groups.matn_no` is tagged by mechanical cause; the
tags (`residue_tags`, not exclusive), the primary tag (`residue_primary`, by `residue.precedence`), the direction
(`stricter`: our code higher; `lenient`: lower), the weakest narrators, the conditional status and the witness's
divergence are stored per group. The definitions are in the module and the report, which states what the chain
cannot see and issues no verdict on which grade is right.

### 4. Two defaults
- **Sibling shawāhid are a variant** (`shahid_scope: group`; `siblings`, `siblings_strict` the variants; D58
  amended, D75): the idf-weighted Dice measures shared vocabulary, not shared meaning (an inspected pair whose
  witness negates the chain scores 0.60), and shāhid detection by meaning is the text layer's work.
- **The mudallis set is the Ṭabaqāt union** (`mudallis_set: union`; `mudallis_source_flag` the variant; D57
  amended, D76): every narrator matched to Ibn Hajar's book at his tier, plus the source's flagged narrators at
  `untiered_tadlis` where not matched, so the sentence cites a book.

## Outputs

| file | content |
|---|---|
| `out/records.parquet` | one row per meaning group (20,745; `status = no_chains` for the 463 without chains) |
| `out/chains.parquet` | one row per chain: flags, chain grade, weakest link, max_rank comparison, v2 verdicts per ruleset |
| `out/bundles/nodes`, `out/bundles/edges` | the bundle graphs, Hive-partitioned by `bucket` (nodes carry `in_bypass`) |
| `out/words.parquet` | transmission word per aligned (sanad, teacher pos) |
| `out/unnamed_tops.parquet` | every chain top that is the unnamed person: mention, designation, method, class, phrase (PR 6 §1) |
| `out/narrators.parquet` | the narrator census (one row per narrator on any bundle) |
| `out/matn_tokens.parquet`, `out/matn_vocab.parquet` | normalized matn tokens and idf for the shāhid overlap |
| `out/stages/<stage>/` | records and chains of each cumulative PR 5 and PR 6 stage (`make stages`) |
| `lists/conditional.yaml`, `lists/conditional_candidates.csv`, `lists/conditional_confirmed.csv` | conditional narrator rulings in force; every proposal with its match evidence; the rows used (`auto` / `needs_review` / `human`) (PR 6 §2) |
| `lists/source/conditional_taqrib.jsonl`, `kawakib_309.jsonl`, `alai_25846.jsonl`, `ightibat_130.jsonl`, `ibn_rajab_9552.jsonl`, `boundary_verdicts.jsonl` | the Taqrīb and Taḥrīr entries of the seed narrators, the three ikhtilāṭ books, Ibn Rajab's section, and the verdicts read for the ṣaḥīḥ/ḥasan line |
| `lists/mudallisin.yaml`, `lists/mudallisin_candidates.csv`, `lists/mudallisin_confirmed.csv` | Ibn Hajar's *Ṭabaqāt al-Mudallisīn* digitized; top-5 narrator candidates per entry; the tier mapping used (`auto` / `human`) |
| `lists/shahid_inspection.yaml`, `reports/shahid_inspection.md` | the 50 cross-group witness candidates read to set the overlap floor, with labels |
| `lists/source/taqrib_sample.jsonl` | the 40-narrator sample against the Taqrīb and Taḥrīr al-Taqrīb (audit §11.7) |
| `lists/kattani.yaml`, `lists/suyuti.yaml` | the classical lists, digitized (al-Suyūṭī secondary, via al-Kattānī) |
| `lists/candidates.csv`, `lists/confirmed.csv` | top-5 group candidates per entry; the mapping used (`auto` / `human`) |
| `reports/audit.md`, `reports/gold.md` | source audit (incl. §10 gold error rate, §11 v2 and every PR 5 correction's before/after, §12 number class and qarāʾin); gold-set results |
| `reports/lists.md`, `reports/common_links.md`, `reports/chapters.md`, `reports/pools/` | bucket-2 reports |
| `reports/residue.md` | the disagreement with the recorded grades, tagged by mechanical cause, with a seeded sample of receipts (PR 6 §3) |
| `figures/` | fig1 (κ by threshold), fig2 (width by Taqrib layer 1–12), fig3 (list bins), fig4 (common-link death years), fig5 (chapter census), fig6 (the residue by primary tag and direction), each with a CSV |

## Gates and gold set

- **Gold set** (`tests/gold/gold.yaml`, 44 entries): 15 mutawatir topics from al-Kattani's *Nazm
  al-Mutanathir* (κ_everyone > 1 and ≥ 10 companions asserted; κ at every threshold recorded), and
  7 gharib / 'aziz / mashhur / mutaba'at cases from Ibn al-Salah, Ibn Hajar, Muslim and al-Tirmidhi,
  asserted down to the exact cut vertices (e.g. *innama al-a'mal* through 'Umar: cut vertices
  'Umar → 'Alqama → al-Taymi → Yahya b. Sa'id al-Ansari (d. 143), κ = 1, ≥ 25 students below Yahya).
  Every chain in the data that contradicts a documented structure is listed by sanad id with its
  reason; the test asserts that list is exact. Bucket 2 adds 11: the siwāk chain through Muḥammad b.
  ʿAmr (level 5; ḥasan li-ghayrihi under `ibn_hajar`, ṣaḥīḥ li-ghayrihi under `ibn_al_salah`, as in
  Ibn al-Ṣalāḥ); the sandals dowry through ʿĀṣim b. ʿUbaydallāh (level 8; no witness inside the group,
  D54, but repaired by a shāhid from a sibling group — Sahl b. Saʿd's report, the one al-Tirmidhī names
  in his «وفي الباب» — D58); a
  maqbūl (level 6) chain followed from its own teacher (mutābaʿa tāmma, code 1); the Kitāb al-ʿAql
  chains (two routes, all through level 12: never upgraded); number class for *innamā* (gharīb
  muṭlaq), *lā yuʾminu* ('azīz), *man kadhaba* (mutawātir by count) and *al-muslim man salima*
  (mashhūr by width, mutawātir by κ since PR 5); qarāʾin; al-Kattānī's entry 2 auto-matched to group 1.
  PR 5 adds 2: al-Aʿmash's ʿan in Muslim (tier 2, no defect) and Qatāda's ʿan from Anas in the *Musnad*
  covered by «حدثنا» in the Ṣaḥīḥayn's chains of the same report (tier 3). PR 6 adds 9: Ḥumayd al-Ḥimyarī's
  «لقيت رجلا صحب النبي ﷺ» (an unnamed companion: a PROPHET edge to u6524, no defect at the top; Ibn Hajar in
  *Fatḥ al-Bārī*); Ibn Lahīʿa through Ibn Wahb (the `via_student` level) and through another student (his own
  level, light); Ismāʿīl b. ʿAyyāsh from the Syrian Shuraḥbīl b. Muslim (the `region_of_shaykh` level) and from
  the Madinan Mūsā b. ʿUqba (level 5, light), as al-Tirmidhī reports al-Bukhārī; Saʿīd b. Abī ʿArūba through
  Yazīd b. Zurayʿ (heard before) and through Wakīʿ (after); Simāk from ʿIkrima (the light defect); Ibn Isḥāq's
  ʿan from Makḥūl in al-Tirmidhī, covered by «حدثني مكحول» in the report's other chains (tier 4; al-Bayhaqī:
  «ذكر فيه سماع محمد بن إسحاق من مكحول»). The sandals entry asserts its repair under `siblings` and its
  in-group result under the default.
- **max_rank gate**: weakest link = `sanads.max_rank` for 100% of chains (577,020/577,020); with the
  book-role positions excluded as the derived grade does, every difference is a chain whose excluded
  compiler (or book transmitter and the compiler after him) is strictly its weakest narrator — the only
  two classes, asserted.
- **Companion band**: for the ten most-narrated groups, upstream's recount ≤ ours ≤ declared
  `sahaba_qty`; corpus-wide (declared ≥ 10) our median ratio to declared is 0.846, inside upstream's
  0.795–0.966; ours exceeds declared in 0.7% of groups.
- **κ = 0 explained**: every group with κ_everyone = 0 has a `kappa_zero_reason`, and `other`
  (a continuous chain but no route) occurs 0 times.
- **No agreement gate** (removed in PR 5, D63): agreement with the recorded grades is reported in the
  audit, never tested. In its place, rule consistency: fatal chains keep their v1 code, unrepairable
  ones max(v1, 2); every upgrade names an attested witness chain and a divergence class; a cross-group
  witness is a shāhid from another group; the number class follows κ — plus the synthetic tests of
  every PR 5 rule (`tests/test_pr5.py`) and every PR 6 rule (`tests/test_pr6.py`); the unnamed companion ends his
  chain at a companion and splitting his node never lowers κ; every disagreeing group has a direction and its
  primary tag among its tags.
- Also asserted: one record per group; κ_lower = min of the three hypotheses, ≤ κ_nocompat ≤ κ,
  κ_nocompat ≤ κ_nocompat_years ≤ κ, and nested thresholds; cut vertices iff κ = 1; bypass = 0 iff the
  common link is a cut vertex; number class and qarāʾin follow their definitions; recorded values
  untouched; no verdict words (receipts v1 and v2 included).

## Results at a glance (full corpus)

![κ across 20,282 meaning groups by narrator-grade threshold, and the share of groups by κ](figures/fig1_kappa.png)

20,282 groups with chains. κ_everyone: 0 in 14.2% (no unbroken companion-ending route in this
data: 2,448 groups with no companion-ending chain, 426 where every such chain is broken), 1 in
55.3%, 2–4 in 22.2%, 5–9 in 5.7%, ≥ 10 in 2.5% (511 groups); at thiqa and above, ≥ 10 in 108 groups.
κ_lower_everyone ≥ 10 in 457 groups (98 at thiqa and above); κ_lower < κ in 2,447 groups, almost all
through removed incompatible links; removing only the years-incompatible links lowers κ in 734. The
unnamed companion (PR 6): 1,915 chain tops in 501 groups read as an unnamed companion; 82 groups that had
no companion-ending chain now have κ_all ≥ 1; splitting the merged node per student would raise κ_all in 17
groups (`kappa_unnamed_split`).

**Derived grade** (after the PR 5 and PR 6 changes; audit §11). Agreement with the recorded group grade is
reported, never gated: v1 72.67%; v2 `ibn_hajar` 71.53%, v2 `ibn_al_salah` 72.75% (PR 5: 72.35%, 71.21%,
72.11%; PR 4: 72.86% and 72.37%). PR 5's corrections, applied in order (stage table, audit §11.1): attested
witnesses only 72.86% → 73.41% (the block *ours 1 / source 3–5* 562 → 457 groups); tiered tadlīs with the
hearing check and the Ṣaḥīḥayn convention → 74.15%; shawāhid from sibling groups → 73.21%; every light defect
covered → 71.09%; the unnamed person named elsewhere → 71.21%. PR 6's, in order: the unnamed companion →
71.49% (72 groups change); conditional narrator rulings → 71.20% (157 groups; 35 rulings in force on 25
narrators, 353 rows await the reviewer); sibling shawāhid made a variant → 71.82% (607 groups); the mudallis set
the Ṭabaqāt union → 71.53% (159 groups). The hearing check on tier 4 was already in PR 5 (variant
`tasrih_tier_3_only`: 71.55%, 28 groups differ). The class corroboration addresses (v1 code 2, recorded حسن)
holds 1,733 groups (v1: 2,556). 2,312 groups are upgraded; their summary witness is a shāhid in 1,343, a
mutābaʿa tāmma in 569, qāṣira in 297, waṣl in 103. In 154 groups whose v2 chain stays ḍaʿīf the union graph had
a route the attested chains do not.

**The residue** ([reports/residue.md](reports/residue.md), fig6). 5,774 of the 20,282 groups (28.5%) disagree
with the recorded grade; 56.8% are lenient (our code lower than the source's). Another attested chain of the
group yields exactly the source's code in 44.8% (the unit of grading); the primary causes after it:
corroboration 24.2%, a narrator with a conditional ruling 6.3%, an uncovered tadlīs ʿan alone 5.9%, a source code
3–5 over a chain of narrators no worse than level 9 5.1%, mixed defects 6.7%. The report lists what the chain
cannot see and issues no verdict on which grade is right.

**Number class** (on κ_all since PR 5): gharīb muṭlaq 51.5%, gharīb nisbī 3.8%, ʿazīz 13.3%, mashhūr
14.7%, mutawātir by count (≥ 10) 511 groups (2.5%); no route 14.2%. The width reading (diagnostic) has
gharīb 77.0% and 95 groups at ≥ 10; the two readings differ in 31.5% of groups, mostly gharīb by width
with κ ≥ 2 (a lone narrator in a layer the other routes skip). **Qarāʾin**: in the Ṣaḥīḥayn 2,690;
≥ 3 distinct ṣadūq+ routes 1,575; a ḥuffāẓ chain (not gharīb by κ) 1,195; all three 664.

**Lists.** al-Kattānī: 308 entries; 92 auto-matched, of which 71 reach κ_all ≥ 10 in a single group
and 21 do not; 216 await review (75 are topics). al-Suyūṭī (111, via al-Kattānī): 58 auto-matched, 46
reach it. *man kadhaba* (group 1): κ_all 63 (an unnamed companion added), κ_thiqa+ 22, 66 named companions.

**Common links** (compiler roles per edge since PR 5). 21,447 (group, common link) pairs; 51.0% sit at
the companion level. Median death year 88 AH (73 in Ṣaḥīḥayn groups); 30.3% died 100–199 AH (23.4% in
Ṣaḥīḥayn groups). PR 4's second cluster of common links dying 200–300 AH (19% of Ṣaḥīḥayn pairs, 4.5%
now) was an artefact of compilers being terminal nodes: their teachers became the uppermost partial
common link. Below the companions al-Zuhrī now ranks 1st (PR 4: 6th), Qatāda 5th (18th), al-Aʿmash
11th (26th), Shuʿba 17th (37th) and Mālik 41st (131st; his *Muwaṭṭaʾ* is one qualifying branch, D61).

**Chapters.** Across the 13 top-level chapters, 43% (المعاملات) to 57% (الفضائل والمناقب) of groups have
κ_all = 1, and 73% to 91% have at most one thiqa route. **Pools**: the Dajjāl subtree (39 groups) has
κ_all 34 (thiqa+ 20) and 42 named companions; the Mahdī subtree (18 groups) κ_all 11 (thiqa+ 3), 14
companions, mashhūr by width and mutawātir by κ.

**Gold error rate.** In the four gold entries inspected chain by chain, 14 of 843 in-scope chains
(1.66%) carry a documented misresolution or dropped link (audit §10).

## Layout

    config/          grades.yaml, structure.yaml, source.yaml; stages/ (the cumulative PR 5 and PR 6 stages)
    src/itibar/      data, audit, audit_pr5, audit_pr6, grades, load, words, unnamed, matn, bundle, flow, structure,
                     derive, corroborate, conditional, residue, residue_report, siblings, pipeline, stages, scope,
                     gold, fixture, figures, cli, pool, lists, mudallisin, provenance, narrators, chapters
    lists/           kattani.yaml, suyuti.yaml, candidates.csv, confirmed.csv, mudallisin*.{yaml,csv},
                     conditional*.{yaml,csv}, shahid_inspection.yaml; source/ (fetched text)
    tests/           unit (flow vs networkx, synthetic bundles, bucket 2, PR 5, PR 6), gold, gates; fixture/ (committed sample)
    reports/         audit.md, gold.md, lists.md, common_links.md, chapters.md, residue.md, shahid_inspection.md, pools/
    figures/         fig1 – fig6
