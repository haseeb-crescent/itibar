# Decisions

Every choice the data forced that the bucket-1 definitions did not settle, with the alternatives.
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
`grades.yaml: companion`). *Alternatives:* upstream's exact label `صحابي` (drops 10,646 chains ending at
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

**D9. Continuity window [0..4], not the brief's {0,1,2}** (`structure.yaml: continuity`). On this
source's tabaka scale, {0,1,2} marks 36% of all 4.4M links incompatible, including canonical ones:
Anas → al-Zuhri, 'Alqama → al-Taymi, al-Zuhri → Malik, Qatada → Shu'ba are gaps of 3, al-Zuhri →
Ibn 'Uyayna 4. [0..4] is the narrowest window that keeps them; "incompatible" then means a gap of 5+
layers or a student placed before the teacher. Years, when both known, still decide first. The
flags are reported only; nothing downstream depends on them.

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

**D17. κ_lower = min(merged, unmerged).** Merging nodes is not monotone: it can splice a dead-end
half-route of one person onto a half-route of another and *raise* κ. Found when we also merged each
compiler stand-in with the compiler's narrator node (Abu Hanifa: his Kufan chain from Ibn Mas'ud
dead-ends in this group, his *Musnad*'s records do not reach P, merged they formed a route; κ rose in
53 group × threshold cases, 2 of them at `all`). That merge is dropped, and κ_lower takes the minimum with the unmerged
(stubs-dropped) graph so it is a bound by construction. Merging only same (name, nickname) clusters
misses misresolution across different full names (e.g. al-Qattan for al-Ansari under al-Taymi);
fixing that needs a name-resolution model and is out of scope; the gold set documents each case it
meets. *Alternative not taken:* the exact "cut a cluster at cost 1" problem (NP-hard in general).

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
