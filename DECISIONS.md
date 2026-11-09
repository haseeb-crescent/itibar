# Decisions

Every choice the data forced that the bucket-1 definitions (and the PR 2 corrections,
`docs/prompts/pr-2.md`, D30–D34, and bucket 2, `docs/prompts/bucket-2.md`, D35–D55) did not settle,
with the alternatives.
Numbers are from the full corpus (`reports/audit.md` has the evidence). Each entry names the config
key that controls it, where there is one.

## Data model

**D1. Narrator grades come from `rank_no`, not the label text.** `rank_no` is Ibn Hajar's twelve
Taqrib levels; the `rank` strings are free text (499 distinct) and a handful contradict their level
(`لم تثبت له صحبة` at level 1, `صحابي صغير` at 3–4, `ضعيف الحديث` at 7). We grade by `rank_no`, list every
label with its ordinal in `config/grades.yaml`, and flag the contradictions in the audit.
*Alternatives:* parse labels into our own scale (re-grades the source; rejected); per-label overrides
(supported later by adding to `grades.yaml`; none applied).

**D2. Companion = rank_no 1 minus explicit denials** (`لم تثبت له صحبة`, `له إدراك`, `لها إدراك`;
`grades.yaml: companion`), plus the young-companion label overrides of D33. *Alternatives:* upstream's exact label `صحابي` (drops 10,646 chains ending at
female companions and 3,879 at `صحابي صغير`); `tabaka = 1` (admits 60 narrators of other levels).

**D3. Four rows are placeholders, not narrators** (`rank IS NULL`, `rank_no = 12`; `grades.yaml:
placeholders`). Break markers `موضع إرسال` (32,502 links), `موضع انقطاع` (13,996), `موضع تعليق` (6,719)
become one *untraversable* gap node per chain occurrence: the gap is recorded and shown, no route
crosses it. *Alternatives:* keep the shared id (fuses unrelated routes into a false hub and gives
every broken chain the كذاب level — rejected); drop broken chains entirely (loses their unbroken
segments); a traversable per-chain gap (counts a broken chain as a route).

**D4. The unnamed person (`اسم مبهم`, 15,187 links) is one node per (student, teacher) context**,
ordinal 0. "A man" between the same two people is taken to be one man. *Alternatives:* one node per
occurrence (inflates width/κ when the same man appears in parallel chains of one hadith); one global
node (fuses everything). κ_lower merges them per student.

**D5. A compiler node `c<author_no>` sits in front of every book; book nodes are never cut.** pos 0
is the compiler in primary collections (al-Bukhari 99.5%, Muslim 99.9%, Ahmad 99.4%) but not in
quoting books (Tarikh Dimashq 11%, Tahdhib al-Kamal, the zawa'id books): 113,130 chains start with
someone else. Without the node, a lone compiler's teachers would count as parallel routes. The
compiler's narrator id is resolved from the dominant pos-0 narrator (share ≥ 0.5,
`structure.yaml: bundle.compiler_min_share`) of any of his books, stored as the derived table
`book_compilers` so the fixture reproduces it. *Alternatives:* the brief's literal `pos 0 → book`
(inflates quoting books); cuttable book nodes (a book is a record, and one author's several books
would count separately).

**D6. A compiler is exempt from grade thresholds in his compiler role only.** If he fails θ his
edges into his own books survive and his edges as a teacher elsewhere are removed. Found through
Muhammad b. Fudayl (Taqrib level 5), who compiles his own Kitab al-Du'a and narrates in al-Bukhari's
chain of *kalimatan khafifatan*; a node-wide exemption let al-Bukhari's route through him pass the
thiqa threshold. Likewise the chain grade excludes pos 0 only when pos 0 is that book's compiler.

**D7. Threshold boundaries.** `above_matruk` = Taqrib 1–9, `saduq_up` = 1–4, `thiqa_up` = 1–3.
*Alternatives:* treat level 9 (majhul al-'ayn) as severely weak (8 as the cut); `saduq_up` = 1–5
(level 5 is "saduq with a qualifier", which later scholars often still call hasan); `thiqa_up` = 1–2.
All are one edit in `grades.yaml: thresholds`.

**D8. Unknown narrators** (25 stubs, the unnamed person) get ordinal 0: kept only at `all`, and a
chain through one cannot be placed above code 2 (the classical rule on jahala).

**D9. Continuity window up to +4, not the brief's {0,1,2}** (`structure.yaml: continuity`; extended
to [−1..4] with an age of hearing in D32). On this
source's tabaka scale, {0,1,2} marks 36% of all 4.4M links incompatible, including canonical ones:
Anas → al-Zuhri, 'Alqama → al-Taymi, al-Zuhri → Malik, Qatada → Shu'ba are gaps of 3, al-Zuhri →
Ibn 'Uyayna 4. [0..4] is the narrowest window that keeps them; "incompatible" then means a gap of 5+
layers or a student placed before the teacher. Years, when both known, still decide first. Since
D30 the flags feed one quantity, the `nocompat` hypothesis of κ_lower; κ and the derived grade
never use them.

**D10. tabaka is not Taqrib's tabaqa.** It runs 0–38 (0 = missing), 1–12 follow Taqrib's
layering (Ibn Hajar's death-year rule holds for 87–100% of layers 4–12) and some narrators sit one
layer off Taqrib (al-Taymi 5 vs 4, Yahya al-Ansari 6 vs 5, al-Bukhari 10 vs 11). We use it as given.

**D11. Layer fallback** for missing tabaka, or a tabaka more than one layer before *every* resolved
teacher: one layer below the latest resolved teacher (depth propagated from P), recorded in
`layer_source`. *Alternative:* plain BFS depth from P (mixes chain steps with tabaka layers, which
are not the same unit).

## Structure

**D12. The transmission word is read before the teacher's mention.** In "حدثنا قتيبة قال حدثنا
سفيان عن الزهري" the `عن` before al-Zuhri is Sufyan's mode of receiving from al-Zuhri. So for edge
u → v the mu'an'an test is `has_tadlis(v)` and the word before **u**'s mention. The brief says "before
v's mention", which would read the student's own teacher-facing word for the wrong link.

**D13. Word extraction.** Mentions restricted to the sanad part (before `matn_start`); chains aligned
exactly (single-chain hadith) or as an in-order subsequence (tahwil and extra mentions; recorded in
`method`); break markers skipped (they have no mention). `word` is the last recognised transmission
token between the previous mention and this one, so `قال: حدثنا` yields `حدثنا`; `word_raw` keeps the
one or two tokens before the mention, as the brief asks. Normalization v1 strips diacritics only.
85.8% of narrator links get a word; upstream's exact check (216,177) reproduces.

**D14. Single strands, PCLs and compilers.** Compiler nodes, book nodes and narrators acting as
compilers are terminals: they are never single strands and do not count as the "non-single-strand
node" that makes a branch qualify (otherwise every branch reaching al-Bukhari, who has many teachers,
would qualify). A branch qualifies "directly" when the student is himself the compiler.

**D15. Common links.** All PCL(2) nodes with no PCL ancestor are reported; when two PCLs sit in one
cycle with no PCL upstream, both are reported and `cl_in_cycle` is set. Companions qualify; P does not.

**D16. Bypass and path counts.** Counted over the on-path graph by DP (exact Python integers, stored
as decimal(38)); on the 322 cyclic bundles, over a deterministic acyclic reduction (back edges of a
sorted DFS dropped), flagged. Added `bypass_chains` (attested continuous chains avoiding the CLs),
which is easier to read than a path count. With several CLs, bypass avoids all of them.

**D17. κ_lower is a minimum over stated hypotheses, not a guarantee.** κ_lower is the minimum of
κ over three stated hypotheses — same-name clusters merged, unmerged, and continuity-incompatible
links removed (the third added in D30). It is a lower bound under those hypotheses, not a
guarantee. Cross-name misresolution that the continuity rule does not catch remains an
unquantified upward bias on κ; `tests/gold/gold.yaml` lists the instances found. Merging nodes is
not monotone: it can splice a dead-end half-route of one person onto a half-route of another and
*raise* κ. Found when we also merged each compiler stand-in with the compiler's narrator node (Abu
Hanifa: his Kufan chain from Ibn Mas'ud dead-ends in this group, his *Musnad*'s records do not
reach P, merged they formed a route; κ rose in 53 group × threshold cases, 2 of them at `all`).
That merge is dropped, and the unmerged (stubs-dropped) graph is in the minimum so that merging
can only lower the bound. *Alternative not taken:* the exact "cut a cluster at cost 1" problem
(NP-hard in general).

**D18. Cut vertices at every threshold** (`cut_vertices_<θ>`), not only at `all`, because classical
gharib claims are about the sound routes.

## Derived grade and comparisons

**D19. Discontinuity cap.** A chain that does not reach P through a companion, or contains a break
marker, cannot be placed above code 2 (`structure.yaml: derive.discontinuity_cap_code`); the best
chain is chosen among continuous companion-ending chains when any exist (`derive.prefer_continuous`;
2,976 groups fall back, flagged). The brief's v1 has no rule for breaks, and without one a mursal
chain of thiqat would derive صحيح. *Alternative:* no cap (set to null).

**D20. Level → code mapping:** 1–3 → 0, 4 → 1, 5–9 → 2, 10 → 3, 11 → 4, 12 → 5 (Nuzha: hasan
li-dhatihi is the khafif al-dabt level, 4; su' al-hifz, level 5, is a cause of weakness that can be
lifted). *Alternative:* 5 → 1. In `grades.yaml: levels`.

**D21. The max_rank gate compares like with like.** `sanads.max_rank` includes pos 0 (upstream
`meta`). Our weakest link over the whole stored chain equals it for 100% of chains (`agree_full`,
gated at > 99%). The derived chain grade excludes the compiler as the brief defines, which differs
from `max_rank` on 7,641 chains (1.32%): every one is a chain whose compiler is strictly its weakest
narrator, the single documented class, asserted in the gates. Read literally (derived grade vs
`max_rank` at > 99%), the brief's gate would sit at 98.68%.

**D22. Companion counts and the band.** Four counts are stored (see README). The gate compares
`companions_chain_end` with `sahaba_qty`: for the ten most-narrated groups upstream's recount ≤ ours ≤
declared, and corpus-wide (declared ≥ 10) our median ratio lies inside upstream's spot-check range.
Note: upstream's table puts group 1 at 64, not 63 (63 is group 2).

**D23. Group 0 and empty groups.** `meaning_groups` has 20,745 rows including id 0 (`غير منشور`); 462
have no hadith and one has hadith but no chain. All get a record with `status = 'no_chains'`.

## Gold set

**D24. Scopes and documented deviations.** Classical gharib claims are about a companion's sound
transmission; the data also carries routes the sources do not count, misresolutions and dropped
links. Each gold entry declares a scope (companion, threshold), lists every contradicting chain by
sanad id with a reason, and the test asserts the list is exact and that the documented structure
holds on the rest. *innama al-a'mal*: 14 of 335 'Umar chains (6 al-Qattan misresolution, 2 dropped
'Alqama, 5 via Muhammad b. 'Amr al-Laythi, 1 via a maqbul narrator). *Alternative:* assert on the
raw data (fails for data reasons the machinery cannot see); assert only at a threshold (misses the
misresolved thiqa chains).

**D25. Mutawatir groups.** A topic spans many meaning groups; we took the group with the most
companions for each al-Kattani topic. raf' al-yadayn in prayer is folded by the source into the
prayer-description group 4, so the entry uses group 31 (in du'a), also in al-Kattani. Citations
name the work; entries marked `confidence: medium` should be checked against a printed edition.

## Engineering

**D26. No rustworkx.** A unit-capacity node-split max flow (Edmonds–Karp, ~150 lines) runs the
whole corpus in ~25 s on 16 cores, with every flow checked by Menger (cut size = route count) and
tested against networkx on random graphs with cycles.

**D27. Determinism.** Node orders, condensation orders and DFS orders are sorted, so outputs are
identical across processes and `PYTHONHASHSEED` values (checked on the full run).

**D28. Fixture.** Gold groups + the ten most-narrated + 300 seeded random + 3 empty groups (333),
with every narrator in their chains plus all members of their name clusters, and the full `books`
and `book_compilers`. On these groups the fixture's records equal the full run's. 6.6 MB, 4.1 MB of
it hadith text (kept so `make ci` exercises word alignment and `itibar show`).

**D29. Not converted:** `group_embedding` (ML vectors; nothing here may depend on ML) and
`sqlite_stat1`.

## PR 2 corrections (`docs/prompts/pr-2.md`, structure version 2)

**D30. κ_lower gains a third hypothesis: continuity-incompatible links removed** (`kappa_nocompat_θ`,
`kappa_lower_source_θ`). The gold set showed the identity error that inflates κ most is a
different full name resolved to the wrong person (al-Qattan for al-Ansari, al-Bahrani for
al-Qurashi, 'Umara b. 'Umayr for 'Umara b. al-Qa'qa'), which same-name merging cannot see; such a
narrator usually sits in the wrong generation for his teacher or student. The nocompat graph is
the unmerged graph (stubs dropped) with every edge the continuity rule (D32) marks incompatible
removed; it drops *edges*, so a chain's compatible segments still count, and it shares one
function (`structure.link_continuity`) with the `drop_incompatible` scope, which drops whole
chains. 10 of the 10 documented cross-name chains are caught (audit §8.4); the candidate in
`la-yuminu-ahadukum` (Sa'id b. Bashir for Ibn Abi 'Aruba) sits in a plausible generation and is
not. At `everyone` κ_lower < κ in 2,436 groups (5 in PR 1), 2,432 of them through nocompat; 1,020
groups with κ ≥ 1 have κ_lower = 0. The source label takes the first minimum in the order
unmerged, merged, nocompat; since removing edges never raises κ, nocompat ≤ unmerged always, so
`unmerged` means neither other hypothesis lowered κ. Note: the data gives al-Taymi d. 119 (Taqrib
120), so PR 1's rule already flagged the al-Qattan link; what changes is that the flag now lowers
the bound. *Alternatives:* drop whole chains with an incompatible link (discards their sound
segments); keep κ_nocompat as a separate column outside the minimum (the paper would quote a bound
that ignores the error class it knows about); give incompatible edges a reduced capacity (no
principled value).

**D31. Why κ is zero, and routes without a continuous chain** (`kappa_zero_reason`). Precedence:
`no_chains`, `no_companion_end`, `broken_only`, `other`; `other` is gated at 0 and is 0 (at
`everyone` nothing is dropped by grade, so a continuous chain is always a route). Groups without
chains keep `kappa_all` null (no bundle) but get the reason, so the reason covers 3,421 groups:
463 + 2,958 of the 20,282 with chains. `n_chains_broken` counts chains with any break marker,
including an irsal marker at the chain end (`n_connected_chains` from PR 1 is renamed
`n_chains_connected`). The converse of the gate does not hold: 13 groups have κ = 1 with no
continuous chain, because chains broken at different places cover each other in the union graph
(group 7978: one copy of the isnad has an inqita' marker mid-chain, another a ta'liq at the
compiler's end). We keep them: routes are paths in the bundle by definition (README), and
`n_chains_connected` / `bypass_chains` count attested chains. *Alternatives:* require each route to
be attested by one chain (a different, chain-level measure, not κ); set κ_all = 0 for groups without
chains (conflates "no data" with "no route").

**D32. Continuity: seniors from juniors, and an age of hearing** (`continuity.tabaka_window:
[−1..4]`, `continuity.min_hearing_age: 5`). A gap of −1 is a senior narrating from a junior
(*riwayat al-akabir 'an al-asaghir*), a recognised pattern; −2 and below stay incompatible. With
years known, a link is compatible iff death(teacher) − birth(student) ≥ 5; PR 1's death ≥ birth
passed a student born the year his teacher died. Five is the youngest age the classical sources
accept for hearing (al-Bukhari's chapter "متى يصح سماع الصغير", on Mahmud b. al-Rabi' remembering
at five). Effect on 3.74M chain links: incompatible by tabaka 56,322 → 34,016 (−1 now accepted);
by years 16,375 → 24,621 (8,246 links at 0–4 years). The new flags catch known dropped links that
PR 1 passed: in group 376, Anas (d. 93) → Malik (b. 89) directly, where al-Zuhri is missing; also
'Abdullah b. Sa'd (d. 59) → Qatada (b. 61). The −2 bound also flags some narrations between
contemporaries the source places two layers apart (e.g. Ibn Akhi al-Zuhri, layer 7, → Ibn Ishaq,
layer 5). *Alternatives:* min_hearing_age 10 (the stricter view, also classical; 46,157 more links
at 5–9 years would flip) or 0 (PR 1); window [−2..4] (accepts those contemporaries but also
students placed two generations early); a per-region age (Kufan, Basran practice differed; no
regional data here).

**D33. Young companions at rank_no 3–4 are companions** (`grades.yaml: companion.label_overrides`:
`صحابي صغير`, `صحابية صغيرة`). The brief counted nine such narrators; the data has eleven at rank_no 3
(8) and 4 (3), of whom eight end a marfu' chain (162 chain ends; audit §2.1), e.g. Zaynab bt. Umm
Salama (92). Their chains now get a PROPHET edge; κ_everyone = 0 groups fall from 2,963 to 2,958
and the companion band gate still holds (median ratio 0.846). Companionship only: their ordinal
still follows rank_no (D1), so the three at rank_no 4 drop out at `thiqa_up`. Disputed
companionship (`مختلف في صحبته` and variants: 31 at rank_no 1, 108 elsewhere) is not overridden and
follows rank_no. *Alternatives:* raise the override narrators to ordinal 12 (all companions are
'udul in the classical view; not taken because grades are the source's, D1, and the brief scoped
this to companionship); treat disputed companionship as companionship (admits narrators the
source itself places among the Successors) or never (drops 31 the source places at level 1).

**D34. Taqrib-only width** (`width_taqrib`, `layers.taqrib_max_layer: 12`; fig2). Layers 13–38 are
later compilers and quoters: their width counts how many books carry a report, not how it was
transmitted, and it dominated the right of the PR 1 heatmap. `width_profile` keeps every layer,
and fig2's CSV keeps every layer (`plotted` marks 1–12). *Alternatives:* cut at each book's
compiler (varies per chain; the compiler node already isolates it); plot layers 13+ in a separate
panel (they answer a different question, book coverage).

**Gold note.** Misresolution deviations now carry `misresolution: {resolved, intended}`, and
`la-yuminu-ahadukum` records `candidate_misresolution` (Sa'id b. Bashir r3306 for Sa'id b. Abi
'Aruba r3281 under Qatada) for the name-resolution work of a later bucket. No assertion changed;
all 22 entries pass unchanged under structure version 2.



## Bucket 2

Classical sources were fetched from Shamela (public read-only MCP server) and matched character for
character against the page; the README quotes each rule with its page. Where a source differs from
the brief's attribution, the entry says so (D55).

**D35. Weakness classes by Taqrib level** (`grades.yaml: weakness`). Light (repairable): 5, 6, 7, 8;
unrepairable: 9; fatal: 10, 11, 12 — the brief's decision, encoded as data. Unrepairable and fatal
both keep the v1 code; they differ only in name (`not_repairable` vs `fatal` in the receipt). Level 9:
the *Nuzha* likens the majhūl al-ʿayn to the mubham («كالمبهم») and names the mastūr, not him, among
those repaired; it never says in so many words that he cannot be repaired (the brief's "explicit
statement" is an inference from the list). `light_includes_level_8: true`: Ibn Hajar's repaired
class is the poor-memory narrator, and level 8 is «ضعيف» without a stated cause. *Alternatives:*
level 8 unrepairable (`no_level_8` variant: 72.15% agreement against 72.86%); level 9 light (the view
that a majhūl is strengthened by a follow-up; not taken, it contradicts «كالمبهم»).

**D36. Structural defects.** Mursal (no companion at the top, or an irsal marker there) and a
mudallis's muʿanʿan link (`has_tadlis` and the word before the teacher in `continuity.muanan_words`)
are light; inqiṭāʿ and taʿlīq markers are fatal, as the brief decides; an irsal marker anywhere but the
top (9 chains) is treated as a break. An unnamed person in the companion slot (5,040 chain tops) is
read as a mursal (`top_mubham: mursal`): he may be an unnamed companion, whose anonymity does not
harm, or a Successor, which makes the chain mursal; below the companion slot an unnamed person or an
undescribed narrator (stub) is unrepairable (`weakness.unknown`), as the mubham «لا يقبل … ما لم يسم».
The mudallis's node is the avoided position (a node-disjoint route cannot see the link word).
**Consequence:** 372 groups v1 grades 0 get a higher v2 code, 271 of them only because of a
mudallis's ʿan (al-Aʿmash, Qatāda, Hishām b. ʿUrwa, Abū Isḥāq …): a light defect reaches ḥasan
li-ghayrihi at most, while the classical treatment accepts the ʿan of the first two of Ibn Hajar's
five tiers of mudallisūn and of mudallisūn in the Ṣaḥīḥayn. The source's binary `has_tadlis` carries
no tiers. *Alternatives:* tiered tadlīs (needs Ibn Hajar's *Ṭabaqāt al-Mudallisīn* joined to `rawis`, a
name-matching task left for later); top unnamed person as an unnamed companion (accepted) or as an
unknown narrator (unrepairable).

**D37. The positions a corroborating route must avoid** (`derive.corroboration.avoid: weakest`). The
brief: "a chain c whose weakest positions form the set W". Default: the light-defect narrators of
the lowest grade; with none (a chain of good narrators with a mudallis's ʿan, or a mursal), the
structural defects. I first generalized this to every light-defect position, on the reasoning that a
route sharing a second light narrator leaves his weakness uncorroborated; under that rule v2
agreement fell below v1 (70.32% `ibn_hajar` against 72.35%). The brief states its definition, so the
default follows it (72.86%), and the generalization is kept as the `all_light_defects` variant with
its number. Recorded plainly: the switch was made after seeing the agreement figures, back to the
brief's text, not to a new rule. *Alternatives:* `all_light_defects` (stricter; above).

**D38. The corroborating route** (`witness_threshold: above_matruk`, `witness_min: light`,
`min_corroborating_routes: 1`). A PROPHET → book route in the bundle with W removed, in the threshold
graph at max(above_matruk, the lowest light level's ordinal): its narrators are light-or-better, as
the brief requires ("whose own attested chain grade is light-or-better"). The witness recorded is an
attested light-or-better chain avoiding W where one exists (80.6% of upgrades), else one route of the
flow, flagged `witness_attested = false`: a route spliced from chains is accepted as corroboration,
as in the κ definition. «فوقه أو مثله لا دونه»: the default reads "light-or-better" as the brief does;
the `witness_not_below` variant requires the witness's grade ≥ the chain's (72.95%). One route
suffices; Ibn Hajar's ṣaḥīḥ li-ghayrihi speaks of «كثرة الطرق». *Alternatives:* attested witnesses
only (rejects spliced routes); `min_corroborating_routes: 2` for ṣaḥīḥ li-ghayrihi.

**D39. Rulesets** (`derive.rulesets`). `ibn_hajar`: weakest level ≤ 3 → 0, ≤ 4 → 1, ṣaḥīḥ li-ghayrihi
from a ḥasan li-dhātihi chain with an independent route of ḥasan-or-better grade avoiding its weakest
ḥasan-level narrators. `ibn_al_salah`: the same with level 5 at the ḥasan level, his siwāk example.
The independent ḥasan route is sought in the graph of narrators at or above the ruleset's ḥasan
level, and an attested witness must be defect-free. Ḥasan li-ghayrihi is never raised further (Ibn
Hajar: it stays below ḥasan li-dhātihi, «مُنْحَطٌّ عن رُتْبَةِ الحَسَنِ لِذَاتِه»). Both rulesets run on every
chain; records carry both codes; `derive.ruleset` names the default shown by `itibar show` and used
by the chapter census.

**D40. Mursal rules** (`derive.corroboration.mursal_rule`). `ibn_hajar` (default): any connected
light-or-better route repairs a mursal, including one through the mursil himself (classed `wasl`).
`shafii` (variant `mursal_shafii`): the witness must avoid the mursil — musnad by others («فإن شركه
فيه الحفاظ المأمونون فأسندوه») — or be a mursal whose mursil is a different person. al-Shāfiʿī also asks
that the second mursil took from teachers other than the first's («من غير رجاله»); a mursal chain names
no teacher above the mursil, so "a different mursil, sharing no node with W" stands in for it, and
his further conditions (companions' sayings, the fatwas of scholars, the mursil being a senior
Successor who names reliable people) are not encoded. Agreement: 72.33%.

**D41. Divergence classes.** Read relative to the chain's topmost avoided position (for a mursal with
nothing to avoid, the mursil): the deepest node the witness shares above it decides tāmma (the weak
narrator's own teacher, same companion) vs qāṣira (higher, same companion); another companion is a
shāhid (the *Nuzha*'s definitions, README). `wasl` names a witness through the mursil of a mursal.
*Alternative:* classify relative to the lowest avoided position (would call more follow-ups tāmma).

**D42. Group grade v2 = the lowest v2 code over all chains**, ties: continuous, higher chain grade,
lower sanad_id (v1's order). v1 restricted the choice to continuous chains first; v2 does not,
because a corroborated mursal (code 1) must be able to beat an uncorroborated continuous chain (2).

**D43. Number class on the width profile** (`number_class.tawatur_n: 10`). As the brief defines it:
Taqrīb layers 1–12 at `all`, compiler roles excluded, min over the layers that have a narrator. Routes
skip layers on this scale (D9), so a layer is a cut only when every route has a narrator in it: 4,401
groups read gharīb by width with κ_all ≥ 2, and the two readings differ in 31.5% of groups. Both are
recorded. `lā yuʾminu` reads ʿazīz only when scoped to Ibn Hajar's two companions (the whole group
folds in other reports and has one narrator at layer 2); group 273 («إن الله لا يقبض العلم انتزاعا»)
is gharīb nisbī by width (Shaqīq alone at layer 2) and mashhūr by κ. *Alternative:* count only layers
that are cuts of the on-path graph (closer to the classical "every ṭabaqa" reading of the chain's
generations; not the brief's definition, left for a later structure version).

**D44. Qarāʾin flags.** `books.id` 1 = Ṣaḥīḥ al-Bukhārī, 2 = Ṣaḥīḥ Muslim (verified in the audit, §11);
`huffaz_chain` counts companions (level 1) as ḥuffāẓ-level and requires every graded narrator to be
level ≤ 2, so a chain of thiqāt (level 3) does not qualify; `sound_distinct_routes` reads "distinct
routes free of weak narrators" as κ at `saduq_up` ≥ 3. Flags are never combined.

**D45. al-Suyūṭī's list is reconstructed from al-Kattānī** (`lists/suyuti.yaml`). *al-Azhār
al-Mutanāthira* is not in Shamela's catalogue (title and content search) or on usul.ai. al-Kattānī
states in his introduction that he included every hadith of al-Azhār and marked each with «أورده في
الأزهار من حديث فلان», listing the companions al-Suyūṭī counted «مسقطاً لما ذكره من المخرجين». The parser
finds 111 marked entries (al-Kattānī counted 112 where al-Suyūṭī stated 100). Each entry keeps
al-Kattānī's page; `index` is the order of appearance in al-Kattānī, not al-Suyūṭī's numbering;
`cited_sources` is null. *Alternative:* wait for a scan of a printed edition (the brief allows the user
to supply one; the file is built to be replaced).

**D46. Parsing al-Kattānī** (`lists.parse_kattani`). Entries are the lines «N- …» in Arabic-Indic
numerals; 84, 187 and 265 are absent from the print and 238 and 267 are printed twice (keys `238b`,
`267b`; the first 238 is a cross-reference). Kind: `wording` for a parenthesized text; `topic` for an
unparenthesized heading, a parenthesized one opening «أحاديث», or one al-Kattānī introduces with the
feminine «أوردها في الأزهار»; `cross_reference` for a short entry pointing back («تقدم»). Narrator
counts are the highest number in his numbered lists; al-Suyūṭī's count is the number word before
«نفسا / أنفس» in the marked segment. Cited works are found with a fixed vocabulary (it may also catch a
critic named in discussion). *Alternative:* hand-transcription (not reproducible).

**D47. Matching and the auto rule** (`config/structure.yaml: lists`). Deterministic token overlap
only: idf-weighted containment of the entry in each member matn and the group's nass, a contiguous
opening phrase, and relative support. Auto-confirm requires a quoted wording of ≥ 4 tokens, score ≥
0.85, margin ≥ 0.25 and ≥ 3 supporting matns. The support floor was added after a spot check found
«شفاعتي يوم القيامة حق» auto-matched through a single long matn of another group (relative support
alone was 1 of 1). Entries whose data group folds in several reports can still auto-match a broader
group (entry 98, the fever wording, sits in group 124 on heat and prayer, with 92 matching matns);
the review column is where a reader corrects that. The pipeline never writes a `human` row.
*Alternatives:* a lower margin (more auto rows, more false ones); group-nass-only matching (fails
*man kadhaba*, whose group nass opens «لا تكذبوا علي»).

**D48. Bins** use κ at `all` against tawatur_n, and the companions count beside it. An entry without
a confirmed group is `unmatched` whether no candidate exists or review is pending; the report counts
pending entries separately. The auto rule maps one group per entry, so `meaning_only` needs human
multi-group rows.

**D49. Pools** are the same builder over the union of chains (group id −1); topic pools take every
group under the node through the nested set. A group under several topic nodes counts in each.

**D50. Collection classes** for the common-link distributions are groups with at least one chain in
the Ṣaḥīḥayn, in a `tasnif_no = 1` book, or any group. *Alternative:* rebuild each bundle from that
class's chains only (asks "where is the common link of the Ṣaḥīḥayn's own routes"; a different
question).

**D51. Compiler-narrators stay terminals in the census** (D14). Mālik ranks 131st among non-companion
common links: in 653 of his 1,155 groups his node is also the compiler of the *Muwaṭṭaʾ*, and a
narrator acting as a compiler is never a single strand or partial common link. The others the brief
names rank 6th (al-Zuhrī), 18th, 26th and 37th below the companions, and are partial common links in
598–1,090 groups each; they lose the common-link label to the companions above them, since a common
link is the uppermost partial common link. *Alternative:* count a compiler-narrator's narrator-role
branches (changes partial common links corpus-wide; left for a later structure version).

**D52. `kappa_nocompat_years_θ`** removes only the years-rule incompatible links (both dates known);
κ_lower keeps the all-incompatible graph, as the brief asks. It lowers κ_everyone in 732 groups,
against 2,436 for all incompatible links.

**D53. Gold error rate** (audit §10). Computed from the existing fields, without editing the entries:
a deviation is a misresolution if it carries `misresolution`, a dropped link if its reason says
"dropped link"; other documented routes are not errors. Only the four entries inspected chain by
chain count (`deviation_key`); entries that reuse a scope (`scope_from`) are not double-counted.
Result: 14 of 843 chains (1.66%).

**D54. Gold choices.** *Sandals dowry* (group 2031): the brief expected corroboration to fire; inside
the meaning group it cannot (47 of 51 chains through ʿĀṣim; the other four are a different report).
Ibn Hajar (*al-Nukat* 1/388–389) says al-Tirmidhī graded it ḥasan «لمجيئه من غير وجه», and al-Tirmidhī's
other routes are his «وفي الباب» reports from other companions — separate reports, other groups. The
entry asserts what the data supports (ʿĀṣim level 8, ḍaʿīf under both rulesets) and records the
classical claim beside it (`classical_claim_holds_in_group: false`). The example is in *al-Nukat*, not
the *Nuzha* as the brief says. *Maqbūl*: group 3487 (al-Tirmidhī's «التاجر الصدوق الأمين», which he calls
ḥasan and knows only through Abū Ḥamza ʿAbdallāh b. Jābir, level 6); al-Ḥākim's chain follows Abū
Ḥamza from his own teacher through Isḥāq b. al-Rabīʿ (level 4): mutābaʿa tāmma, by a narrator above
him. *Fatal*: group 7688, the Kitāb al-ʿAql chains, which al-Dāraqutnī traces to Maysara b. ʿAbd Rabbih,
Dāwūd b. al-Muḥabbar and Sulaymān b. ʿĪsā al-Sijzī (via Ibn Taymiyya, *Bughyat al-Murtād* 173) — exactly
the level-12 narrators of its two routes. *Mashhūr*: group 218, Ibn al-Ṣalāḥ's «مشهور بين أهل الحديث
وغيرهم» (naw' 30); width 9 at its narrowest layer, κ_all 19. *Gharīb not in the Ṣaḥīḥayn*: group 3487
scoped to Abū Saʿīd. New entries reuse an existing scope with `scope_from`; no existing entry changed.

**D55. Source corrections to the brief.** (1) Fatḥ al-Bārī (Salafiyya, 1/11) contains neither
«مشهور بالنسبة إلى آخره غريب بالنسبة إلى أوله» nor «أكثر من مائتي إنسان أكثرهم أئمة»; Ibn Hajar there
writes that the hadith «اشتهر عن يحيى بن سعيد وتفرد به من فوقه». The second phrase is al-Nawawī's (*Sharḥ
Muslim* 13/54); the first is in Ibn Daqīq al-ʿĪd and in al-ʿIrāqī quoting al-Nawawī. (2) The *Nuzha*
reads «باعتبار المجموع», not «بالمجموع». (3) al-Suyūṭī's ten-companion criterion is known here only
through al-Kattānī and *Kashf al-Ẓunūn* (his *Tadrīb* gives al-Iṣṭakhrī's «أقله عشرة»). (4) The Taqrīb's
twelve levels are quoted from *Taḥrīr al-Taqrīb*, Shamela's copy of the Taqrīb lacking its introduction.
(5) The sandals example is in *al-Nukat*, not the *Nuzha* (D54).
