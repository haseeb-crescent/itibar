itibar — PR 7: what the recorded grade is, and the critics' own verdicts
Paste as the first message of a fresh session opened at the root of `itibar` on `main` (PR 6 is merged). Save this file as `docs/prompts/pr-7.md` in the PR. Read `README.md`, `DECISIONS.md` (D1–D79), `reports/audit.md` §1, §11 and `reports/residue.md`, and the briefs in `docs/prompts/` before writing code; they define every term used below.
What itibar is
Every hadith comes with an isnad — the chain of named people who passed it down to the book that records it. Overlay every chain of one report across all books and you get a graph from the Prophet to the books: the isnad bundle. itibar builds that graph for every one of 20,745 reports in a 715k-narration corpus (hadith-kg, CC-BY) and computes on it what the hadith sciences have always computed by hand: how many independent routes a report has (κ, a minimum vertex cut, at four narrator-grade thresholds), who all routes pass through (cut vertices, common links), the classical number class (gharīb / ʿazīz / mashhūr / mutawātir), and the grade the critics' narrator verdicts imply, with and without corroboration (v1 best chain, v2 the classical ladder under two rulesets, tiered tadlīs, the unnamed companion, conditional narrator rulings) — with a receipt for every number. The outputs are a dataset, a paper, and a site. The standing rule: the machinery computes and reports; it never issues a verdict of its own, never uses "weak" or "fabricated" in its own outputs, and where the tradition has two readings both are implemented as selectable rulesets. Nothing is tuned to raise agreement with anyone's grades.
Why this PR exists
Until now the only external check on the grades has been agreement with the source's recorded group grade (`meaning_groups.matn_no`): v1 72.7%, v2 71.5% (`ibn_hajar`). Review of PR 6 found that this number does not measure what the residue report says it measures, and that a far better test set has been sitting inside the data.

1. The source's grade is itself a mechanical template. `sanads` carries a recorded grade for every chain (`matn_no`, and `hukum`, a sentence). The sentences are templates filled from the narrator table: «إسناده متصل ، رجاله ثقات» (+ «رجاله رجال الشيخين / البخاري / مسلم»), «إسناد حسن», «إسناده حسن رجاله ثقات عدا X وهو صدوق …», «إسناده حسن في المتابعات والشواهد … عدا X وهو مقبول», «إسناده ضعيف ويحسن إذا توبع», «إسناد ضعيف فيه X وهو ضعيف الحديث», «إسناد ضعيف لأن به موضع إرسال / تعليق», «إسناد شديد الضعف فيه X وهو متروك الحديث». Audit §1 shows the chain code against the chain's weakest Taqrīb level over all 577k chains: levels 2–3 → 0, levels 4, 5 and 6 → 1 (means 1.00, 1.02, 1.05), 7–9 → 2, 10 → 3, 11 → 4. itibar codes levels 5–6 as 2 (`config/grades.yaml`), following Ibn Hajar's own definition of the maqbūl — accepted where followed, «وإلا فلين الحديث». So:
   * v1's 16% / 13% agreement at weakest levels 5 / 6 (audit §11.9) is that convention, not substance; most of the distance between 72% and full agreement is probably the code map.
   * v2's rise at levels 5–6 (to 48% / 45%) is partly coincidence: v2 lifts a corroborated maqbūl chain to 1, and the source gives 1 to every maqbūl chain. It is not, by itself, evidence that corroboration works.
   * On the 347-group test fixture, the group grade equals the best chain's recorded code in 88.5% of groups, lies within the chains' range in 98%, and is better than the best chain in 0.9%; a hadith's grade equals its best chain's in 99.5%. If that holds on the full corpus, the source grades chains by template and takes the best — no corroboration across chains. Then the residue's `chain_choice` (44.8% of disagreements, read as "the source may have graded a particular hadith") and `source_severe` (38%, read as "verdicts on the text") are readings the data can now check directly rather than infer.
   * Template inputs are not only `rank_no`: on the fixture some level-5–6 chains are coded 2 with «فيه يحيى بن عبد الحميد الحماني وهو ضعيف الحديث», and 291 chains whose weakest is the level-12 placeholder are coded 0 «إسناده متصل ، رجاله ثقات». Find out exactly what the template reads.
2. The critics' own verdicts are in the texts. `hadiths.nass` holds the authors' remarks after the matn. In the fixture, 107 of 190 al-Tirmidhī hadith carry «قال أبو عيسى: هذا حديث حسن صحيح / حسن غريب / …» and 59 carry «وفي الباب عن فلان وفلان». al-Ṭabarānī's al-Muʿjam al-Awsaṭ and al-Ṣaghīr close most reports with «لم يرو هذا الحديث عن X إلا Y، تفرد به Z»; al-Bazzār with «لا نعلمه يروى عن رسول الله ﷺ إلا من هذا الوجه»; al-Dāraquṭnī and al-Bayhaqī write «تفرد به فلان»; al-Ḥākim «صحيح على شرط الشيخين ولم يخرجاه». These are per-report claims by third- and fourth-century critics about exactly what itibar computes — who alone carried a report (a cut vertex), whether it is gharīb (κ), which companions also narrated it (shawāhid), whether its men are the Ṣaḥīḥayn's. No one has tested them at corpus scale. They are the external test the paper needs, and the «وفي الباب» lists are the ground truth bucket 3 needs for meaning-based shāhid detection.

The task
Decode the source's recorded grade exactly (chains, then groups), rebase agreement and the residue on that decoding, and build the critics' embedded verdicts into a test set that the graph and the grades are scored against.
Definition of done

1. The source's chain grade, decoded

* Parse every distinct `sanads.hukum` into a template and its slots (the named narrator(s) and the verdict word given for each, the break kind, the «رجال الشيخين / البخاري / مسلم» clause, «روى له البخاري تعليقًا»). Table every template with its count and its `matn_no` distribution.
* Write the template as a v1 ruleset, `source_template`: whatever it reads (level → code map, the verdict word if it is not the level — find which `rawis` column carries «ضعيف الحديث» etc., or whether the source re-grades narrators —, break and placeholder handling, the companion slot, the compiler at pos 0, the unnamed person, tadlīs in the wording «صدوق إلا أنه يدلس»). Reproduce `sanads.matn_no` chain by chain. Report the exact reproduction rate and every residual class with counts and printed examples, and whether the narrator the hukum names is among itibar's weakest positions. The aim is exact reproduction, or a named reason for every chain it misses.
* Add a code-map switch to the derive config, `codes: classical | source` (classical = today's map; source = the template's: levels 4–6 → 1). Every agreement table in audit §11 is printed under both maps, so the paper can separate convention from substance.

2. The source's group grade, decoded

* How `meaning_groups.matn_no` and `hadiths.matn_no` follow from the chain codes: best chain, mode, a particular book, the hadith's own chains? State the rule and its coverage on the full corpus.
* List the exceptions by kind — a group grade better than its best chain (something beyond the chains raised it), worse than its best chain, outside the chains' range — with a printed sample of each, the `takhrij` fields and the hadith texts beside them, so the reader can see what the editors used beyond the template.

3. The residue, rebased

Rewrite `reports/residue.md` and `figures/fig6_residue.*` on the decoding, as three layers that add up:

* chain layer: itibar's chain code under `source_template` against the recorded chain code, chain by chain (what differs in reading the narrator table);
* aggregation layer: the recorded group grade against the recorded best chain (what the editors did beyond the template);
* substance layer: v2 (both rulesets, both code maps) against `source_template` v1 — what corroboration, tiered tadlīs, the unnamed companion and the conditional rulings change, which is the content of the classical ladder. Retire `chain_choice` and `source_severe` in their present reading and replace them with what the decoding shows; keep every tag that stays mechanically true. Record the change in DECISIONS (amending D74). Agreement stays reported, never gated, never targeted.

4. The critics' verdicts, extracted

`src/itibar/verdicts.py`, `out/verdicts.parquet`, `reports/verdicts.md`. Read every hadith text (diacritics and tatweel stripped, `lists.normalize`), in the books whose authors comment on their reports. The books and phrase families below are where to start, not a closed list — survey the corpus for the comment formulas each author uses (n-grams after `matn_end` per book) and cover every family with more than a trivial count:

* al-Tirmidhī (book 3): the verdict («حسن», «صحيح», «حسن صحيح», «غريب» and every combination, «حسن صحيح غريب من هذا الوجه», «ليس إسناده بذاك القائم», «إسناده ليس بمتصل», «مرسل»); its scope («من هذا الوجه», «من حديث فلان»); his tafarrud statements («لا نعرفه إلا من هذا الوجه», «لا نعرفه إلا من حديث فلان»); «وفي الباب عن …» and the companions named; his comparisons («وهذا أصح من حديث فلان»); al-Bukhārī's views he relays («سألت محمدا …»).
* al-Ṭabarānī (al-Awsaṭ, al-Ṣaghīr, al-Kabīr where present): «لم يرو هذا الحديث عن X إلا Y», «تفرد به Z», «لا يروى عن X إلا بهذا الإسناد».
* al-Bazzār: «لا نعلمه يروى عن رسول الله ﷺ إلا من هذا الوجه / بهذا الإسناد», «لا نعلم رواه عن X إلا Y».
* al-Dāraquṭnī, al-Bayhaqī, Abū Nuʿaym, al-Khaṭīb: «تفرد به فلان», «غريب من حديث X تفرد به Y».
* al-Ḥākim (book 12): «صحيح على شرط الشيخين ولم يخرجاه», «على شرط مسلم / البخاري», «صحيح الإسناد ولم يخرجاه»; al-Dhahabī's talkhīṣ comments if the text carries them.
* Abū Dāwūd, al-Nasāʾī, Ibn Khuzayma, Ibn Ḥibbān: their formulas (Abū Dāwūd's «هذا حديث منكر», al-Nasāʾī's «هذا خطأ», «ليس بالقوي», Ibn Khuzayma's «إن صح الخبر»), as the survey finds them.

Each claim is one row: book, hadith id, the quoted span, claim type, its slots. Names in a claim are resolved to nodes among the narrators of that hadith's own chain(s), deterministically, as PR 6 resolved conditions among adjacent narrators; unresolved slots are recorded with the reason and counted. A claim is about the hadith it closes; record which chain(s) it attaches to.

5. The machinery scored against them

For each claim type, quote its classical definition in the README (verified against the Shamela page text as in PR 4–6) and score it:

* Tafarrud («لم يرو هذا الحديث عن X إلا Y», «تفرد به Y», «لا نعرفه إلا من هذا الوجه»): in the group's bundle, is Y a cut vertex of the routes through X (the claim is relative: from X, only Y)? Count holds and fails per critic. For every failure, print the route that breaks it: its book, that compiler's death year against the critic's (a later book preserving a route the critic could not know is different from an earlier book he should have known), whether the breaking route passes the continuity rule, and whether its divergence is a misresolution candidate (a homonym resolved wrongly — feed these to the gold-style error rate of audit §10). This is the central test of the graph core against the critics.
* Gharīb (al-Tirmidhī, with and without «من هذا الوجه»): against the κ number class, absolute and relative.
* al-Tirmidhī's ḥasan: his definition in al-ʿIlal al-Ṣaghīr includes «ويُروى من غير وجه نحو ذلك». For «حسن» alone, «حسن صحيح», «حسن غريب», «صحيح» and «غريب», report κ at each threshold, whether a «وفي الباب» companion route exists, v1/v2 under both rulesets and both code maps, and the narrators' levels. The «حسن غريب» puzzle — how a report needing more than one route can be gharīb — has been argued since Ibn al-Ṣalāḥ; report what the bundles of each verdict class look like and do not resolve it.
* «وفي الباب عن»: for each companion named, is there a chain ending at that companion in the same group, in a sibling group (same lowest topic node, PR 5's sibling search), or anywhere under the same taraf? Report recall of each search scope; and over the true pairs found, the distribution of the idf-weighted Dice score of PR 5 against non-pairs drawn from the same siblings — this says what the 0.32 floor is worth and is the calibration set bucket 3 will use.
* «على شرط الشيخين / مسلم / البخاري»: are all men of al-Ḥākim's chain narrators of both / of the named Ṣaḥīḥ (`rawis.is_bukhari`, `is_muslim`), and in the same student → teacher pairings the Ṣaḥīḥ uses? Count holds per clause; the classical baseline is al-Dhahabī's correction of al-Ḥākim.
* Grade words (ṣaḥīḥ, ḥasan, ḍaʿīf and the rest, each critic separately): against v1 and v2 under both rulesets and both code maps, as crosstabs.
* `figures/fig7_critics.*`: tafarrud holds/fails per critic with the breaking route's book date relative to the critic; al-Tirmidhī's verdict classes against κ.

6. Gold

Add entries from the critics, each with the quote and page: two al-Ṭabarānī tafarrud claims that hold (cut vertex asserted), one that a later book's route breaks (the breaking chain asserted), one al-Tirmidhī «حسن غريب» and one «حسن صحيح» with their κ recorded, one «وفي الباب» list with the sibling groups found, one al-Ḥākim «على شرط الشيخين» that holds and one that al-Dhahabī corrects. All existing 44 entries keep passing.
Gates and housekeeping

* Gates as before: `other = 0`, the max_rank gate, Menger, PR 6's residue and unnamed-companion invariants; new: every parsed claim's quoted span is a substring of its hadith text; the residue's three layers sum to the disagreement count. No agreement gate.
* `derive.version: 5` (the code-map switch and `source_template`). DECISIONS D80+ with the alternative for each. README: the decoding (one paragraph: what the recorded grade is), the critics' test set, and every claim type's classical definition with the Arabic sentence and Shamela page. Regenerate audit, residue, gold report, figures, fixture (add the gold groups and the hadith texts the new gold reads), README numbers. CI green on the fixture.
* Open a PR against `main`; commits authored as the repository owner (`Haseeb Chaudhry <haseeb@crescentintel.com>`), no agent attribution trailers of any kind (no Co-Authored-By, no session links).

What's on the shelf

* `load.py` (`sanads.matn_no` is already loaded per chain as `matn_no`, the hadith's as `hadith_matn_no`), `pipeline.py` (`sanad_matn_no_mode`, `sanad_matn_no_counts`; `out/chains.parquet` has `chain_code`, `weakest_positions`, `matn_no`, `hadith_matn_no` per chain), `derive.py` (v1, receipts), `corroborate.py` (v2, rulesets, variants), `residue.py`, `residue_report.py`, `structure.py` (cut vertices, threshold subgraphs, continuity), `siblings.py` and `matn.py` (sibling search, Dice), `conditional.py` (adjacent-restricted name resolution — reuse for claim slots), `mudallisin.py` (deterministic name matcher), `lists.py` (`normalize`, the Shamela client), `provenance.py` (Taqrīb/Taḥrīr fetches), `words.py` (mention offsets, `matn_start` / `matn_end`).
* `books` (1 al-Bukhārī, 2 Muslim, 3 al-Tirmidhī, 12 al-Mustadrak; find al-Ṭabarānī's, al-Bazzār's, al-Dāraquṭnī's and al-Bayhaqī's ids), `rawis.is_bukhari`, `is_muslim`, `hadiths.takhrij`, `sanads.takhrij`, `sanads.hukum`.
* Classical references: al-Tirmidhī, al-ʿIlal al-Ṣaghīr (his definition of ḥasan and of gharīb); Ibn al-Ṣalāḥ, Muqaddima (the ḥasan, the gharīb, the afrād, the iʿtibār); Ibn Hajar, al-Nukat and Nuzhat al-Naẓar (the ḥasan gharīb discussion, the fard nisbī); al-Dhahabī's Talkhīṣ al-Mustadrak; Ibn Hajar's definition of the maqbūl in the introduction to the Taqrīb.

Decisions already made

* The source's grade is decoded, not assumed: the chain template and the group rule are stated from the full corpus with their coverage.
* The classical code map stays the default; the source map is a reported switch.
* The critics' claims are tested as they are stated — relative claims as relative — and a failed claim is reported with the route that breaks it, never as the critic being wrong: a later book, a misresolved name, and a route the critic judged unreliable are different findings and are kept apart.
* Agreement is reported, never gated, never targeted.

Out of scope
Matn alignment, variants and meaning-based shāhid detection (bucket 3 — this PR only extracts the «وفي الباب» ground truth and scores the existing Dice floor against it); the site; the paper's prose; changing any grade rule to fit any critic.
How to work
Start with the decoding (§1–2): it changes how every later number reads. Survey before parsing: for each book, list the most frequent closing formulas, then write the parsers for what the survey shows. Print samples of every claim type with its parse before scoring anything. Where the data or the sources present a case these definitions do not settle, choose, record it in DECISIONS with the alternative, and keep going. Surface what we did not know to look for — a formula family, a critic, a pattern in where claims fail — that is a goal of this PR, not a distraction from it.
