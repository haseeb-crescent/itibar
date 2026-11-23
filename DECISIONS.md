# Decisions

Every choice the data forced that the bucket-1 definitions (and the PR 2 corrections,
`docs/prompts/pr-2.md`, D30–D34, bucket 2, `docs/prompts/bucket-2.md`, D35–D55, and the PR 5
corrections, `docs/prompts/pr-5.md`, D56–D68, PR 6, `docs/prompts/pr-6.md`, D69–D79, the site, `docs/prompts/site.md`,
D80–D82, PR 7, `docs/prompts/pr-7.md`, D83–D96, and the reading layer, `docs/prompts/site-ux.md`, D97–D105) did not settle, with
the alternatives.
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
harm, or a Successor, which makes the chain mursal (*amended by D69–D70, PR 6: a top unnamed person whose
designation in the text is a companion's is an unnamed companion; `top_mubham` now governs only the rest*); below the companion slot an unnamed person or an
undescribed narrator (stub) is unrepairable (`weakness.unknown`), as the mubham «لا يقبل … ما لم يسم».
The mudallis's node is the avoided position (a node-disjoint route cannot see the link word).
**Consequence:** 372 groups v1 grades 0 get a higher v2 code, 271 of them only because of a
mudallis's ʿan (al-Aʿmash, Qatāda, Hishām b. ʿUrwa, Abū Isḥāq …): a light defect reaches ḥasan
li-ghayrihi at most, while the classical treatment accepts the ʿan of the first two of Ibn Hajar's
five tiers of mudallisūn and of mudallisūn in the Ṣaḥīḥayn. The source's binary `has_tadlis` carries
no tiers. *Alternatives:* tiered tadlīs (needs Ibn Hajar's *Ṭabaqāt al-Mudallisīn* joined to `rawis`, a
name-matching task left for later); top unnamed person as an unnamed companion (accepted) or as an
unknown narrator (unrepairable).

**D37. The positions a corroborating route must avoid** (`derive.corroboration.avoid: weakest`). *Superseded by D59
(PR 5: `each_defect`; `weakest` is kept as a variant).* The
brief: "a chain c whose weakest positions form the set W". Default: the light-defect narrators of
the lowest grade; with none (a chain of good narrators with a mudallis's ʿan, or a mursal), the
structural defects. I first generalized this to every light-defect position, on the reasoning that a
route sharing a second light narrator leaves his weakness uncorroborated; under that rule v2
agreement fell below v1 (70.32% `ibn_hajar` against 72.35%). The brief states its definition, so the
default follows it (72.86%), and the generalization is kept as the `all_light_defects` variant with
its number. Recorded plainly: the switch was made after seeing the agreement figures, back to the
brief's text, not to a new rule. *Alternatives:* `all_light_defects` (stricter; above).

**D38. The corroborating route** (superseded by D56 for what counts as a witness; the floor is unchanged) (`witness_threshold: above_matruk`, `witness_min: light`,
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

**D43. Number class on the width profile** (`number_class.tawatur_n: 10`). *Superseded by D60 (PR 5: the class
is read on κ; the width reading is kept as `number_class_width`).* As the brief defines it:
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

**D51. Compiler-narrators stay terminals in the census** (D14). *Superseded by D61 (PR 5).* Mālik ranks 131st among non-companion
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


## PR 5 corrections (`docs/prompts/pr-5.md`; derive version 3, structure version 4)

The corrections are applied cumulatively in the brief's order, each one a config switch whose PR 4 value is kept
(`config/stages/`, `make stages`); stage 0 reproduces PR 4's records exactly and audit §11.1 tabulates every stage.
Classical passages were fetched from Shamela and checked character for character against the page text by a
separate pass; the README quotes each with its page.

**D56. A witness is one attested chain** (`derive.corroboration.witness: attested`). A mutābaʿa or shāhid is a
narration recorded in a chain, so a witness is one `sanads` row: continuous (companion end, no break marker),
light-or-better itself (no fatal or unrepairable defect), and carrying none of the nodes to cover. PR 4 accepted
any union-graph route at the light floor, and 19.4% of its upgraded groups rested on a route spliced from several
chains. The graph test still runs and is stored (`witness_route_exists_v2_<rs>`, `route_exists_v2_<rs>` per chain):
in the final run 1,519 of 24,508 ḍaʿīf chains (125 of 5,441 ḍaʿīf groups) had a route but no chain. Effect alone
(stage 1): upgraded groups 3,730 → 3,310, the block *ours 1 / source 3–5* 562 → 457. `min_corroborating_routes: k`
now means k distinct attested chains. *Alternatives:* `witness: route` (PR 4); requiring k pairwise vertex-disjoint
attested chains for k ≥ 2 (not needed at the default k = 1).

**D57. Tiered tadlīs** (`derive.tadlis`, `lists/mudallisin*`, `src/itibar/mudallisin.py`). Ibn Hajar's *Ṭabaqāt
al-Mudallisīn* (*Taʿrīf Ahl al-Taqdīs*) is Shamela book 1186 (ed. ʿĀṣim al-Qaryūtī, 1983): 152 entries in five tiers
(33, 33, 50, 12, 24, as the tier heads print them); the editor's appendix of 22 further names is not Ibn Hajar's and is
left out. Matching to `rawis` is deterministic (idf-weighted name tokens, article-insensitive, compound names as units,
nickname in the entry head, a prolific-narrator tie-break) with two auto rules: (a) score ≥ 0.7, margin ≥ 0.15 and
ism + father agreeing; (b) ism + father agreeing, score ≥ 0.6, margin ≥ 0.1 and the source's own `has_tadlis` flag on
the candidate and on no namesake (two independent sources agree). 92 entries are auto-confirmed, 60 wait for the
reviewer in `lists/mudallisin_confirmed.csv` (`human` rows are the user's and are never written by the pipeline).
Of the 83 narrators the source flags, 58 are matched (tier 1: 4, 2: 8, 3: 25, 4: 10, 5: 11); 25 are not, among them
al-Ḥasan al-Baṣrī (tier 2 in the book; his data name «حسن بن يسار» does not match Ibn Hajar's «الحسن بن أبي الحسن» on
ism + father) and al-Ḥakam b. ʿUtayba (two flagged namesakes) — they take `untiered_tadlis: 3`. Rules:
tiers 1–2 accepted; tier 3 a light defect unless covered; tiers 4–5 a defect unless covered, unrepairable by
corroboration (`tier_4_5: not_repairable`: the chain keeps code ≥ 2). **Covered**: the same teacher → student link
carries a hearing word (`hearing_classes`: ḥaddathanā, akhbaranā, anbaʾanā, samiʿtu — the *Nuzha* says anbaʾanā is
ikhbār in the early usage and ijāza only for the later; qirāʾa is left out because its marker «على» is ambiguous) in
another chain of the report (`tasrih_scope: group`), or anywhere (`corpus`, variant). **Ṣaḥīḥayn**: a mudallis's ʿan in
a chain of al-Bukhārī or Muslim is no defect, and that link then counts as established for the report's other chains
(al-Nawawī: their muʿanʿanāt are carried «على ثبوت السماع من جهة أخرى», i.e. hearing of that report was established).
The 271 ʿan-only downgrades of PR 4 (stage 2): 122 back to code 0 by the tier, 9 by the Ṣaḥīḥayn convention, 6 by
a hearing word elsewhere in the report; 74 ḥasan li-ghayrihi, 57 ḍaʿīf (tier 3 or untiered, uncovered), 3 not
repairable (tier 4–5). **Source correction:** the brief has tier 5 "rejected unless explicit hearing is shown"; Ibn
Hajar's tier 5 is «من ضعف بأمر آخر سوى التدليس فحديثهم مردود ولو صرحوا بالسماع» — rejected even with hearing, for the
other weakness, which itibar already carries as the narrator's level; the ʿan rule applied to tier 5 is tier 4's.
**Who is a mudallis** (`mudallis_set: source_flag`; *amended by D76, PR 6: the default is now `union`*): the
narrators the source flags; the book gives their tier. 34
narrators matched to the book are not flagged by the source (al-Zuhrī among them, tier 3): adding them
(`mudallis_union`, variant) makes every uncovered ʿan of theirs outside the Ṣaḥīḥayn a defect (agreement 70.96%
against 71.21%). The source's flag is its editors' verdict on the narrator (D1), and Ibn Hajar's placement of al-Zuhrī
in tier 3 is itself disputed. *Alternatives:* `tasrih_scope: corpus` (72.37%), `tier_4_5: light`, `mudallis_set: union`,
`tiers: false` (PR 4).

**D58. Shawāhid from sibling groups, and the overlap floor** (*amended by D75, PR 6: `shahid_scope: group` is the
default and `siblings` a variant; the floor below is unchanged*) (`shahid_scope: siblings`, `shahid_min_overlap: 0.32`,
`src/itibar/siblings.py`, `src/itibar/matn.py`). A group's rows in `topics` are always leaves; the brief's "leaf
topic node(s)" are read as their parents, the lowest topic nodes holding the report, and the siblings of g are the
other groups under any of them. A sibling witness is classified exactly as in its own group (a first pipeline pass
computes, per chain and per parameter set, whether it can lend a light-or-better or a ḥasan-or-better witness), must
avoid the positions to cover, and its matn must overlap the chain's matn. **The measure was changed after inspection.**
The idf-weighted overlap coefficient |A∩B| / min(|A|, |B|) (the lists matcher's containment, made symmetric in the
denominator) was inspected first on 30 pairs, three per decile: it scores a three-word fragment contained in a long
text near 1, and 5 of the 15 pairs at ≥ 0.5 were different reports. The idf-weighted Dice coefficient
2|A∩B| / (|A| + |B|) does not; 20 more pairs were drawn in pre-set bands of 0.06 between 0.20 and 0.50 to place the
floor. **Rule:** the lowest band in which at least four in five inspected pairs carry the chain's content in whole or in
part — 0.32 (bands below: 60%, 75%; at 0.32–0.38: 80%; above 0.38: 93%). Recorded plainly: the sandals pair (gold,
0.333) was known when the rule was set; under the stricter "nine in ten" rule (0.38, variant `shahid_strict`) it is
not repaired. One inspected pair whose witness negates the chain («لا يصافح النساء») scores 0.60: token overlap cannot
read meaning, and the floor bounds that error without removing it (reports/shahid_inspection.md). A cross-group
witness is always classed shāhid and flagged (`witness_group_v2_<rs>`, receipt `cross_group`), as the brief decides;
17.6% of them come through the same companion as the chain (a mutābaʿa by the *Nuzha*'s definition, filed by the
source as another report). Sibling search runs only for a position the group cannot cover. Agreement: 71.21% with,
71.80% without (`shahid_group`), 71.53% strict. **Fixture:** it carries the siblings of the gold entries that assert a
cross-group shāhid, and the full corpus's idf for its matns; other fixture groups lack their siblings, so their v2 can
differ from the full run where a cross-group witness decided it. *Alternatives:* the overlap coefficient; containment
of the chain's matn in the witness's; a floor of 0.26 or 0.38; siblings at the grandparent topic node.

**D59. Every light defect covered** (`avoid: each_defect`). «ومتى تُوبعَ السَّيِّئُ الحِفْظِ بمُعْتَبَرٍ» read for each
defective narrator: every light-defect position, and every structural light defect (a tier-3 ʿan, the mursal), needs a
witness of its own avoiding it; witnesses may differ per defect. The mursal's witness avoids nothing under
`mursal_rule: ibn_hajar` (any connected chain repairs it) and the mursil under `shafii`. The ṣaḥīḥ li-ghayrihi step
applies the same reading to the ḥasan-level positions. The summary witness recorded for a group is the one covering the
topmost position (D41). Effect alone (stage 4): 73.21% → 71.09%; 941 of the 2,492 ḥasan li-ghayrihi groups' v2 chains
needed more than one witness. *Alternatives:* `weakest` (PR 4, 73.34%) and `all_light_defects` (one witness avoiding
all, 71.21% — it differs from `each_defect` on 481 chains but only 4 groups' v2 chains).

**D60. Number class on κ** (`number_class.basis: kappa`). Tafarrud is one man through whom every route passes, a cut
vertex: `number_class` = the cut points on κ_all; gharīb muṭlaq when a companion is among the cut vertices, else nisbī
(`gharib_cut_kind` names the topmost cut vertex's kind). 14 gharīb groups have only compiler cut vertices (every route
ends in one compiler's books): their tafarrud is the compiler's, and they read gharīb nisbī. The width reading is kept
as `number_class_width` (diagnostic, D43); the two differ in 31.5% of groups. `huffaz_chain` (not gharīb) now reads the
κ class: 733 → 1,185 groups. Gold: *innamā* (scoped) stays gharīb muṭlaq (ʿUmar a cut vertex), *lā yuʾminu* (scoped)
ʿazīz, *man kadhaba* mutawātir; *al-muslim man salima* (group 218), asserted mashhūr by width in PR 4, is mutawātir by
κ (κ_all 19) — the width assertion is kept beside the new one. *Alternative:* `basis: width` (PR 4).

**D61. Compiler roles per edge** (`structure.compiler_terminal: edge`). A narrator who compiled a book of the group
(or transmitted it, D62) is terminal only on his edge into that book. For single strands his in-degree counts his
narrator-role in-edges only (the many teachers feeding his own book do not make him a branching point); his out-edges
all count, so a compiler with his book and one student has two branches. A narrator with only a compiler role is
neither a single strand nor a branching point (as before); a branch into him qualifies directly when he compiled the
report from that teacher (`role_in`). The bundle records role and narrator-role adjacency per chain occurrence
(`role_edges`, `role_in`, `nr_in`, `nr_out`). Effect on the census: Mālik 131st → 40th below the companion layer
(partial common link in 677 groups against 99), al-Zuhrī 6th → 1st, Qatāda 18th → 5th, al-Aʿmash 26th → 11th, Shuʿba
37th → 17th; (group, common link) pairs 25,387 → 21,408 and the companion share 41.7% → 51.1%, because compilers who
also teach now count as branching, more branches above them qualify, and the uppermost partial common link moves up.
No group grade changes (stage 5). A compiler failing a threshold keeps exactly his role edges (PR 4 kept every edge
into any compiler node); a role edge shared with a narrator-role occurrence could carry a failing author's material to
the transmitter's other students (A → X → Y); the data has no such case at any threshold that matters (both book
authors with a transmitter are level 2). *Alternative:* `node` (PR 4, D14, D51).

**D62. Book transmitters** (`bundle.book_transmitters`, `book_transmitter_min_share: 0.2`). A narrator at pos 0 while
the book's author (the narrator whose death year is `books.author_death_year` ± 1) sits at pos 1, in at least 20% of
the book's chains. Two books qualify, with shares 0.459 and 0.333; the next largest share in the corpus is 0.016:
*Musnad Ibn al-Jaʿd* (al-Baghawī transmits it; `book_compilers` named al-Baghawī its compiler — fixed: the compiler is
now ʿAlī b. al-Jaʿd, the PR 4 reading kept as `compiler_rawi_id_pos0`, `pos0_misidentified` true) and Aḥmad's *al-Waraʿ*
(Muḥammad b. Yaḥyā al-Warrāq, level 4, was graded as a narrator). The brief's examples are not of this shape here:
ʿAbd al-Razzāq himself is at pos 0 in 94.5% of the *Muṣannaf*'s chains, and Aḥmad in 99.4% of the *Musnad*'s. In every
chain of such a book whose pos 0 is the transmitter, he holds the role: exempt from thresholds, terminal on his edge
into the book, **excluded from the chain grade like a compiler** (the brief's "like a compiler"; D6), and so is the
author at pos 1. That adds a max_rank class, `book_role_strictly_weakest`, gated like `compiler_strictly_weakest`.
In the census his groups in that role only are not counted (`groups_book_transmitter_role`). 95 chains of *al-Waraʿ*
change chain grade; no group's v2 chain does. *Alternatives:* grade the transmitter (PR 4); a share of 0.1 or 0.5
(the same two books).

**D63. No agreement gate.** The v2 ≥ v1 gate is removed: agreement with the recorded grades is a reported result (audit
§11), never a test, because a gate that rewards agreement invites tuning (D37 recorded that pressure). In its place:
rule-consistency gates (fatal keeps the v1 code, unrepairable max(v1, 2), every upgrade names an attested witness, a
cross-group witness is a shāhid from another group, the number class follows κ), the synthetic tests of
`tests/test_pr5.py`, and the gold set. The final default agrees 71.21% (`ibn_hajar`) and 72.11% (`ibn_al_salah`)
against v1's 72.35%; PR 4 gave 72.86% and 72.37%.

**D64. The unnamed person named elsewhere** (`unknown_repair: named_elsewhere`). In PR 4, 569 disagreeing groups (626
weakest positions, the brief's count) had the unnamed person among the weakest positions of their v2 chain: 188 only
in the companion slot (read as mursal, D36), 381 below it. Ibn Hajar: «ويُستدَلُّ على معرفةِ اسمِ المُبْهَم بورودِه من طريقٍ أُخرى مُسَمًّى»; Ibn al-Ṣalāḥ: «وَيُعْرَفُ ذَلِكَ بِوُرُودِهِ مُسَمًّى فِي بَعْضِ الرِّوَايَاتِ». A mid-chain unnamed
person is covered when another chain of the same report has a named narrator between the same teacher and student
(in one chain: teacher, named, student consecutive); the position then takes that narrator's level — the weakest if
several are named there — and is graded like him (a light, fatal or ḥasan level as the case may be). Only 21 of the 381
mid-chain cases are named in their report; the companion-slot case stays mursal. Effect alone (stage 7): 34 groups
change, agreement 71.09% → 71.21%. *Alternatives:* `none` (PR 4); the best of several named narrators; naming across
the corpus (the same teacher and student in any report: not the classical identification of *this* man).

**D65. Whose verdicts the labels are** (audit §11.7, `src/itibar/provenance.py`). 40 narrators of al-Bukhārī or
Muslim (20 labelled «صدوق حسن الحديث», 20 other labels of levels 2–9; seeded), looked up in Shamela's *Taqrīb* (8609)
and *Taḥrīr al-Taqrīb* (127715); 29 read whole in both (6 not found by name search, 1 namesake rejected on tabaqa and
grandfather, 3 Taḥrīr entries cut by a page break, 1 found in the Taqrīb only). Where Taḥrīr revises Ibn Hajar
(«بل: …»), the label is Taḥrīr's revision in 7 of 7; where it does not, the labels other than the ṣadūq formula are Ibn
Hajar's wording in 12 of 13 (the 13th, «مختلف في صحبته», summarises the entry); the formula «صدوق حسن الحديث», Taḥrīr's
own (it writes it in its revisions), stands for Ibn Hajar's «صدوق» (5), a qualified «صدوق» (2), and twice a verdict of
another level («ثقة ورمي بالإرجاء», «لا بأس به»). Hence the README: for the Six Books' narrators the labels are
Taḥrīr's reading normalized by the source's editors; for the rest, the editors' own. The brief's premise holds with
that qualification. `in_taqrib` is **not stored**: the only
membership test available is name matching against the Taqrīb's ~8,800 entries, which is not reliable on this data
(the source spells names without the article and with full nasab, and namesakes abound — the 40-narrator lookups
themselves needed ism + father agreement and a manual read). *Alternative:* store a name-matched flag with its match
score (not done: a flag that is wrong a few percent of the time would be quoted as fact).

**D66. Engineering.** `ITIBAR_CONFIG_OVERRIDE` deep-merges a YAML over `config/` (the stage runs and the tests use
it). The pipeline makes a first pass over the groups that can lend a sibling witness (classification under every
parameter set) and pickles a compact sibling index the workers load; matn tokens and idf are built once
(`make matn`). A full run takes ~100 s on 16 cores (PR 4: ~60 s); `make stages` ~8 min. Outputs stay deterministic.

**D67. Gold changes.** Number-class assertions follow D60 (the three the brief names pass unchanged; *mashhur-al-muslim*
now asserts its width class and its κ class). *Sandals*: repaired with siblings (Sahl b. Saʿd's report, group 763,
overlap 0.333), and `alt_shahid_group` code 2 asserts PR 4's in-group finding (`classical_claim_holds_in_group: false`,
`classical_claim_holds_with_siblings: true`). New: *muanan-tier-2-in-muslim* (group 3, sanad 9756: Muslim ← … ←
al-Aʿmash ʿan Ibrāhīm, tier 2, no defect) and *muanan-tier-3-covered-by-tasrih* (group 7, sanad 74843: Aḥmad ← Ghundar
← Shuʿba ← Qatāda ʿan Anas, covered by «حدثنا» in al-Bukhārī's and Muslim's chains and «سمعت» in Ibn Manda's). 35
entries, all pass.

**D68. Version numbers.** `derive.version: 3`, `structure.version: 4` on every record; the old values are reproduced by
`config/stages/s0_pr4.yaml` (records otherwise identical: the stage-0 run matches PR 4's codes, rules and structure
group by group).


## PR 6 (`docs/prompts/pr-6.md`; structure version 5, derive version 4)

The changes are applied cumulatively in the brief's order as stages 8–11 (`config/stages/`; stage 7 is PR 5's
defaults and reproduces PR 5's records exactly); audit §11.9–§11.12 tabulates what each moved. Classical passages
were fetched from Shamela and checked byte for byte against the page text by a separate pass.

**D69. The unnamed companion: reading the designation** (`unnamed_companion`, `src/itibar/unnamed.py`). The mention
span in `hadith_rawis` is often the noun alone («رَجُلٍ»), the designation following it, so the designation is the
mention plus the words after it up to the next mention, a delimiter (، : ؛ .) or a transmission word (قال، أن، عن …),
at most 80 characters. Alignment as in `words.py`; unaligned chains take the hadith's last unnamed-person mention in
the sanad part (`sanad_fallback_mention`). Where the hadith has no unnamed-person mention at all
(`sanad_fallback_text`, 324 chain tops) the text before `matn_start` was read and found to be mostly the matn's own
opening (`matn_start` is approximate: «قال: لدغت رجلا عقرب فجاء النبي …»), so nothing is read as a designation there
(class `none_text`, treated as none). The phrase list was written after tabulating every designation (audit
Appendix B), from meaning, not from agreement: the brief's companion phrases plus the others the table shows that
designate someone who met the Prophet as a believer — his wives («أزواج النبي», «أمهات المؤمنين»), his servant and
collector, one who heard him, prayed with him, rode behind him or pledged allegiance to him; «أدرك النبي» (lived in
his time) is none. «رجل أتى النبي» is a narrative, not a designation, and is not listed. Classes by precedence
companion, ansar_muhajir, none, so «رجل من الأنصار من أصحاب النبي» is a companion. A chain top counts as narrating from
the Prophet (the ansar_muhajir condition) because it is the top of a chain of the report. *Alternatives:* the mention
span alone (misses most designations); classify the text fallback too (reads the matn); a broader ansar list
including Anṣārī clans («من بني سلمة»): tribal, left none as the brief says.

**D70. One node per group, never identified with a named companion** (`u<group_id>`). Every unnamed companion of a
group is one node, as the brief decides. I first also identified him with a named companion when his student
narrates the report from exactly one named companion in another chain (Ibn Hajar's rule for naming a mubham from
another route). Group 6524 shows why that is unsafe here: Ḥumayd al-Ḥimyarī's «لقيت رجلا صحب النبي ﷺ كما صحبه أبو
هريرة» — the man is explicitly *not* Abū Hurayra — has two chains the source resolved to Abū Hurayra, and the rule
named all thirteen unnamed companions Abū Hurayra. Dropped. The node is a companion (ordinal 12, layer 1, a PROPHET
edge; `gharib_mutlaq` when it is the cut vertex), counts as level 1 in v1 and v2, is skipped by the census (kind
`ucomp`) and by the `companions` / `companions_chain_end` counts (they stay comparable to the source's
`sahaba_qty`); `kappa_unnamed_split` splits it per student. Ibn Hajar's condition in *al-Nukat* — the Successor
free of tadlīs — is applied as the ordinary tadlīs rule on the link from the unnamed companion. *Alternatives:* the
identification above; one node per (student) context as for other unnamed persons (D4; that is
`kappa_unnamed_split`).

**D71. Conditional rulings: what is read and from where** (`derive.conditional`, `src/itibar/conditional.py`,
`lists/conditional*`). The ruling table is built from the books, never from the disagreement table: the seed (PR 5's
residue narrators, the conditional labels, the source's `has_ikhtilat` flag — 161 narrators, not mentioned by the
brief —, the brief's named cases, and every entry of al-Kawākib al-Nayyirāt, al-ʿAlāʾī's al-Mukhtaliṭīn,
al-Ightibāṭ and Ibn Rajab's «القسم الثاني» matched to `rawis`) only says where to look. Each seed's Taqrīb and Taḥrīr
entries are fetched by name; an entry is accepted after an identity check (four name words in order, or three
with a nisba of his nickname or nasab in the entry, or three with the source's label inside the entry), because
the prefix reader of PR 5 lands on namesakes (it read «إبراهيم بن محمد الفزاري» for Ibn Abī Yaḥyā); vowelling notes
inside a name («سماك بكسر أوله وتخفيف الميم ابن حرب») are skipped. Conditions are read by fixed patterns on the whole
entry (the condition often follows the tabaqa: «من السابعة خلط بعد احتراق كتبه»), effects as in the README. The
books' matcher for entry heads is the mudallisin matcher with its rule (a), and, as its rule (b) used the source's
`has_tadlis`, the source's `has_ikhtilat` flag as the independent second source (on the candidate and on no namesake,
ism + father agreeing, margin ≥ 0.1, score ≥ 0.45: these heads give the name alone, without the nickname the
*Ṭabaqāt* prints after it, so scores run lower; 46 of al-Kawākib's 70 entries, 37 of al-ʿAlāʾī's 46). Names in a condition are resolved
among the narrators adjacent to him in the chains; a name several adjacent narrators fit resolves to one only when it
carries ≥ 95% of their links with him (`conditional_rules.dominance`; the source splits some men in two, e.g.
ʿAbdallāh b. Wahb r5147 / r5146). **Auto rule:** the condition is stated in the narrator's own Taqrīb or Taḥrīr entry,
every id matched uniquely, no name left unmatched, and Taḥrīr does not dispute it. For the ikhtilāṭ the condition
stated in his entry is the confusion itself; the students placed before and after come from his entry (Taḥrīr lists
them for ʿAṭāʾ b. al-Sāʾib, Saʿīd b. Abī ʿArūba, Ibn Lahīʿa) and from the ikhtilāṭ books, read only from explicit list
phrases («وممن سمع منه قبل الاختلاط: …»), the entry's lists first, a student placed on both sides left out. **Result:** 227 narrators looked up, 388 rows; 35 auto — 21 applied rulings on 14 narrators (9 from a teacher, Ismāʿīl b. ʿAyyāsh's region, Ibn Lahīʿa's students, five ikhtilāṭ narrators) and 14 unobservable — and 353 needs_review, most because no Taqrīb or Taḥrīr entry was identified (the source's has_ikhtilat flag covers many narrators after the Taqrīb's twelve layers) or no student is documented as hearing before. Effect alone (stage 9): 157 groups change, agreement 71.49% → 71.20%.
*Alternatives:* the strict reading of the auto rule for the ikhtilāṭ (the students too must be named in the Taqrīb or
Taḥrīr entry): three of the five ikhtilāṭ narrators (ʿAṭāʾ b. al-Sāʾib, Saʿīd b. Abī ʿArūba, Ibn Lahīʿa,
whose Taḥrīr entries list the students; Simāk's and al-Jurayrī's early students come from al-Kawākib); a window around trigger words for the lists (tried first: it put al-Ṭaḥḥān, ʿAlī b. ʿĀṣim
and Hushaym, whom al-ʿAlāʾī names as hearing ʿAṭāʾ late, among the early students; dropped).

**D72. When the books disagree, the row waits.** The labels follow Taḥrīr (audit §11.7). (1) A ruling read from
Taḥrīr's «بل:» revision supersedes Ibn Hajar's of the same kind (Ibn Lahīʿa: Taqrīb «ورواية ابن المبارك وابن وهب عنه
أعدل», Taḥrīr «وحديثه صحيح إذا روى عنه العبادلة»). (2) Where Taḥrīr's comment disputes a Taqrīb condition («فيه نظر»,
«ليس بجيد … فإنه لم يختلط», «لا معنى لذكره») the row is needs_review: Maʿmar's teachers, Jaʿfar b. Burqān in al-Zuhrī,
Abū Isḥāq al-Sabīʿī's ikhtilāṭ. (3) A narrator al-ʿAlāʾī places in his first category («من لم يوجب ذلك له ضعفا أصلا»:
Ibn ʿUyayna, Ibn Rāhawayh, Jarīr b. Ḥāzim, Abū Isḥāq …) gets no ikhtilāṭ ruling in force; a confusion the entry calls
minor («قليلا», «لم يفحش», «فلم يحدث») likewise. (4) An ikhtilāṭ ruling needs at least one student documented as hearing
before: with `unknown: after`, none would put every student after the change, which no source does for such a narrator
(al-ʿAlāʾī closes ʿAbd al-Razzāq's entry «وبالجملة فهو حجة على الإطلاق», though Aḥmad's early hearing is stated only as
«قبل المئتين», which no list phrase captures). *Alternative:* apply Ibn Hajar's wording throughout (the brief's
"Taqrīb or Taḥrīr" allows either; mixing them would grade one link by two critics).

**D73. The hearing check on tier 4 was already there.** The brief says PR 5 applied the hearing-elsewhere check to tier
3 only; PR 5's code lifted any tier ≥ 3 ʿan covered by a hearing word on the same link in the report (D57 «a defect
unless covered»; `muanan_covered_tasrih_tier_4` 4,832 chains in PR 5's audit). No default changes; the switch
`tadlis.tasrih_tiers: [3, 4, 5]` makes the rule explicit and `tasrih_tier_3_only` measures what tiers 4–5 contribute
(audit §11.11). There is no stage of its own.

**D74. The residue tags** (*amended by D89, PR 7: the residue is decomposed into three layers; `chain_choice` and
`source_severe` are retired, `tadlis_only` and `mursal_only` became `tadlis` and `mursal`*) (`src/itibar/residue.py`,
`residue.precedence`). Computed in the pipeline for the default
ruleset's v2 chain. Weakest positions: the defect positions, else the positions of the weakest level. `source_severe`
reads the effective levels of the v2 chain (after rulings); `corroboration` is an upgrade the source does not follow
(our code lower) or a ḍaʿīf/ḥasan chain with an uncovered target where the source is higher; `level_only` is a chain
whose only defects are levels, with no upgrade and no corroboration tag; `conditional_narrator` / `resolved` needs the
`conditional_off` variant (a group agreeing now, disagreeing with the rulings off, with a ruling fired). The
precedence puts the unit of grading first, then what the machinery names on the chain, then what lies outside it.
`tahrir_vs_ibn_hajar` reads the head formula of the Taqrīb verdict and of Taḥrīr's «بل:» revision for the 100
narrators most often weakest at the ṣaḥīḥ/ḥasan line (`lists/source/boundary_verdicts.jsonl`). *Alternatives:* a
precedence led by `source_severe` (the strongest claim about the grader) — the order changes the primary tag only.

**D75. Sibling shawāhid off by default** (D58 amended; `shahid_scope: group`, variants `siblings`, `siblings_strict`).
The idf-weighted Dice measures shared vocabulary, not shared meaning — the inspection found a pair whose witness
negates the chain («لا يصافح النساء») at 0.60 — and shāhid detection by meaning belongs to the text layer (bucket 3).
The machinery, the floor and the inspection stay and are reported. Effect alone (stage 10): 607 groups change,
agreement 71.20% → 71.82%; the `siblings` variant 70.98%, `siblings_strict` 71.28%. The sandals dowry is repaired
under `siblings` only.

**D76. The mudallis set is the Ṭabaqāt union** (D57 amended; `mudallis_set: union`, variant `mudallis_source_flag`).
The paper's sentence must cite a book, not the dataset's editors: every narrator matched to Ibn Hajar's book at his
tier, plus the source's flagged narrators at `untiered_tadlis` where not matched. al-Zuhrī's tier-3 placement is
disputed and is discussed by name (audit §11.12, reports/residue.md). Effect alone (stage 11): 159 groups change,
agreement 71.82% → 71.53%; `mudallis_source_flag` 71.82%. al-Zuhrī's uncovered ʿan is a v2 defect in 5,688 chains;
191 groups' v2 chain is one of them, 127 of which disagree with the recorded grade.

**D77. Gold.** Nine entries (44 in all, all pass), each with its classical source checked against the page: the unnamed
companion of Ḥumayd al-Ḥimyarī (group 6524; *Fatḥ al-Bārī*: «إبهام الصحابي لا يضر»); Ibn Lahīʿa through Ibn al-Mubārak
(3555) and through Yaḥyā b. Ḥassān (2); Ismāʿīl b. ʿAyyāsh from the Syrian Shuraḥbīl (458) and the Madinan Mūsā b.
ʿUqba (1990), the two hadith after which al-Tirmidhī reports al-Bukhārī's verdict; Saʿīd b. Abī ʿArūba through
Yazīd b. Zurayʿ and through Wakīʿ (13); Simāk from ʿIkrima (407); Ibn Isḥāq's ʿan from Makḥūl in al-Tirmidhī covered
by «حدثني مكحول» (37). The Ibn Isḥāq entry asserts that his link is covered and that his node is not a position to
cover; the chain keeps a light defect, Makḥūl's own uncovered ʿan (tier 3 under the union), so it does not assert a
defect-free chain. The sandals entry asserts code 2 under the default and 1 under `siblings`; the gold reader now
reads a variant on the path's best chain under that variant (with the default all 47 ʿĀṣim chains tie at code 2 and
the first of them is not the one the sibling witness overlaps). Ibn Lahīʿa's Taḥrīr ruling (the four ʿAbādila, «صحيح»)
waits for review because «ابن يزيد المقرئ» fits several of his students; the Taqrīb's (Ibn al-Mubārak and Ibn Wahb,
«صدوق», level 4) is in force, and a student a via_student ruling vouches for is placed before the burning of his books.

**D78. Engineering.** `out/unnamed_tops.parquet` is built by `make words` (and `make ci`) and read by the loader;
`make conditional` rebuilds the ruling table from the committed `lists/source/` (no network); `make conditional-fetch`
re-downloads the entries and the four books. Stage files are sorted by number (s10 after s9). Gold `chain_check` gains
`rulings_include`, `rulings_eq`, `weak_nodes_include` / `_exclude`, `defects_include`, `unnamed_companion` and
`alt_*` codes; entries gain `edges_include`. The fixture carries the narrators with rulings in force and the ids
their conditions name.

**D79. Versions.** `structure.version: 5`, `derive.version: 4`; stages 0–7 set the new switches off
(`unnamed_companion.enabled: false`, `conditional: false`, `mudallis_set: source_flag`) and stage 7 reproduces PR 5's
records group by group (κ, cut vertices, v2 codes and rules, receipts).

## Site

**D80. Static pages with precomputed bundle layouts.** Each report and every named narrator on a
route gets an HTML page. Python lays out the stored generations and writes a bounded bundle view
and its expandable drawing as compact JSON. The overview contracts runs of at least three
unmarked single-strand narrators where the drawing stays unbranched. When it hits 220 nodes it
prioritizes marked nodes and stored paths, then samples across generations by chain occurrence.
Canvas draws the positions, cut and common-link marks, and the stored threshold edge masks.
The browser reads the same κ values and receipts as the page. The pipeline now persists
`receipt_structure` with threshold cuts, disjoint paths, chain citations for their edges, the
lower-bound inputs, number class, common-link branches and dates. The census includes route and
cut counts covering book-role occurrences alongside its existing counts.
The alternative was an SVG from Graphviz per report and threshold, which would repeat node
labels and fix each layout.

**D81. Published size and page budgets.** The first full tree measured 1.47 GB with plain JSON
and HTML for every narrator-list continuation. The build now stores per-report drawings, chains
and receipts as gzip JSON and pages the longer narrator lists through gzip JSON. They are read
on demand using the browser's gzip support. Report and narrator landing pages stay in HTML.
The measured full tree uses **825,269,155 bytes** across **64,866 HTML pages**, including
**20,745** reports and **44,114** narrators. Reports account for about 450 MB, narrators 258 MB,
downloads 102 MB, and search 16 MB. The uncompressed upload archive uses 979,824,640 bytes
including tar overhead. `make site-check` enforces the
[1 GB GitHub Pages cap](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
using the sum of published file sizes. It also caps HTML and compressed drawings at 192 KiB
each, and report HTML plus its initial drawing at 256 KiB. Those budgets leave room for the
long residue report and the densest graph while keeping initial phone loads bounded. The
largest HTML measured 141,138 bytes (residue). Group 2 had the largest initial report at
187,972 bytes, including a 114,909-byte drawing. Publishing expanded HTML and SVG with HTTP
compression was the alternative. It reduces transfer size while leaving the publish tree
over its storage budget.

**D82. Sharded Arabic search.** The Python index uses `lists.normalize` v1 on each opening,
the representative full text shown on its page, and both sourced narrator names. The browser's
matching normalizer is tested against Python. Queries intersect exact Arabic tokens and rank
opening and name hits first. Sorted posting lists use variable-length differences,
with individual files for high-frequency tokens and hashed shards for the rest. Result labels
are in blocks of 24 records. A separate index covers source book and hadith number pairs,
with aliases for common collection names and Arabic and Western digit forms. Five cold-index
queries covering opening, full text, name, and Arabic and English citations returned in
819–826 ms on a 390-pixel Chrome viewport with 4× CPU throttling, 100 ms latency, and 4 Mbit/s
download. The alternative was a single browser search index that loads all text and titles
up front.

## PR 7 (`docs/prompts/pr-7.md`; derive version 5)

The recorded grade is decoded (reports/source_grade.md) and the residue rebased on the decoding (reports/residue.md);
the critics' own verdicts are extracted from the texts and the machinery is scored against them (reports/verdicts.md).
Classical definitions were fetched from Shamela by one pass and checked byte for byte against the page text by a
second (`lists/source/critics_definitions.jsonl`, 25 records).

**D83. The source's chain grade is a template, decoded** (`src/itibar/source_template.py`). `sanads.hukum` (44,524
distinct strings) parses into 1,083 skeletons in 978 families, 99.97% completely (the rest are a hand-written
minority: «وجهالة الصحابي لا تضر», «على شرط الإمام البخاري», «سقط أكثر من راوي», «وفي الإسناد X متهم بالتدليس»). The
verdict word after «وهو» is `rawis.rank` in 99.70% of named narrators in their chain (the source does not re-grade in the
sentence; the mismatches are labels edited later). The code: the weakest `rank_no` over **every** position (the compiler
at pos 0 included — without him 96.84% instead of 99.68% on single-chain hadith), an undescribed narrator read as
«مجهول الحال» (level 7, as the sentences say), the unnamed person not graded; level → code 1–3 → 0, 4–6 → 1, 7–9 → 2,
10 → 3, 11 → 4, 12 → 5; one break marker → code ≥ 2, two or more → ≥ 3, the unnamed person counting as one «موضع
إرسال» only when an inqiṭāʿ or taʿlīq marker is in the chain (a chain with an irsal marker and an unnamed person reads
one irsal: 373 of 433 such chains are 2; with an inqiṭāʿ or taʿlīq marker 3). Reproduction: 92.10% chain by chain, 99.68%
in single-chain hadith, 99.62% as a multiset per hadith (D84); every miss has a named class (source_grade.md §3.1). The
tadlīs rule is absent (the word «مدلس» is only a label); «روى له البخاري تعليقًا / مقرونًا» reads a field the dump does
not carry. *Alternatives:* grade without pos 0 (itibar's v1 reading, 96.84%); the unnamed person always an irsal (codes
every «عن رجل» chain ≥ 2: contradicted by 3,384 single-chain «إسناده متصل ، رجاله ثقات» over an unnamed person).

**D84. In hadith with several chains the recorded chain codes are attached to the wrong chains.** Where a hadith's chains
have different template codes, the recorded codes match them as a multiset but the pairing with `sanads` rows is close to
chance (2 chains: 7,674 in sanad order, 6,737 swapped, 7,242 expected by chance; 3 chains: every one of the six pairings
about equally often), and 23,366 sentences name a narrator found in another chain of the same hadith and not in their own.
So a per-chain `sanads.matn_no` or `hukum` is a statement about *a* chain of the hadith; per hadith and per group
(minima) nothing changes. Reproduction is reported chain by chain and per hadith; nothing is re-attached in the data
(re-attaching by names works only for the sentences that name someone). *Alternative:* a bipartite re-attachment by named
narrators and codes (not done; it would edit a recorded value).

**D85. The group grade is the best recorded chain's, with editors' exceptions.** `hadiths.matn_no` = the lowest chain code
of the hadith in 99.47% (never better; worse in 0.53%, a hadith coded 3–5 over a best chain of 2–4).
`meaning_groups.matn_no` = the lowest recorded chain code of the group in 86.77% (within the chains' range 98.25%; the best
hadith grade 87.09%; the modal chain code 64.97%); worse than the best chain in 2,503 groups (nearly all 3–5 over 2–4),
better in 181. No field of the dump records why (`takhrij` is an id shared by parallel narrations, without text); no
corroboration across chains: a group of ḍaʿīf chains is never ḥasan by count. *Alternatives considered and measured:* the
modal chain, a book class's minimum, the largest takhrīj cluster's minimum (none explains the exceptions).

**D86. The code-map switch** (`derive.codes: classical | source`, `grades.yaml: levels[].code_source`). Classical stays
the default (D20). Both maps are always computed and stored (`derived_code_<map>`, `chain_code_<map>`,
`code_v2_<ruleset>_<map>` for every ruleset and variant); the switch picks the main columns. In v2 only the codes that
read a level change: a fatal chain keeps its v1 code and an unrepairable one max(v1, 2) under the map (identical in
practice), and a ḍaʿīf chain whose uncovered defects are all level-5 or level-6 narrators is 1 under the source map —
the code that map gives those levels; corroboration then matters only for levels 7–8, the mursal and tadlīs. *Alternative:*
the source map as `hasan_max_level: 6` (rejected: it would let a level-6 chain reach ṣaḥīḥ li-ghayrihi, a ruleset question,
not a code convention).

**D87. `source_template` is a v1 ruleset of the pipeline** (`derive.source_template`). Every chain carries
`code_source_template`, `level_source_template`, `breaks_source_template`; every group `code_source_template` (its lowest
chain code, ties by lowest sanad id, no continuity preference — the source has none), `best_sanad_source_template`, and
the recorded best chain `matn_no_best_chain`. On itibar's chains it agrees with the recorded group grade in 86.55% and
with the recorded best chain in 99.13%. *Alternative:* keep the template outside the pipeline (rejected: the residue's
layers need it per group).

**D88. The critics' «وفي الباب» scopes.** `tarafs` holds one row per meaning group, so the brief's «anywhere under the same
taraf» would be the group itself; it is read as the grandparent of the group's leaf topic rows (the sibling search one
level up, D58's listed alternative). Names are resolved among the companions who end a chain within that widest scope.
*Alternative:* the whole corpus (every companion who ends any chain: resolves more names, tests nothing about the
chapter).

**D89. The residue in three layers** (D74 amended; `src/itibar/residue.py`). recorded − v2 = (recorded − R) + (R − ST) +
(ST − v2), R the recorded best chain, ST the template on itibar's chains. A disagreeing group is attributed to the first
non-zero layer (aggregation, chain, substance), so the counts add up (gated); every non-zero layer is stored. PR 6's
`chain_choice` read the per-chain recorded code, which D84 shows is attached to the wrong chain about as often as chance,
and its groups are what the aggregation and substance layers now measure; `source_severe` is the aggregation layer
measured directly. The substance tags name the defects or rules v2 applies to the compared chain (v2's chain when v2 is
lower than the template, else the template's best chain as v2 grades it) that the template does not; `tadlis_only` and
`mursal_only` became `tadlis` and `mursal` (a chain carrying both shows both, where PR 6 put it under `unexplained`).
*Alternatives:* attribute a group to the layer with the largest absolute contribution (a tie rule needed; the precedence
reads the order of grading: the editors last touched the grade); substance first.

**D90. The critics' claims: where they are read and how names resolve** (`src/itibar/verdicts.py`). The books whose
authors comment were found by the survey (n-grams after `matn_end`, `reports/verdicts_survey.csv`); formulas are matched on
`lists.normalize` text from `matn_start` on (`matn_end` is approximate) and every span is mapped back to `hadiths.nass`
offsets (gated: the span is the text at its offsets). One claim per span and type. A relayed claim is the original
critic's: al-Khaṭīb's «قال سليمان لم يروه …» is al-Ṭabarānī's, *Kashf al-Astār*'s «قال البزار …» al-Bazzār's (so a claim
can be read twice, in two books, and is scored twice). Names are resolved among the narrators of the hadith's own chains
by `conditional.find_names` (D71's resolver), «رسول الله» / «النبي» as the PROPHET node; al-Bayhaqī's «رواه البخاري في
الصحيح عن X» resolves X among the Ṣaḥīḥ chains' pos-1 narrators of the group. Unresolved slots keep the reason (not in the
chain, ambiguous, several names). *Alternative:* resolve against the whole `rawis` table (more hits, many namesakes).

**D91. The tafarrud test** (`src/itibar/critics.py`). «From X only Y» is tested as stated: in the group's bundle (on-path
edges, threshold everyone) every route from X to a book passes through Y. Where the claim leaves X or Y implicit, they are
read off the hadith's own chain: «تفرد به Y» — X is Y's teacher there; «لا يروى عن X إلا بهذا الإسناد» and «لا نعلمه يروى
عن X إلا من هذا الوجه» — Y is X's student there (X absent = the Prophet, Y the companion); «لا نعرفه / لا نعلمه / لم نكتبه
إلا من حديث Y» — from the Prophet, only through Y; «ولا عنه إلا Z» — from the previous Y, only Z. A narrator on no
Prophet → book route is *not on path* and the claim untestable there. A failure is classed by its strongest breaking chain:
in the critic's own works, in a book whose compiler died before him, only in later books, or only a spliced route; a
breaking chain is a *misresolution candidate* when the narrator below X in it is a namesake of Y (same ism and father, or
the same name cluster) or its link to X is continuity-incompatible. *Alternatives:* the test on the hadith's own chains
only (trivially true); at the threshold the critic would accept (the claims are about narration, not soundness).

**D92. al-Tirmidhī's gharīb, ḥasan and verdict classes.** Absolute gharīb = κ_all 1 (the number class); «غريب من هذا الوجه»
relative to the chain's companion (one student below him), «غريب من حديث X» relative to X. The verdict classes are
profiled, not tested: κ at each threshold, a «وفي الباب» companion found, v1/v2 under both rulesets and both maps, the
weakest level of his chain. The «حسن غريب» question is reported with its classical answers (Ibn Hajar's *Nuzha*, Ibn
Rajab's *Sharḥ ʿIlal al-Tirmidhī*) and not resolved. **Source correction:** the brief places the discussion in Ibn Hajar's
*al-Nukat*; its commentary on the ḥasan (Shamela 8316, pp. 360–465) has no passage on «حسن غريب» as such (the nearest
sentence says al-Tirmidhī left his definition unqualified, «فلم يقيده بغرابة»); the question and answer are in the *Nuzha*
(1565/63) and Ibn Rajab (9552/549, 552). *Alternative:* «من هذا الوجه» as the whole chain unique (untestable on a pooled
group).

**D93. al-Ḥākim's shart.** The men judged are those of his chain up to the Ṣaḥīḥayn's generation: pos 0 (al-Ḥākim) and
every narrator who died after 261, or undated after tabaka 11, are left out; companions are not judged. *men*: each a
narrator of the named Ṣaḥīḥ by `rawis.is_bukhari` / `is_muslim` (lenient: `is_bukhari` includes narrators cited only
muʿallaq); *pairings*: each teacher → student link among them in a chain of the named Ṣaḥīḥ anywhere in the corpus. The
classical baseline, al-Dhahabī's Talkhīṣ, is not in the corpus text (no «قلت» or «الذهبي» in book 12): one example is
quoted from Shamela's ʿIlmiyya edition (2266/2907) and is a gold entry. *Alternatives:* the men of the whole chain (al-Ḥākim's
own teachers can never be the Ṣaḥīḥayn's men); pairings within the same group only.

**D94. The Dice calibration.** The true pairs are (al-Tirmidhī's matn, a named companion's best matn among the sibling
groups); the non-pairs (his matn, any other companion's best matn among the same siblings). At the 0.32 floor the
idf-weighted Dice of PR 5 keeps 7.3% of the true pairs and 0.8% of the non-pairs (reports/verdicts.md §6): it ranks named
companions higher but finds few of them, because the «وفي الباب» relation is a report *on the subject*, often in other
words. The floor stays (D75: siblings are a variant); the set is kept for bucket 3 (`out/critics/pairs.parquet`).
*Alternative:* every sibling matn of the named companion as a true pair (dilutes the set with his other reports: tried
first, the two distributions then coincide).

**D95. Gold.** Eight entries from the critics (52 in all, all pass), each quoting the claim from the corpus text with its
book, page and hadith: al-Ṭabarānī's tafarrud from Nāfiʿ (only Ibn Isḥāq) and from Ibn Sūqa (only Ḥafṣ b. Sulaymān) hold;
from Abū Jaʿfar al-Rāzī (only Muḥammad b. Sulaymān) is broken by al-Mustadrak's chain (al-Ḥākim d. 405, after the critic);
al-Tirmidhī's «حسن غريب» (group 11435) and «حسن صحيح» (14519) with κ at every threshold; his «وفي الباب عن ابن مسعود وجابر
وأنس» with Ibn Masʿūd and Anas found in the sibling groups 777 and 2652; al-Ḥākim's «على شرط الشيخين» that holds (13468)
and his «على شرط مسلم» for «لا طلاق ولا عتاق في إغلاق» (437) that al-Dhahabī corrects: the check finds Muḥammad b. ʿUbayd
al-Makkī outside Muslim, as al-Dhahabī says. The gold reader compares quotes as `lists.normalize` text (hand-copied Arabic
orders shadda and vowel differently) and asserts the extracted span is the hadith text at its offsets. The fixture carries
the sibling groups a gold «وفي الباب» entry names; the pairing check needs the corpus's Ṣaḥīḥ links and is asserted only on
the full run.

**D96. Versions, gates, engineering.** `derive.version: 5` (the code maps and `source_template`); `structure.version`
stays 5. New gates: every claim's span is its hadith's text at its offsets; the residue's three layers sum to the
disagreement count and their signed differences to recorded − v2. No agreement gate (D63). `make source-template` and
`make verdicts` are new targets; `make ci` extracts the claims on the fixture.

## The reading layer (`docs/prompts/site-ux.md`; D97–D105)

The critics' check (PR 7, built in parallel) takes D83–D96; these entries start at D97.

**D97. Information architecture: an answer first, evidence after.** A report page reads top to bottom as
the brief orders it: the English title, the Arabic opening and the major collections as chips; *At a glance*
(four tiles and three to six sentences); *How it reached the books* (the story view); *Why this grade*;
*Where it is recorded* (books in four groups, only the first open); *All chains*; *Classical notes*; *For
specialists*. Each sentence of *At a glance* ends in a link to the section that computes it, and every
number in it is a stored value restated. Hierarchy comes from type and rules between sections, not panels.
Narrator pages follow the same order — who he was, his rating on the twelve-step scale, his place in
transmission, teachers and students, the critics' statements. Browse (topics, collections, notable
narrators, famous reports) is a page of its own, and every topic and collection has a list page.
The alternative was to keep PR 7's single scroll and add a summary panel above it; the long book list and
the specialists' tables would still stand between a reader and the chains. Tabs were rejected too: they
hide the order of the argument and break find-in-page.

**D98. The story view.** A report's bundle is drawn as rows of generations (`src/itibar/site/story.py`):
compiler nodes contracted so that chains run from their last narrator into the book; a row of at most six
narrators named in full; a wider row names its marked narrators (cut vertices at any threshold, common
links) and anyone carrying a quarter of the row's chains, and groups the rest by the item above them that
most of their chains come through ("8 students of Yaḥyā b. Saʿīd"); once two successive rows have been
grouped, everything below is folded into one band per anchor ("Yaḥyā b. Saʿīd's line: 501 narrators,
generations 7–30"); then the books, the nine major collections by name. Links carry the chain count
(drawn as thickness) and their threshold mask. The independent lines are the receipts' stored maximum sets
of vertex-disjoint routes at each threshold (`receipt_structure.<threshold>[0].data.routes`, persisted
since PR 7, D80), mapped onto the items they pass through and drawn in colour; nothing is recomputed.
The filter sentence restates κ at the step, names the minimum cut when it is small (Menger: every
remaining line passes through one of them), and lists the companions whose chains no longer reach a book
at that step (reachability over the stored edge masks) with the first narrator on their heaviest path
who falls below it. Where a gold check scopes a report (319 through ʿUmar), the scoped cut vertices are
marked "single line" with the scope in the tooltip, and *At a glance* says the scoped count beside the
whole count (D99). The browser lays chips out with CSS and draws the links in an SVG behind them, so names
never overlap and rows wrap on a phone. The full canvas graph (PR 7) stays in *For specialists*, loaded
when opened. Alternatives: a Sankey layout (flows merge and split cleanly but cannot name 500 narrators or
show skipped generations), and the full graph with labels on demand (PR 7's view: correct, unreadable).

**D99. Sentences by template; scoped numbers in words; grades attributed.** `src/itibar/site/view.py`
writes every sentence from the record with fixed templates — no model, the same output on every build.
A gold check's scoped result is stated next to the whole count: for 319, "The classical account counts only
the chains through ʿUmar. Counting those 335 chains less 14 documented deviations, itibar finds 1
independent line, through ʿUmar, ʿAlqama, al-Taymī and Yaḥyā b. Saʿīd one after another. The other 21
chains through other companions are outside that account." Grades are always the classical term, its
Arabic, a gloss and an attribution: "By the classical rules, from the narrators' ratings: ṣaḥīḥ li-dhātihi
(sound in itself)" and "Recorded in the dataset: ṣaḥīḥ (sound) — the grade the dataset's editors attached
to the report" (worded so that PR 7's finding, that the recorded grade is produced from narrator ratings
by the dataset's editors, can be added as one more sentence). *Why this grade* draws the ruleset's best
chain from the Prophet to the book with a rating badge per narrator, marks the positions the receipt names
as weak, says the rule in one sentence per rule class (`RULE_SENTENCE`), and draws each witness chain the
same way with its divergence class glossed; the two readings appear separately only when Ibn Ḥajar's and
Ibn al-Ṣalāḥ's differ in rule, code or chain. CI rejects any page whose text says "this hadith/report is
…" with a grade word. The alternative — generated prose summaries — was ruled out by the brief and by the
standing rule: a template can be audited against the record, a model's paraphrase cannot.

**D100. The glossary is hand-written; the interface shows no internal identifier.** `config/glossary.yaml`
holds 43 terms (term, Arabic, transliteration, a one-sentence definition, a paragraph, where it comes
from, related terms), the twelve Taqrīb levels (a short badge name, the level name, the Arabic terms, the
meaning in plain English), Ibn Ḥajar's twelve generations with his examples, the five tiers of tadlīs with
what itibar does with each, the four filter steps, and the grade and number-class terms. The glossary page
renders it; every term in the interface links to its entry and shows the definition on hover, focus or a
first tap (`assets/glossary.js`, from `assets/glossary.json`). The translation prompt includes the terms'
spellings. `make site-check` scans the visible text of report, narrator, browse, home, search, glossary
and classical-check pages for identifiers (`sahih_li…`, `_v2`, `v1`, `ordinal`, `kappa_`, rule and class
keys, "None recorded"), for κ before the specialists' section, and for verdicts in the site's voice; a test
asserts that every glossary id the templates and `view.py` link to exists. The method, residue, figures and
downloads pages document the data and keep its column names. The alternative was definitions inline in
the page text, which repeats the same paragraph on 20,000 pages and still leaves terms undefined where they
recur.

**D101. Human translations: HadeethEnc, joined; not sunnah.com or re-hosted publishers' text.**
HadeethEnc's "Terms and Policies" (https://hadeethenc.com/en/home, the download section) allow the
translations to be "downloaded and republished" provided the content is not modified, added to or deleted
from, the publisher and source (HadeethEnc.com) are named, the version is stated, and no inappropriate
advertisement is shown. itibar shows a matched item's English text verbatim, as a separate block headed
"A human translation of this report", with "From HadeethEnc.com … reproduced unmodified; retrieved
<date>" and a link to the item; its title, where it exists, is the report's English title (credited the
same way). The API (v1) carries no per-item version number, so the retrieval date and the API version
stand in for it; `make hadeethenc-fetch` re-reads the source when they update, as their terms ask. The site
has no advertisements. HadeethEnc's own grade and explanation are not shown (they are its verdicts, and the
site shows only attributed classical terms). `make hadeethenc-fetch` walks the category list and fetches
each English item once at about one request every two seconds (2,328 items), writing
`translations/source/hadeethenc_en.jsonl`; `make hadeethenc` joins each item to the group whose recorded
texts share the most idf weight with its Arabic (lists.normalize tokens; at least 60% of the item's weight
and 15 points clear of the next group), keeping one item per group: of the 2,328 items, 1,281 match clearly,
and 1,090 reports carry a human translation (a sample of matches read by hand were all the right report). sunnah.com's English is the publishers'
(Darussalam and others) under copyright and its site is not licensed for scraping; the GitHub repositories
that re-host those translations carry no licence from the publishers, so neither is used. The alternative
was machine translation only; human translations, where their terms allow, are better English and carry
their own accountability.

**D102. The translation files are the contract; a session or an API run may produce them.** (Amended in
the session: there is no API key.) `translations/<kind>.parquet` — kinds `book`, `topic`, `place`,
`critic`, `narrator`, `opening`, `text` — holds one row per item: `key`, the Arabic `source` exactly as
read, `source_sha` (sha256, 16 hex), `en`, `extra` (JSON: short name, transliterated title, author),
`producer` (`session:<date>:<label>` or `api-batch:<batch id>`), `model`, `prompt_sha` (the fixed prompt,
the kind's instruction and the glossary's spellings) and `created`. Every producer writes through
`python -m itibar.translate import`, which accepts an item only if its key exists for the current outputs,
its `source_sha` matches the current Arabic and its kind's fields are non-empty; an item whose source
later changes is stale and never shown. `translate pending` writes the missing items as JSONL work sets
with the prompt (`PROMPTS.md`) for a session; `make translate` is the optional Message Batches path
(structured JSON output, the system prompt cached, `uv sync --extra translate`); nothing else imports the
`anthropic` package and nothing computed reads the files — only the site does, labelled "Machine
translation · the Arabic is the text", always beside the Arabic. Which text is translated per report is
the page's representative text (the hadith carrying the best single chain, else the first by book and
number), keyed `group:hadith`. This PR fills the fixture's items in a Claude session
(`producer = session:2026-11-23:itibar-site-ux`, model `claude-opus-5-5`): 425 books, 375 level-1 and
level-2 topics, 743 places, 871 critics, the 11,476 narrators on a route in the fixture's reports, and the
351 openings and 348 representative texts of its reports. The second pass (`make translate-sample`, `make
translate-checks`) drew 200 items at random from the 14,589 (160 narrators, 13 critics, 8 texts, 6 openings,
6 places, 5 books, 2 topics) and had a separate session, which had not produced them, check each against the
Arabic and the source records: 195 correct, 5 minor (two village vowellings, a critic's common name, a critic's
nisba, an opening cut short), none wrong; the five were corrected (producer `session:2026-11-23:itibar-site-ux-check`)
and the verdicts are in `translations/checks.parquet`. The translators also listed the items they were unsure
of — mostly corrupt or rare spellings in the source names — and kept "en" as written where the source and the
narrator's fuller record disagree. A later session fills the rest of the corpus
into the same files. The alternative — translating at build time — would make the site depend on a model
and a key, and would change the English between builds.

**D103. Search over English and Arabic, ordered by spread.** One box (`src/itibar/site/search.py`,
`assets/search.js`). Arabic: `lists.normalize`, every query word must match, as in PR 7, now over each
report's 30 most frequent distinct openings as its books record them (`hadiths.taraf_nass`) as well as the
representative text, so «من كذب علي متعمدا» finds report 1 though its listed opening is «لا تكذبوا علي».
English: lower case, accents and ʿ/ʾ removed, a short stop list and light suffix stripping (version 1,
mirrored in `normalizer.mjs`, parity tested), over the English titles and texts (machine and HadeethEnc),
the transliterated narrator names and the book titles; a document must contain most of the query's words
(all of one or two). Documents are numbered by spread — reports by their number of chains, narrators by
the number of reports they are on a line of — and matches are ranked by the number of query words found
(Arabic: then words in an opening), then by that number, so among equally good matches the famous report
comes first and the best results sit in the first document shards. Result cards carry the English title,
the Arabic opening, the major collections, the independent lines (with the trustworthy-only count), the
classical term of the best chain and the number class; filters for topic, collection, grade and number
class apply to the best 600 matches in the browser. A query naming a book links its collection page.
The alternative, a client-side full-text library (lunr, MiniSearch) over a single index, loads the whole
index before the first result.

**D104. Teachers and students.** `make narrators` also writes `out/narrator_links.parquet`: every
on-route link between two narrators over all bundles, counted in reports and chains (274,889 pairs).
Narrator pages list the eight teachers and eight students carrying the most reports. A compiler's link
into his own book is not a pair.

**D105. The size budget after the redesign.** The first full build of the new pages measured 1.27 GB, over
GitHub Pages' 1 GB: report HTML had grown from 14 to 24 KB a page and narrator pages from 4.6 to 6.7 KB, and
each report gained a story file. What brought it back, without dropping a page or a number: the receipts'
list, the full-graph controls and the tree's filter controls are built by the script that needs them (they do
nothing without it); the text outline of the tree is rendered from the story file in the browser (screen
readers run scripts; without one, *At a glance* and *For specialists* state the same numbers); a small
minifier collapses indentation and unquotes simple attribute values on every page (`pages.minify`, `<pre>`
untouched); a shorter shared header and footer (65,000 pages carry them); name tooltips only where a name
stands alone; narrator pages list three reports per role and five teachers and students, the rest paged as
before; group members described in the story file capped at twelve and drawn lines at eight; the full graph of a
report that has routes holds its on-route nodes only (the off-route view stays for the reports with no route,
where it is the only drawing); `out/matn_tokens.parquet` and `out/matn_vocab.parquet`, the shāhid overlap's
intermediate inputs that `make matn` rebuilds, are no longer copied to Downloads, and the published Parquet
files are written with zstd at level 19 (the same rows and columns, a quarter smaller); a report's JSON record
omits the two fields it repeats (`disjoint_routes_all`, in its structural receipt, and `nass`); the meta
description is kept on the home, search, browse and glossary pages only. Measured full tree:
**948,494,626** bytes in 180,352 files (65,603 HTML pages), with the full HadeethEnc join (reports 552,724,980, narrators 282,707,901, downloads 69,655,332,
search 18,658,523, browse 24,206,367). The English for the rest of the corpus, filled later, adds
titles, texts and names in place of Arabic-only pages; comparing the translated fixture's pages with untranslated
pages of the same size puts the growth at about 7 MB for reports, 6 MB for narrators and some 5–10 MB of search
index, about 20 MB in all; `make
site-check` fails the build before it can exceed the cap, and the remaining levers are listed here in order of
size: the per-report full graph (60 MB), record JSON (77 MB), Downloads (84 MB). When PR 7's verdicts land,
each report's critics' panel shows at most six remarks (about 10 MB in all). The page budgets are unchanged
except that a report's initial load is now its HTML and its story file (the full graph loads when opened).
The alternative — publishing fewer narrator pages, or moving Downloads to a release — changes what the site
offers; the cuts above change only how it is written.
