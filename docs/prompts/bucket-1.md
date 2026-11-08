# itibar — bucket 1: ingest, audit, bundles, structure, grade derivation v1

Paste this as the first message of a Claude Code session opened at the root of the empty `itibar` repo.

## Why this exists

Every hadith (a report of something the Prophet said or did) comes with an isnad: the chain of named people who passed it down, e.g. "Bukhari heard it from al-Humaydi, who heard it from Ibn Uyayna, who heard it from Yahya b. Sa'id ... who heard the Prophet say it." A single report is recorded in many books through many chains. Overlay every chain for one report and you get a directed graph from the Prophet to the books — the "isnad bundle." The classical Islamic science of hadith graded reports by the shape of this graph and the reliability of the people in it: many independent routes at every generation = tawatur (mass transmission, certainty); the weakest narrator caps a chain's grade; corroborating chains can lift a grade. Western critical hadith studies analyze the same graph under different names (common link, partial common link, single strand, dive). Both traditions do this by hand, one hadith at a time, over months, so almost no report has ever had it done thoroughly.

itibar is an open research project that computes this analysis for every report in a 715k-hadith corpus, reproducibly, from open data, and publishes three things: a dataset, a paper, and a site. The name is the classical term for exactly this operation — gathering all the chains of a report to see what corroborates what.

One design rule governs everything: the machinery computes structure and derives grades mechanically from the classical narrator verdicts, with a receipt for every number. It never issues a verdict of its own, never uses ML to predict authenticity, and never uses words like "weak" or "fabricated" in its outputs. It reports cut values, widths, grades-as-derived, and the data they came from. Interpretation is left to the reader; the site will later show the classical reading and the critical reading of the same facts side by side.

## The task

Build the pipeline that turns the hadith-kg SQLite database into one structural record per meaning group (= per distinct report): the bundle graph, its width profile and vertex connectivity at grade thresholds, its key figures, its continuity checks, a mechanically derived grade with receipt, and comparisons against the grades recorded in the source — for all 20,745 meaning groups, validated against a gold set of hadith whose structure is classically documented.

## Definition of done

1. `make data` downloads `hadith-kg.db` (Hugging Face dataset `emadjumaah/hadith-kg`, file `hadith-kg.db`, CC-BY-4.0, ~1.6 GB) into `data/` and converts the tables we use to Parquet/DuckDB under `data/parquet/`. The source file is read-only input: never modified, never committed.
2. `make audit` writes `reports/audit.md`. It re-verifies everything in the upstream `DATA_REPORT.md` that we depend on, and adds:
   * the full vocabulary of `rawis.rank` with counts, and the `rank_no` ordering — confirm whether higher `rank_no` means weaker, as `sanads.max_rank` = "weakest narrator's rank_no" implies;
   * the `tabaka` distribution and whether it matches Ibn Hajar's twelve generations;
   * coverage of `birth_year` / `death_year` (parsed vs raw-only vs missing), by tabaka;
   * how many hadith have an inline mention sequence that aligns exactly with their chain (upstream reports 216,177 of 307,205 single-chain hadith) — this is what lets us read the transmission word before each narrator;
   * the 421 same-name distinct-person clusters, the 25 stub narrators, the 17,811 marfu'/qudsi chains not ending in a companion, and the 461 groups with no hadith;
   * anything else you find that would change a connectivity number.
3. `make bundles` builds B(g) for every meaning group and writes:
   * `out/bundles/` — per-group nodes and edges (Parquet, partitioned), edges carrying the set of chain ids and book ids they come from and the transmission word where recoverable;
   * `out/records.parquet` — one row per group with: width profile by tabaka; kappa at four thresholds (everyone / above severely-weak / saduq and above / thiqa and above); kappa_lower (recomputed with homonym clusters merged and stubs removed); distinct companions (and the source's `sahaba_qty` beside it); single-strand nodes; partial common links at k=2 and k=3; common link(s); cut vertices; bypass-path count; terminus (death year of the common link and of each cut vertex); mursal-chain count; per-edge continuity flags rolled up (count compatible / incompatible / unknown; count mu'an'an-by-mudallis); derived grade with receipt; recorded grades from `hadiths.matn`, `sanads.matn`, `meaning_groups.matn_no`; agreement flags. The whole run should finish in well under an hour on an M-series laptop. If networkx is the bottleneck, switch the connectivity computation to rustworkx.
4. `make gold` runs tests on a gold set of at least 20 hadith whose structure is classically documented, asserting that the computed structure matches the documented one. Each gold entry records the expectation and its classical source (al-Kattani's Nazm al-Mutanathir for mutawatir claims; Ibn Hajar's Nuzhat al-Nazar / Ibn al-Salah's Muqaddima for the standard gharib examples). Seeds, to be verified and extended by you:
   * innama al-a'mal bi-l-niyyat — expect kappa = 1 with cut vertex Yahya b. Sa'id al-Ansari (d. 143 AH), a single strand of four above him, a wide fan below him;
   * man kadhaba 'alayya muta'ammidan — expect dozens of companions and kappa well above 1 (upstream shows it as group 1 with 63 recomputed companions);
   * nahy 'an bay' al-wala' wa hibatihi — the textbook gharib sahih: expect kappa = 1 at 'Abdullah b. Dinar below Ibn 'Umar;
   * al-din al-nasiha (via Tamim al-Dari) — classically cited as gharib at its root; verify and encode;
   * the standard mutawatir examples from al-Kattani's list: al-mash 'ala al-khuffayn, raf' al-yadayn, al-hawd, al-shafa'a, ru'yat Allah, nazala al-Qur'an 'ala sab'ati ahruf, man bana masjidan — expect high companion width; record the actual kappa at each threshold rather than asserting a number, but assert kappa_everyone > 1;
   * buniya al-Islam 'ala khams — a well-known mashhur report with modest early width; encode what the sources say. Tests fail if the structure disagrees with a documented expectation. Two further gates: our weakest-link per chain must equal `sanads.max_rank` for more than 99% of chains (investigate every class of disagreement and document it); our recomputed companion count must sit within the band the upstream audit shows against `sahaba_qty`.
5. `itibar show <group_id>` prints the record as a readable card (Arabic text, narrator names, the numbers, the receipt). `itibar render <group_id>` writes an SVG of the bundle via Graphviz: layered by tabaka, Prophet at top, books at the bottom, cut vertices marked, single strands visually distinct.
6. `make figures` produces `fig1`: the distribution of kappa across all groups at each of the four thresholds; and a heatmap of width by tabaka for the Sahihayn (`books.tasnif_no = 1`, and specifically Bukhari and Muslim) versus the rest of the corpus.
7. `README.md` documents every definition below in plain English with the formula, the config files, and how to reproduce from scratch. `DECISIONS.md` records every choice the data forced that these definitions didn't settle, with the alternatives. Tests pass in CI (GitHub Actions) on a sampled fixture (`make fixture` generates it: the gold-set groups plus a few hundred random groups, small enough to commit) so CI never needs the 1.6 GB file.

## What's on the shelf

Verified facts about the data, from the upstream `build_hkg.py` and `DATA_REPORT.md`. Do not rediscover them; do verify them in the audit.

Schema:

* `sanad_rawis(sanad_id, pos, rawi_id)` — one chain as ordered narrator links. `pos 0` = book author, ascending toward the companion. Edges therefore run from `pos+1` (teacher) to `pos` (student).
* `sanads(id, hadith_id, matn_no, matn, hukum, group_id, takhrij, max_rank, length)` — one chain of one hadith. `matn`/`matn_no` = recorded grade of this chain; `hukum` = the source's full sentence on the chain; `takhrij` = the source's route-cluster id within the group (a partition of routes you can compare your branch structure against); `max_rank` = weakest narrator's `rank_no`; `length` counts distinct narrators.
* `hadiths(id, book_id, no_inbook, page_no, type_no, type, matn_no, matn, group_id, takhrij, taraf_nass, nass, matn_start, matn_end)` — `type_no` 0 qudsi, 1 marfu', 2 mawquf, 3 maqtu'; `nass` is the plain text of sanad + matn; the matn is `nass[matn_start:matn_end]`; `group_id` is NULL for mawquf/maqtu'.
* `hadith_rawis(hadith_id, seq, rawi_id, start, end)` — inline narrator mentions as [start, end) character offsets into `nass`, in text order. The transmission word is the token or two immediately before `start`.
* `rawis(id, name, nickname, rank_no, rank, tabaka, is_bukhari, is_muslim, has_ikhtilat, has_tadlis, riwaya_qty, birth_year, birth_year_raw, death_year, death_year_raw, age_raw, profession, nasab, iqama, death_place)`.
* `meaning_groups(id, taraf_id, is_qudsi, matn_no, sahaba_qty, repeat_qty, nass)` — one row per report; `nass` is the normalized opening phrase; `matn_no` the recorded overall grade (0 sahih, 1 hasan, 2 da'if, 3 severely weak, per upstream comment — verify).
* `tarafs`, `topics` (nested-set subject tree; leaves link to meaning groups), `aqwal(alem_id, rawi_id, qawl)` and `alems` (critic statements on narrators) — load them all; this bucket uses only `topics` incidentally and `aqwal` not at all, but bucket 2 needs them in Parquet.
* `books(id, name, author_no, author_name, author_death_year, city, dar, tabaa, tasnif_no, tasnif, hadith_qty)` — `tasnif_no 1` = the Sahih/mustakhraj class.

Upstream audit facts: 715,790 hadith; 577,024 chains; 4,414,211 chain links; 49,844 narrators; 20,745 meaning groups (461 empty; 522 marfu' hadith with no group); 17,811 marfu'/qudsi chains whose end is not a companion; 421 same-name distinct-person clusters (homonyms, not merge candidates — but the obvious place resolution errors hide); 25 stub narrators the source never described; 1,988 narrators whose declared narration count is off by more than 10x; declared `sahaba_qty` runs a few percent above recomputed on the largest groups; `sanads.length` disagrees with distinct narrators in 60 chains.

Provenance: the upstream repo builds from a 2017 MongoDB dump of an Arabic hadith project it does not name, plus a meaning-groups CSV. Record this in README as a known limitation. We redistribute only our derived outputs, under CC-BY-4.0 with attribution to hadith-kg.

## Definitions to implement

Parameters live in `config/`. Every definition below gets a README entry.

* Bundle B(g). Nodes: every narrator appearing in any chain of any hadith with `group_id = g`, plus `PROPHET` (virtual source), plus one sink node per book that records the report. Edges: teacher -> student for adjacent positions in each chain; `PROPHET -> last narrator` only when that narrator's rank is the companion rank; `author (pos 0) -> book(hadith.book_id)`. Chains ending in a non-companion are kept in the bundle and flagged mursal; they do not connect to `PROPHET`. Each edge carries the set of `(sanad_id, book_id)` it came from and the transmission word when recoverable.
* Layers. `rawis.tabaka`; fall back to graph depth from `PROPHET` where tabaka is missing or produces an edge going backward by more than one layer, and record the fallback.
* Width profile. Distinct nodes per tabaka among nodes lying on at least one `PROPHET -> book` path.
* kappa. Minimum vertex cut between `PROPHET` and a super-sink joined to all books, computed by node splitting + max flow (networkx `node_connectivity` / `minimum_node_cut`, or rustworkx). By Menger's theorem this equals the maximum number of internally vertex-disjoint routes; store the cut set and one maximal set of disjoint routes.
* Grade ordinal and thresholds. Build an ordinal grade per narrator from `rank` / `rank_no`; write the mapping to `config/grades.yaml` listing every observed rank label and its ordinal, with the companion rank at the top. `kappa_theta` = kappa on the subgraph of narrators with grade >= theta. Four thetas: everyone; above severely-weak; saduq and above; thiqa and above. Name the four columns by threshold, not by number.
* kappa_lower. kappa after merging each same-name cluster into one node and dropping stub narrators. This is the pessimistic bound every headline number must survive.
* Single strand. A node with exactly one in-neighbor and one out-neighbor among on-path nodes.
* Partial common link (k). A node with at least k out-branches whose reachable sub-bundle is not entirely single-strand (it reaches a book through at least one non-single-strand node, or directly). Report k=2 and k=3.
* Common link. A partial common link with no partial-common-link ancestor. If several qualify, report all of them.
* Bypass paths. `PROPHET -> book` paths avoiding the common link. Zero iff the common link is the unique cut vertex.
* Terminus. `death_year` of the common link and of each cut vertex, with `death_year_raw` kept beside it.
* Continuity per edge (u teacher, v student). Compatible if `death_year(u) >= birth_year(v)` when both are known; otherwise if `tabaka(v) - tabaka(u)` is in {0, 1, 2}; otherwise incompatible; unknown when the data can't say. Mu'an'an-by-mudallis: `has_tadlis(v) = 1` and the transmission word before v's mention in that hadith is one of عن / أن / قال — evaluated only for hadith whose mention sequence aligns with the chain; otherwise "unknown word".
* Derived grade v1. Chain grade = minimum narrator grade over the chain excluding the author node. Best chain = the chain with the maximum chain grade (widest path). Group derived grade = best chain grade. Receipt = ordered list of (check, rule applied, data read, result). No corroboration upgrades in v1 — leave the hook and a config stub; bucket 2 adds them.
* Comparisons. Derived chain grade vs `sanads.max_rank` (must agree); derived group grade vs `meaning_groups.matn_no` and vs the modal `hadiths.matn_no` in the group. Store agreement flags. Never overwrite a recorded value.

## Decisions already made

* Python 3.12, managed with uv. DuckDB + Parquet for storage. networkx first, rustworkx if needed. Graphviz (`dot`) for rendering. pytest. Makefile targets as named above. Config in YAML. No web framework in this bucket.
* Arabic text is stored as-is; any normalization is a separate derived column produced by a versioned function.
* The source database is read-only input and is never committed. CI runs on the sampled fixture.
* Open a PR for the work. Subagents are fine for reading and scouting; use cheaper models for them.

## Out of scope for this bucket

Text alignment and congruence; corroboration upgrade rules; the classical mutawatir lists; narrator-level corpus statistics; the site; anything with ML.

## How to work

Work it as you see fit. The gold tests, the `max_rank` agreement gate, and the audit report are the arbiter. Where the data forces a choice these definitions don't settle, choose, record the choice and its alternatives in `DECISIONS.md`, and keep going.
