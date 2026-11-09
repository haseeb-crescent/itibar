itibar — bucket 2: corroboration, number class, qarāʾin flags, the classical lists, the common-link census, the chapter census
Paste as the first message of a session opened at the root of `itibar` on `main` (after PR 2 is merged). Save this file as `docs/prompts/bucket-2.md` in the PR.
Why this exists
Buckets 1–2 built the skeleton: for each of 20,745 reports, the transmission graph, how many independent routes it has (κ) at four narrator-grade thresholds, who it is forced through, and what grade its best single chain earns from the critics' verdicts. What the skeleton still cannot say is what the hadith sciences actually argue about:

1. Whether routes add up. The classical grade was never the best chain alone. A report whose only chains have light defects — a narrator with poor memory, an unknown-status narrator, a gap, a mudallis's ʿan — is repaired when another independent route carries the same report; a report whose defect is fatal — an accused or lying narrator — never is. Our v1 grade ignores this, which is why it calls 2,573 groups ḍaʿīf where the source says ḥasan. Until corroboration is implemented the derived grade is a strawman of the classical grade.
2. What the tradition's own classifications say about each report. Hadith science keeps three axes separate: number (mutawātir, or āḥād split into mashhūr ≥3 / ʿazīz 2 / gharīb 1, counted at the narrowest layer and blind to narrator quality), grade (ṣaḥīḥ / ḥasan / ḍaʿīf, about people and links), and knowledge yield (certainty vs probability — where the schools disagree). We have computed grade only. The width profile already contains the number axis; it has not been labelled.
3. Whether the two camps' claims hold corpus-wide. Al-Suyūṭī and al-Kattānī list ~300 reports as mutawātir (criterion: ten or more companions). Western common-link theory predicts common links cluster in the second century. Neither has ever been checked against a whole corpus. And the source's 54k-node topic tree is a fiqh table of contents, so the Iqbal question — which parts of the law rest on what kind of transmission — is a group-by.

Standing rule: the machinery computes and reports with a receipt; it never issues a verdict and never uses "weak" or "fabricated" in outputs. Where the tradition has two readings, both are implemented as selectable rulesets and both are reported. Knowledge yield is not computed: we output the qarāʾin (indicators) Ibn Hajar names and leave the conclusion to the reader.
The task
Add the corroborated grade, the classical number class and the qarāʾin flags to every record; digitize and join the classical mutawātir lists; compute the narrator-level common-link census and the chapter census; add pooled bundles; and carry two small corrections — for all 20,745 groups, with gold tests for each new mechanism.
Definition of done
A. Corroborated grade (derived grade v2)
Implement the classical ladder as parametric rules in `config/structure.yaml: derive.corroboration`, not in code. Definitions:

* Weakness classes by Taqrīb level (`rawis.rank_no`), stored in `config/grades.yaml: weakness`:
   * light (repairable): 5 (ṣadūq with lapses — poor memory), 6 (maqbūl: Ibn Hajar's own definition is "accepted where he is followed, otherwise layyin"), 7 (mastūr / majhūl al-ḥāl), 8 (ḍaʿīf — Ibn Hajar's Nuzha example of ḥasan li-ghayrihi is ʿĀṣim b. ʿUbaydallāh, graded ḍaʿīf in the Taqrīb, repaired because his defect is memory). Structural light defects: a chain ending at a non-companion (mursal), and a muʿanʿan link by a mudallis.
   * not repairable by Ibn Hajar's explicit statement: 9 (majhūl al-ʿayn — he restricts repair to the mastūr and excludes the majhūl al-ʿayn).
   * fatal: 10 (matrūk), 11 (accused), 12 (liar / fabricator), and break markers mid-chain (inqiṭāʿ, taʿlīq) are not repaired by routes. Keep 8 in light by default with a config switch `light_includes_level_8` and record the alternative.
* Corroborating route. For a chain `c` whose weakest positions form the set `W` (all light, none fatal): `c` is corroborated if there exists a PROPHET→book route in the bundle at the `above_matruk` threshold that avoids every node of `W` and whose own attested chain grade is light-or-better — "equal to it or above it, not below it". Compute by vertex connectivity on the bundle with `W` removed; store the witnessing route (one attested chain where possible, else the route) in the receipt. Config `min_corroborating_routes` (default 1).
* Classify the corroboration by the deepest node the witnessing route shares with `c` above the weak node: same companion and the weak narrator's own teacher → mutābaʿa tāmma; same companion, higher → mutābaʿa qāṣira; different companion → shāhid. Store it.
* Rulesets (`derive.ruleset`): `ibn_hajar` (default) and `ibn_al_salah`. Under `ibn_hajar`: weakest level 1–3 → ṣaḥīḥ (0); level 4 → ḥasan li-dhātihi (1); light defect + corroboration → ḥasan li-ghayrihi (1); ḥasan li-dhātihi + an independent route of ḥasan-or-better grade → ṣaḥīḥ li-ghayrihi (0); light defect uncorroborated → ḍaʿīf (2); fatal → the source's codes 3/4/5 by level as today, never upgraded. Under `ibn_al_salah`: level 5 (ṣadūq with lapses) is ḥasan li-dhātihi on its own, so its corroboration yields ṣaḥīḥ li-ghayrihi — his siwāk example through Muḥammad b. ʿAmr. Everything else identical. Both rulesets run; records carry `code_v2_ibn_hajar` and `code_v2_ibn_al_salah`; the receipt names the rule that fired, the witnessing route, the divergence class, and the weak positions.
* Mursal. Default: a chain not reaching a companion is light-defective and corroborated by any connected route of light-or-better grade; alternative ruleset switch `mursal_rule: shafii` requiring the witness to be musnad or a mursal from a different teacher (al-Shāfiʿī's conditions) — implement both, default `ibn_hajar`.
* Group grade v2 = the best code over chains after corroboration (ties broken as v1). Keep v1 columns. Report agreement with `meaning_groups.matn_no` before and after, by ruleset, and the disagreement table by (our code, source code) and by weakest narrator.

B. Number class and qarāʾin flags

* `number_class` on the on-path graph at the `all` threshold, Taqrīb layers 1–12 only, compiler-role nodes excluded: `min_width` = minimum on-path narrator width over the layers that have any on-path narrator; `tafarrud_layers` = layers with width 1; class = `gharib` if min_width = 1 (`gharib_mutlaq` if layer 1 is among the tafarrud layers, else `gharib_nisbi`), `aziz` if 2, `mashhur` if 3 ≤ min_width < N, `mutawatir_count` if min_width ≥ N, with N = `tawatur_n` (default 10, al-Suyūṭī's criterion; alternatives 4, 5, 12, 40, 70 as documented config values). Also `number_class_kappa` using κ_all with the same cut points, and a flag where the two disagree (hidden sharing across layers). Record both; the width one is the classical count, the κ one the stricter formal reading.
* Qarāʾin flags (Ibn Hajar's three indicators that an āḥād report yields knowledge — reported, never summed into a verdict): `in_sahihayn` (any chain in Ṣaḥīḥ al-Bukhārī or Ṣaḥīḥ Muslim; separately `in_sahih_class` for `tasnif_no = 1`); `sound_distinct_routes` (κ at `saduq_up` ≥ 3 — "mashhūr with several distinct routes free of weak narrators"); `huffaz_chain` (there exists a connected chain whose every narrator is level ≤ 2, and `number_class` is not gharīb — "a chain of ḥāfiẓ-imams, provided it is not gharīb"). README states that knowledge yield is not computed and names the disagreement (Ibn Ḥazm / Ibn Hajar / al-Nawawī).

C. The classical lists

* Obtain the texts of al-Kattānī's Naẓm al-Mutanāthir min al-Ḥadīth al-Mutawātir and al-Suyūṭī's al-Azhār al-Mutanāthira fī al-Akhbār al-Mutawātira from the Shamela library (shamela.ws; the user can supply a printed-edition scan if the site is unusable). Parse each into entries: index, the hadith wording given, the author's stated companion count and companion names where given, his cited sources. Store as `lists/kattani.yaml`, `lists/suyuti.yaml` with the source URL/edition and page per entry.
* Match each entry to meaning groups deterministically: normalize (strip diacritics and taṭwīl; conservative letter normalization as a versioned function), token-set overlap and opening-phrase match against `meaning_groups.nass` and against member matns (`hadiths.nass[matn_start:matn_end]`). Write `lists/candidates.csv` (entry → top-5 groups with scores). Auto-confirm only when the top score clears a high threshold and the margin to the second is large (both in config); everything else is `needs_review`. Write `lists/confirmed.csv` as the mapping the pipeline reads, with a `confirmed_by` column (`auto` / `human`) — the human rows are filled by the user, not by you. An entry may map to several groups (the authors list topics).
* Join and bin. For each entry: the matched groups, the pooled bundle (section E), companions on path, κ at every threshold on the pool and on the best single group, the author's own count beside ours, and the bin: `wording` (a single group reaches `tawatur_n` at `all`), `meaning_only` (only the pool does), `below_threshold_in_this_data`, `unmatched`. Table in `reports/lists.md`; figure `fig3_lists_bins`.

D. The common-link census

* `out/narrators.parquet`: per narrator — groups on path; groups as cut vertex at `all` and at `thiqa_up`; groups as common link; groups in a bypass; share of his incoming links that are muʿanʿan where he is a mudallis; death year, tabaka, Taqrīb level.
* Distributions: common-link death years and tabaka, overall and split by collection class (Ṣaḥīḥayn-only groups / `tasnif_no = 1` / all); the top-30 common links by count. Figure `fig4_cl_death_years`. Sanity check written into the report: al-Zuhrī, Qatāda, al-Aʿmash, Shuʿba and Mālik should be near the top; if they are not, find out why before closing.

E. Pooled bundles

* `itibar pool` over any set of groups: build one bundle from all their chains (same builder), compute κ at every threshold, width profile, number class, companions. Expose for topic nodes (`--topic <id>`, all groups under the node) and list entries (`--entry kattani:<n>`). Note in README that a pool mixes distinct reports, so pooled κ measures tawātur in meaning at the granularity of the pool, not of a wording.
* Two case studies run and saved: the Mahdī and Dajjāl topic subtrees (find the nodes in `topics`).

F. The chapter census

* For every level-1 and level-2 topic node: groups; share with κ_all = 1; share with κ_thiqa_up ≤ 1; median κ_all; share by `number_class`; share whose v2 grade depends on corroboration (v1 ≠ v2). Table in `reports/chapters.md`; figure `fig5_chapter_census` restricted to the level-1 nodes.

G. Carried over

* Split `kappa_nocompat_θ` into `kappa_nocompat_years_θ` (only links incompatible by the years rule removed — strong evidence) and the existing all-incompatible version; κ_lower keeps using the all-incompatible one; the paper quotes both.
* Misresolution rate from gold: for each gold entry, documented misresolution/dropped-link chains over in-scope chains; the pooled rate; written to audit §10 as the indicative chain-level error rate for the limitations section.

Gold (extend `tests/gold/gold.yaml`; all existing entries unchanged)
Each new entry cites its classical source with `confidence`. Locate the groups in the data and verify the narrators' Taqrīb levels before encoding.

* siwāk through Muḥammad b. ʿAmr b. ʿAlqama (law lā an ashuqqa ʿalā ummatī la-amartuhum bi-l-siwāk; Muḥammad b. ʿAmr ← Abū Salama ← Abū Hurayra; Ibn al-Ṣalāḥ's example of ḥasan raised to ṣaḥīḥ by other routes). Assert: the best chain's weakest narrator is Muḥammad b. ʿAmr at level 5; corroboration fires; final code is 1 under `ibn_hajar` and 0 under `ibn_al_salah`.
* the sandals dowry through ʿĀṣim b. ʿUbaydallāh (a woman of Banū Fazāra married for two sandals; Ibn Hajar's Nuzha example of ḥasan li-ghayrihi). Assert: weakest is ʿĀṣim at level 8; corroboration fires; final code 1 under both rulesets.
* a maqbūl chain repaired: one real case where the weakest narrator is level 6 and a mutābaʿa exists; assert the upgrade to code 1 (Ibn Hajar's Taqrīb definition of level 6). Choose and document.
* fatal weakness not repaired: one group whose chains all pass through level 11–12 narrators on several routes; assert no upgrade.
* number class: innamā al-aʿmāl (scope ʿUmar) → `gharib_mutlaq`, tafarrud layers include layer 1; lā yuʾminu aḥadukum → `aziz` (Ibn Hajar's own example); man kadhaba → `mutawatir_count` at N = 10; one mashhūr example with its source.
* qarāʾin: innamā al-aʿmāl → `in_sahihayn` true; a gharīb report not in the Ṣaḥīḥayn → false.
* lists: the Kattānī entry for man kadhaba must auto-match group 1.

Gates: v2 agreement with recorded grades ≥ v1 agreement under both rulesets (report the numbers; do not tune to raise them); `other = 0` from PR 2 still holds; all previous gold entries pass unchanged.
Housekeeping

* `derive.version: 2`, `structure.version: 3` on records. DECISIONS D35+ for every choice, with the alternative. README: every definition above with its formula and classical source (Nuzhat al-Naẓar, Nukhbat al-Fikar, Muqaddimat Ibn al-Ṣalāḥ, Taqrīb al-Tahdhīb introduction) — fetch the texts (shamela.ws, usul.ai) and quote the rule sentences in Arabic with the reference, so the README is checkable against the books. Regenerate audit, gold report, all figures and CSVs, the fixture (it will need the gold groups added), the README numbers. CI green on the fixture. Open a PR against `main`; subagents for reading, cheaper models for them.

What's on the shelf

* `src/itibar/structure.py`: `threshold_succ`, `vertex_connectivity` (flow), `on_path_subgraph`, `layers`, width profile, cut vertices, common links — corroboration is "connectivity with a node set removed", number class is "min over the existing width profile", pooling is "the existing builder over a union of chains".
* `src/itibar/derive.py`: v1 grade and receipt; `grades.yaml` levels and thresholds (Taqrīb 1–12; higher = weaker; ordinal = 13 − rank_no).
* `src/itibar/bundle.py`: `ChainInfo` with `ends_companion`, `gaps`, `connected`, `compiler_at_pos0`; edge occurrences carry the transmission word and `edge_muanan` is already computed.
* `topics` table: nested set with `lft/rgt`, leaves linked to meaning groups; `books.tasnif_no`; `books.id` 1 = al-Bukhārī, 2 = Muslim (verify).
* Classical texts: Nuzhat al-Naẓar (the corroboration sentence: "ومتى توبع السيئ الحفظ بمعتبر، كأن يكون فوقه أو مثله لا دونه، وكذا المستور والمرسل والمدلس، صار حديثهم حسنًا لا لذاته بل بالمجموع"; the three qarāʾin for āḥād yielding knowledge; mutābaʿa tāmma/qāṣira and shāhid; ʿazīz example lā yuʾminu aḥadukum; ḥasan li-ghayrihi example ʿĀṣim b. ʿUbaydallāh); Taqrīb introduction (level 6: "مقبول حيث يتابع وإلا فلين الحديث"); Muqaddimat Ibn al-Ṣalāḥ (siwāk through Muḥammad b. ʿAmr; iʿtibār / mutābaʿāt / shawāhid); al-Suyūṭī's preface to al-Azhār ("ما رواه من الصحابة عشرة فصاعدًا"); Ibn Hajar in Fatḥ al-Bārī on innamā al-aʿmāl ("مشهور بالنسبة إلى آخره غريب بالنسبة إلى أوله ... أكثر من مائتي إنسان أكثرهم أئمة").

Decisions already made

* Rulesets `ibn_hajar` (default) and `ibn_al_salah`, both computed and stored. Light = {5, 6, 7, 8} + mursal + muʿanʿan-by-mudallis; 9 not repairable; fatal = {10, 11, 12} and mid-chain break markers. Corroborating route must avoid the weak nodes and be light-or-better; divergence class stored. `tawatur_n` = 10. Number class on Taqrīb layers 1–12 at `all`. Qarāʾin reported as flags only.
* The lists mapping is confirmed by a human for every non-obvious match; the pipeline never confirms by itself beyond the documented auto rule. No embeddings anywhere; deterministic token overlap only.
* Nothing is tuned to improve agreement with the recorded grades.

Out of scope
The text layer (alignment, variants, congruence) — bucket 3. The site. Any name-resolution model.
How to work
Verify every rule against the classical text before encoding it, and quote it in the README. The gold tests and the regenerated reports are the arbiter. Where the data or the sources present a case these definitions do not settle, choose, record it in DECISIONS with the alternative, and keep going.
