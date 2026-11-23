# itibar — the site: every hadith's transmission, browsable, with a receipt for every number

Paste as the first message of a fresh session opened at the root of `itibar` on `main`. Save this file as `docs/prompts/site.md` in the PR. Read `README.md`, `DECISIONS.md` and `docs/prompts/bucket-1.md` before writing code; they define every term used below.

## What itibar is, and what the site is for

Every hadith comes with an isnad — the chain of named people who passed it down to the book that records it. Overlay every chain of one report across all books and you get a graph from the Prophet to the books: the isnad bundle. itibar builds that graph for every one of 20,745 reports in a 715k-narration corpus (hadith-kg, CC-BY) and computes on it what the hadith sciences have always computed by hand: how many independent routes a report has (κ, a minimum vertex cut, at four narrator-grade thresholds), who all routes pass through (cut vertices), where it first fans out (common links), the classical number class, and the grade the critics' narrator verdicts imply, with and without corroboration — with a receipt for every number. The outputs are a dataset, a paper, and a site.

The site is how anyone — a student of hadith, a Western historian of early Islam, a curious Muslim — sees this for a report they care about. The test: someone types a few words of a hadith they know, lands on its page, and within a minute can see how it reached the books, through whom it narrowed and where it spread, what the numbers are, and how each number was computed, down to the chains. The same standing rule as the machinery: the site shows what is computed and what the sources record, side by side, and issues no verdict of its own; it never uses "weak" or "fabricated" in its own words.

## The task

Build a static site generated from itibar's outputs that gives every report and every narrator on a route a page, with search, and deploy it.

## Definition of done

1. **Report pages** — one per meaning group with chains (20,282; the 463 without chains get a short page saying so):
   * The report: its opening (`tarafs`), one full text, and the books it is in with hadith numbers.
   * The bundle, drawn: the Prophet at the top, companions, the generations down to the compilers and books; on-path nodes only by default with a switch to show everything; nodes shaded by Taqrīb level; cut vertices and common links marked; hover or tap a node for name, death year, level and label; pan and zoom; the four threshold views (everyone → thiqa only) as a toggle that greys out the narrators below the threshold and shows κ change. Large bundles (thousands of nodes) stay usable: collapse long single strands, cap with an explicit "show all".
   * The numbers: κ at each threshold with κ_lower, the number class, the cut vertices, the common link(s) with death year, the terminus.
   * The grade: the derived grade v1 and v2 under both rulesets, the rule that fired, the defects, the witness chain(s) for an upgrade with their divergence class; beside it, labelled as the source's, the recorded grade and its sentence. Every one of these expands into its receipt (the `steps` stored in `out/records.parquet`).
   * The chains: every chain as a row (book, hadith number, the narrators in order with the transmission word before each, the source's chain grade), filterable by book.
   * Gold: where the report is a gold entry, the classical claim, its source, and what itibar finds.
   * Where `out/verdicts.parquet` exists (PR 7, being built in parallel, extracts the critics' own remarks — al-Tirmidhī's verdicts, al-Ṭabarānī's tafarrud statements — and scores them against the bundle), a panel "what the critics said" with each quote and its result. Build the panel against PR 7's branch if it has landed when you get there; otherwise render nothing for it and leave the reader code in place, tested on a small synthetic file.
2. **Narrator pages** — one per narrator on any route: names as the data gives them, death year, tabaka and Taqrīb layer, level and label, tadlīs tier, conditional rulings with their quotes, and the reports in which he is a common link, a cut vertex, or on a route (counts, and lists linking to the report pages).
3. **Corpus pages** — home (what itibar is in a few sentences, with "Actions are only by intentions" through ʿUmar as the worked example, linking to its page); method (the README's method sections, rendered); figures (fig1–fig6 with their captions and CSV links); the gold set (each classical case, its source, the result); the residue report; downloads (the Parquet outputs, the CSV figure data, licences, how to cite).
4. **Search** — client-side, diacritic- and tatweel-insensitive Arabic (`lists.normalize` rules, applied identically at index and query time), over report openings and texts, narrator names, and book + hadith number. A query returns in under a second on a phone.
5. **Build and deploy** — `make site` writes `site/dist` from `out/*.parquet`, `reports/`, `figures/` and the source tables; nothing on the site is computed in the browser except drawing and search. A GitHub Actions workflow builds the site on the fixture in CI (every page type renders, internal links resolve, no page above a size budget you set and justify) and deploys the full build to GitHub Pages from `main`. The full build must fit GitHub Pages' limits (1 GB published size): measure it and choose the representation accordingly — e.g. precomputed layouts as compact JSON drawn client-side rather than 20k SVG files, sharded search index — and record the numbers.
6. **Reading** — English interface, Arabic content right-to-left with a proper Arabic face, readable on a phone, light and dark, no tracking, no external requests at runtime except the fonts if self-hosting them is impractical (prefer self-hosting).

## Housekeeping

* The generator lives in `src/itibar/site/` (Python, templates) with any client code in `site/` (small, dependency-light; no framework unless it pays for itself). Tests for the page builders and the search normalizer.
* README: a "The site" section (what it shows, how to build it locally, the URL once deployed). DECISIONS: entries for the representation, the size budget, and the search design, each with the alternative.
* Open a PR against `main`; commits authored as the repository owner (`Haseeb Chaudhry <haseeb@crescentintel.com>`), no agent attribution trailers of any kind. If `main` moved while you worked (PR 7), rebase and rebuild before opening.

## What's on the shelf

* `out/records.parquet` (one row per group: κ_θ, κ_lower, cut vertices, common links, number class, v1 / v2 codes, rules, receipts as JSON `steps`, residue tags), `out/chains.parquet` (one row per chain: narrators, words, chain codes, the source's `matn_no`), `out/nodes.parquet` / `out/edges.parquet` (the bundles), `out/narrators.parquet` (the census), `reports/*.md`, `figures/*`, `tests/gold/gold.yaml`, `lists/conditional.yaml`, `lists/mudallisin.yaml`.
* `src/itibar/cli.py` — `show` (a group's record as a card: the information hierarchy of a report page) and `to_dot` / `render` (the Graphviz drawing, on-path pruning, `max_nodes`): start from these.
* `make data` downloads the pinned source; `make all` rebuilds every output (about half a minute for the pipeline).

## Decisions already made

* Static, generated, deployed to GitHub Pages from `main`; no server, no database, no analytics.
* The derived grade and the recorded grade are always shown side by side and labelled by whose they are; no wording of the site's own judges a report.
* Every number on a page can be expanded to the steps that produced it.

## Out of scope

New computation of any kind (the site reads outputs; if a number it needs is missing, add it to the pipeline in this PR with a test and say so); the paper; a custom domain (a one-line CNAME later).

## How to work

Build the report page for group 319 (innamā al-aʿmāl) end to end first, including the drawing at all four thresholds, then a large bundle (a mutawātir entry from the gold set), then the narrator page, then generalise. Look at the pages in a browser as you go — desktop and a phone-sized viewport — and fix what reads badly before moving on.
