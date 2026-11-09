# itibar — source audit

Generated 2026-11-09 03:25 by `make audit` (`itibar.audit`) from the Parquet copy of `hadith-kg.db` (Hugging Face `emadjumaah/hadith-kg` @ `8ae7e3d5be28`, sha256 `d528084321e71500…`). Upstream comparison values are from `DATA_REPORT.md` at `emadjumaah/hadith@b5a0cf2`.

Every number below is recomputed. Where itibar's definition differs from upstream's, both are shown.

## 1. Upstream facts re-verified

| quantity | ours | upstream | |
|---|---|---|---|
| rows in `hadiths` | 715,790 | 715,790 | match |
| rows in `sanads` | 577,024 | 577,024 | match |
| rows in `sanad_rawis` | 4,414,211 | 4,414,211 | match |
| rows in `rawis` | 49,844 | 49,844 | match |
| rows in `meaning_groups` | 20,745 | 20,745 | match |
| rows in `books` | 425 | 425 | match |
| rows in `tarafs` | 20,745 | 20,745 | match |
| rows in `hadith_rawis` | 3,339,040 | 3,339,040 | match |
| rows in `hadith_ayas` | 117,194 | 117,194 | match |
| rows in `aqwal` | 127,863 | 127,863 | match |
| rows in `alems` | 1,015 | 1,015 | match |
| rows in `topics` | 54,862 | 54,862 | match |
| meaning groups (id > 0) with no hadith | 461 | 461 | match |
| marfu'/qudsi hadith with no group | 522 | 522 | match |
| marfu'/qudsi chains whose end has rank != 'صحابي' (upstream definition) | 17,811 | 17,811 | match |
| homonym clusters: same (name, nickname), non-stub, >1 narrator | 421 | 421 | match |
| stub narrators (is_stub = 1) | 25 | 25 | match |
| sanads.length != distinct narrators in chain | 60 | 60 | match |
| sanads.max_rank != max(rank_no) over the whole chain incl. pos 0 | 0 | 0 | match |
| narrators whose riwaya_qty is off from chain appearances by >10x | 1,988 | 1,988 | match |
| single-chain hadith | 307,205 | 307,205 | match |
| …whose mention sequence equals the chain minus pos 0 (upstream check) | 216,177 | 216,177 | match |

All upstream facts this project depends on reproduce exactly. Note: `meaning_groups` also has a row `id = 0` (`غير منشور`, "unpublished") with no hadith; upstream excludes it (`id > 0`), so the table holds 462 groups without hadith. `sanads.max_rank` includes the book author at pos 0 (upstream `meta`), which matters for the derived-grade comparison (§8.6).

### sahaba_qty spot check (10 most-narrated groups)

`upstream` = distinct chain-end narrators with rank exactly `صحابي`; `itibar` = distinct companions (rank_no 1 minus the labels that deny companionship, plus the young-companion labels at any rank_no) at chain ends; `on path` = companions narrating directly from PROPHET on an unbroken route to a book (`records.companions`; requires `make bundles`).

| group_id | declared | upstream | itibar | on_path | opening |
|---|---|---|---|---|---|
| 2 | 68 | 63 | 66 | 65 | توضأ فغسل وجهه أخذ غرفة من ماء فمضمض بها واستنشق ث |
| 4 | 46 | 41 | 42 | 41 | إذا قمت إلى الصلاة فأسبغ الوضوء ثم استقبل القبلة ف |
| 3 | 67 | 60 | 61 | 61 | يتوضأ فغسل وجهه ويديه ومسح برأسه ومسح على الخفين |
| 1 | 68 | 64 | 66 | 66 | لا تكذبوا علي فإنه من كذب علي فليلج النار |
| 5 | 44 | 35 | 39 | 35 | صلى لنا رسول الله ركعتين من بعض الصلوات ثم قام فلم |
| 6 | 38 | 31 | 32 | 30 | أقام النبي تسعة عشر يقصر فنحن إذا سافرنا تسعة عشر  |
| 8 | 54 | 45 | 49 | 48 | نهى رسول الله عن الدباء والحنتم والمقير والمزفت |
| 9 | 24 | 20 | 22 | 22 | أن يجعلوها عمرة إلا من معه الهدي |
| 7 | 58 | 56 | 56 | 56 | الله قد حرم على النار من قال لا إله إلا الله يبتغي |
| 21 | 20 | 16 | 17 | 16 | المزابنة بيع الثمر بالتمر كيلا بيع الزبيب بالكرم ك |

The upstream audit table reads group 1 at 64 recomputed companions (the brief's "63" is group 2's figure). Upstream's exact-label rule misses female companions (`صحابية`) and `صحابي صغير`.

## 2. `rawis.rank` vocabulary and the `rank_no` ordering

| rank_no | narrators | labels | taqrib_level | itibar_ordinal | top_labels |
|---|---|---|---|---|---|
| 0 | 25 | 1 | never described (stubs) | 0 |  |
| 1 | 2,315 | 11 | الصحابة | 12 | صحابي |
| 2 | 994 | 165 | أوثق الناس / ثقة ثقة / ثقة حافظ | 11 | ثقة حافظ |
| 3 | 6,173 | 78 | ثقة / متقن / ثبت / عدل | 10 | ثقة |
| 4 | 5,718 | 48 | صدوق / لا بأس به | 9 | صدوق حسن الحديث |
| 5 | 301 | 90 | صدوق سيء الحفظ / يهم / له أوهام / تغير بأخرة | 8 | صدوق يخطئ |
| 6 | 5,901 | 14 | مقبول | 7 | مقبول |
| 7 | 23,001 | 19 | مستور / مجهول الحال | 6 | مجهول الحال |
| 8 | 1,788 | 21 | ضعيف | 5 | ضعيف الحديث |
| 9 | 1,868 | 3 | مجهول | 4 | مجهول |
| 10 | 966 | 14 | متروك / متروك الحديث / ساقط | 3 | متروك الحديث |
| 11 | 540 | 19 | متهم بالكذب | 2 | متهم بالوضع |
| 12 | 254 | 16 | كذاب / وضاع | 1 | كذاب |

**`rank_no` is Ibn Hajar's twelve-level scale from *Taqrib al-Tahdhib*.** The labels are Taqrib's wording verbatim (Malik's `رأس المتقنين وكبير المتثبتين`, al-Bukhari's `جبل الحفظ وإمام الدنيا في فقه الحديث` sit at level 2), and the levels run in Taqrib order: companions → `ثقة ثقة`/`حافظ` → `ثقة` → `صدوق` → `صدوق يهم` → `مقبول` → `مجهول الحال` → `ضعيف` → `مجهول` → `متروك` → `متهم` → `كذاب`/`وضاع`. **Higher `rank_no` is weaker**, confirmed three ways: the label sequence; `sanads.max_rank` = max(rank_no) over the chain (0 mismatches, §1), i.e. the weakest link is the maximum; and the source's own chain grades worsen monotonically with it:

| max_rank | chains | mean_chain_code | share_code0 |
|---|---|---|---|
| 1 | 3 | 1.330 | 0.333 |
| 2 | 15,233 | 0.060 | 0.958 |
| 3 | 131,625 | 0.110 | 0.919 |
| 4 | 98,183 | 1 | 0.055 |
| 5 | 39,122 | 1.020 | 0.028 |
| 6 | 45,383 | 1.050 | 0.025 |
| 7 | 44,475 | 1.870 | 0.032 |
| 8 | 69,550 | 1.950 | 0.015 |
| 9 | 9,783 | 1.990 | 0.007 |
| 10 | 35,636 | 2.930 | 0.007 |
| 11 | 16,633 | 3.860 | 0.006 |
| 12 | 71,398 | 2.270 | 0.070 |

The dip at 12 is the placeholders (§8.1): every chain through a break marker gets `max_rank` 12.

`rank_no = 0` is not a grade: it marks the 25 stub narrators the source never described. The four rows with `rank IS NULL` and `rank_no = 12` are not people at all (§8.1). The full vocabulary — 499 distinct (rank_no, label) pairs with counts and itibar's ordinal — is regenerated into `config/grades.yaml` (`labels:`) by this target and reproduced in Appendix A.

Labels whose wording disagrees with their level (kept at the source's level; itibar grades by `rank_no`):

| rank_no | rank | n |
|---|---|---|
| 1 | له إدراك | 10 |
| 1 | لم تثبت له صحبة | 2 |
| 1 | لها إدراك | 1 |
| 3 | صحابي صغير | 6 |
| 3 | صحابية صغيرة | 2 |
| 3 | مقبول | 1 |
| 4 | صحابي صغير | 3 |
| 6 | انفرد بتوثيقه ابن حبان | 7 |
| 6 | انفرد بتوثيقه ابن شاهين | 1 |
| 7 | ضعيف الحديث | 1 |

### 2.1 Companion label overrides

`grades.yaml: companion.label_overrides` (`صحابي صغير`, `صحابية صغيرة`) makes a narrator a companion whatever its `rank_no`. 11 narrators carry these labels outside rank_no 1 (22 more are at rank_no 1 and were companions already). Their chains now reach PROPHET. Companionship only: the ordinal still follows `rank_no` (DECISIONS D33).

| id | nickname | rank | rank_no | tabaka | death_year | chain_ends | groups |
|---|---|---|---|---|---|---|---|
| 3,165 | زينب بنت أم سلمة المخزومية | صحابية صغيرة | 3 | 1 | 73 | 92 | 18 |
| 4,407 | عبد الرحمن بن عبد القاري | صحابي صغير | 3 | 2 | 88 | 3 | 2 |
| 4,516 | عبد الرحمن بن جارية الأنصاري | صحابي صغير | 3 | 2 | 93 | 14 | 3 |
| 4,645 | عبد الله بن زيد الأنصاري | صحابي صغير | 3 | 2 | 84 | 1 | 1 |
| 4,852 | عبد الله بن سهل الأنصاري | صحابي صغير | 3 | 2 |  | 0 | 0 |
| 4,959 | عبد الله بن عكيم الجهني | صحابي صغير | 3 | 2 |  | 36 | 2 |
| 17,500 | زينب بنت علي القرشية | صحابية صغيرة | 3 | 1 |  | 0 | 0 |
| 25,711 | عمرو بن صليع المحاربي | صحابي صغير | 3 | 3 |  | 0 | 0 |
| 4,072 | عاصم بن عمر العدوي | صحابي صغير | 4 | 1 | 70 | 12 | 4 |
| 17,511 | السائب بن أبي لبابة الأنصاري | صحابي صغير | 4 | 1 |  | 3 | 3 |
| 41,203 | عبيد بن رحى الجهني | صحابي صغير | 4 | 2 |  | 1 | 1 |

Disputed companionship (`مختلف في صحبته` and variants) is not overridden and follows `rank_no`: a companion at rank_no 1, a narrator of that level otherwise.

| rank_no | narrators | companions_in_itibar | chain_ends |
|---|---|---|---|
| 1 | 31 | 31 | 1,120 |
| 2 | 5 | 0 | 20 |
| 3 | 21 | 0 | 241 |
| 4 | 5 | 0 | 19 |
| 6 | 14 | 0 | 95 |
| 7 | 60 | 0 | 218 |
| 8 | 3 | 0 | 69 |

## 3. `tabaka`: distribution, and Ibn Hajar's twelve generations

| tabaka | narrators | with_death | median_death | min_death | max_death | fits_taqrib_rule |
|---|---|---|---|---|---|---|
| 0 | 8,143 | 3 | 576 | 373 | 802 | 0 |
| 1 | 2,365 | 386 | 48 | 2 | 307 | 0.987 |
| 2 | 693 | 157 | 77 | 32 | 135 | 0.924 |
| 3 | 2,949 | 310 | 100 | 39 | 238 | 0.474 |
| 4 | 1,213 | 144 | 121 | 75 | 155 | 0.868 |
| 5 | 1,231 | 154 | 132 | 92 | 168 | 0.981 |
| 6 | 2,585 | 359 | 136 | 90 | 199 | 0.992 |
| 7 | 2,216 | 371 | 162 | 109 | 209 | 0.997 |
| 8 | 1,789 | 389 | 188 | 132 | 211 | 0.915 |
| 9 | 1,966 | 590 | 214 | 180 | 256 | 0.929 |
| 10 | 3,147 | 958 | 241 | 210 | 307 | 1 |
| 11 | 2,489 | 784 | 267 | 200 | 477 | 0.999 |
| 12 | 2,923 | 947 | 292 | 273 | 331 | 1 |
| 13 | 2,621 | 878 | 318 | 300 | 413 |  |
| 14 | 1,621 | 680 | 344 | 268 | 410 |  |
| 15 | 1,612 | 628 | 369 | 341 | 390 |  |
| 16 | 1,082 | 562 | 393 | 375 | 490 |  |
| 17 | 1,088 | 556 | 419 | 396 | 490 |  |
| 18 | 935 | 524 | 445 | 417 | 487 |  |
| 19 | 767 | 464 | 470 | 420 | 492 |  |
| 20 | 830 | 428 | 496 | 441 | 541 |  |
| 21 | 681 | 437 | 524 | 417 | 653 |  |
| 22 | 1,175 | 784 | 543 | 469 | 572 |  |
| 23 | 419 | 308 | 571 | 546 | 595 |  |
| 24 | 539 | 381 | 600 | 556 | 678 |  |
| 25 | 445 | 359 | 625 | 594 | 681 |  |
| 26 | 387 | 281 | 649 | 626 | 711 |  |
| 27 | 307 | 235 | 680 | 610 | 722 |  |
| 28 | 521 | 452 | 700 | 627 | 744 |  |
| 29 | 400 | 349 | 725 | 693 | 761 |  |
| 30 | 307 | 246 | 744 | 666 | 807 |  |
| 31 | 94 | 74 | 769.500 | 738 | 822 |  |
| 32 | 110 | 72 | 803 | 787 | 817 |  |
| 33 | 59 | 36 | 825 | 803 | 841 |  |
| 34 | 71 | 57 | 854 | 837 | 870 |  |
| 35 | 34 | 27 | 870 | 864 | 880 |  |
| 36 | 21 | 7 | 900 | 890 | 906 |  |
| 37 | 8 | 6 | 923.500 | 909 | 933 |  |
| 38 | 1 | 1 | 969 | 969 | 969 |  |

The column runs 0–38, not 1–12. **0 means missing** (8,143 narrators, including the 25 stubs and the four placeholders). Values 1–12 follow Ibn Hajar's layering: `fits_taqrib_rule` tests the rule Ibn Hajar gives in the introduction to *Taqrib* (layers 1–2 died before 100 AH, 3–8 after 100, 9–12 after 200) against the parsed death year. Values 13–38 extend the same scheme past Taqrib to the later compilers, about 25 years per layer (al-Bayhaqi, d. 458, is 19). Individual narrators can sit one layer off Taqrib:

| narrator | rawi id | source tabaka | Taqrib tabaqa |
|---|---|---|---|
| 'Alqama b. Waqqas | 5719 | 2 | 2 |
| Muhammad b. Ibrahim al-Taymi | 6796 | 5 | 4 |
| Yahya b. Sa'id al-Ansari | 8272 | 6 | 5 |
| Yahya b. Sa'id al-Qattan | 8271 | 9 | 9 |
| 'Abdullah b. Dinar | 4797 | 4 | 4 |
| Malik b. Anas | 6659 | 7 | 7 |
| Sufyan al-Thawri | 3436 | 7 | 7 |
| Shu'ba b. al-Hajjaj | 3795 | 7 | 7 |
| Sufyan b. 'Uyayna | 3443 | 8 | 8 |
| Qatada | 6458 | 4 | 4 |
| Nafi' mawla Ibn 'Umar | 7863 | 3 | 3 |
| al-Humaydi | 4698 | 10 | 10 |
| Ahmad b. Hanbal | 488 | 10 | 10 |
| al-Bukhari | 6817 | 10 | 11 |

So `tabaka` is the source's generation scale anchored on Taqrib, not a copy of Taqrib's tabaqa field. Layers are used for the width profile; layer gaps along chain links calibrate the continuity check (§8.5).

## 4. Birth and death years: coverage by tabaka

| tabaka | narrators | death_parsed | death_raw_only | death_missing | birth_parsed | birth_raw_only | birth_missing |
|---|---|---|---|---|---|---|---|
| 0 (missing) | 8,143 | 3 | 0 | 8,140 | 5 | 0 | 8,138 |
| 01 | 2,365 | 386 | 25 | 1,954 | 17 | 2 | 2,346 |
| 02 | 693 | 157 | 8 | 528 | 20 | 0 | 673 |
| 03 | 2,949 | 310 | 14 | 2,625 | 56 | 0 | 2,893 |
| 04 | 1,213 | 144 | 7 | 1,062 | 19 | 0 | 1,194 |
| 05 | 1,231 | 154 | 7 | 1,070 | 23 | 0 | 1,208 |
| 06 | 2,585 | 359 | 21 | 2,205 | 39 | 0 | 2,546 |
| 07 | 2,216 | 371 | 4 | 1,841 | 72 | 0 | 2,144 |
| 08 | 1,789 | 389 | 3 | 1,397 | 85 | 0 | 1,704 |
| 09 | 1,966 | 590 | 2 | 1,374 | 100 | 0 | 1,866 |
| 10 | 3,147 | 958 | 3 | 2,186 | 136 | 0 | 3,011 |
| 11 | 2,489 | 784 | 1 | 1,704 | 95 | 0 | 2,394 |
| 12 | 2,923 | 947 | 28 | 1,948 | 91 | 0 | 2,832 |
| 13+ | 16,135 | 8,832 | 15 | 7,288 | 4,319 | 0 | 11,816 |

Raw-only values are ranges or approximations the build declined to parse, e.g. `130 - 121` (16), `290 - 281` (14), `300 - 291` (11), `23 - 13` (7), `40 - 20` (6), `158 - 136` (6), `35 - 23` (5), `60 - 41` (4). itibar keeps them beside the parsed value (terminus columns) and never parses them itself. Where both the teacher's death and the student's birth are known the continuity check uses years; otherwise it falls back to tabaka (§8.5).

## 5. Inline mentions and transmission words

Upstream's check (single-chain hadith whose full mention sequence equals the chain minus pos 0) reproduces: **216,177 of 307,205**. This is what lets us read the transmission word before each narrator.

itibar's alignment (`itibar.words`) restricts mentions to the sanad part (before `matn_start`), skips break markers (they have no mention), and accepts in-order subsequences for multi-chain (tahwil) hadith:

| method | chains | links |
|---|---|---|
| exact | 237,315 | 1,411,817 |
| subseq | 260,594 | 1,837,809 |

Words are recovered for 3,249,626 of 3,786,705 narrator links (85.8%); chains of 79,115 sanads are unaligned and get `unknown word`.

| class | links | top_forms |
|---|---|---|
| haddathana | 1,279,407 | حدثنا |
| an | 1,245,518 | عن |
| akhbarana | 392,784 | أخبرنا |
| anbaana | 87,856 | أنبأنا |
| (no token) | 72,744 |  |
| samitu | 58,009 | سمعت |
| qala | 46,296 | قال |
| anna | 38,203 | أن |
| other | 17,119 | إلى |
| qiraa | 8,722 | على |
| kitaba | 1,676 | إلي |
| tahwil | 1,292 | ح |

`(no token)`: two mentions with nothing between them (co-teachers joined by `و`).

## 6. Homonyms, stubs, chains not ending in a companion, empty groups

### 6.1 The 421 same-name clusters

| nickname | members | members_in_chains | chain_links |
|---|---|---|---|
| سليمان بن موسى القرشي | 2 | 2 | 1,221 |
| سعيد بن يسار | 2 | 2 | 647 |
| عبد الله بن عامر العنزي | 2 | 1 | 583 |
| أبو عبد الله الأشعري | 2 | 2 | 275 |
| محمد بن موسى الحرشي | 2 | 2 | 233 |
| أبو صالح الأشعري | 2 | 2 | 197 |
| معاوية بن يحيى الشامي | 2 | 2 | 172 |
| إبراهيم بن محمد الأصبهاني | 2 | 2 | 151 |
| عبد الرحمن بن عبد الله السلمي | 2 | 2 | 140 |
| شهاب بن عباد العبدي | 2 | 2 | 106 |
| محمد بن سعد الأنصاري | 3 | 3 | 97 |
| مسلم بن سالم الجهني | 2 | 2 | 95 |

A cluster can only change kappa inside a group where two of its members both occur: that happens 63 times (group × cluster). `kappa_lower` merges every cluster into one node. Misresolution across *different* full names is not caught by these clusters: e.g. `يحيى بن سعيد` resolved to al-Qattan (r8271, nickname `يحيى بن سعيد القطان`) where the student of al-Taymi is al-Ansari (r8272, `يحيى بن سعيد الأنصاري`) in six chains of *innama al-a'mal* (tests/gold/gold.yaml). Same-name clusters by `nickname` alone would be 2,545.

### 6.2 The 25 stubs

| id | name | chain_links | min_pos | max_pos |
|---|---|---|---|---|
| 47,654 | كُرَيْبٍ السَّحُولِيِّ | 6 | 6 | 10 |
| 40,137 | عَبْدُ اللَّهِ بْنُ عُبَيْدَةَ | 6 | 1 | 6 |
| 44,306 | مُحَمَّدِ بْنِ عَبْدِ الصَّمَدِ | 5 | 4 | 9 |
| 51,756 | بِنْتِ كُرْزٍ | 5 | 5 | 7 |
| 50,119 | أَبِي | 4 | 8 | 10 |
| 44,304 | عَبْدُ الْمُؤْمِنِ | 4 | 2 | 7 |
| 44,305 | أَبَاهُ | 2 | 4 | 4 |
| 40,740 | وَمُحَمَّدُ بْنُ الْحُسَيْنِ | 2 | 2 | 2 |
| 47,655 | عَبْدِ اللَّهِ بْنِ حُذَيْمٍ | 2 | 5 | 5 |
| 40,138 | مُحَمَّدُ بْنُ عَمْرٍو | 2 | 1 | 3 |
| 9,481 | غير معرف | 2 | 7 | 7 |
| 50,436 | أَبِيهِ | 2 | 6 | 7 |
| 47,653 | النُّعْمَانِ بْنِ نُعَيْمٍ | 2 | 5 | 7 |
| 60,137 | مَخْرَمَةَ الْعَبْدِيِّ | 2 | 5 | 5 |
| 40,741 | وَأَبُو مُسْلِمٍ | 2 | 2 | 2 |
| 26,043 | عِيسَى بْنُ الأَشْعَثِ | 2 | 4 | 8 |
| 50,437 | السُّمَيْطِ الْبَجَلِيِّ | 2 | 6 | 6 |
| 40,142 | مُحَمَّدِ بْنِ مَطَرٍ | 1 | 2 | 2 |
| 40,260 | قَيْسٌ السَّعِيدِيُّ | 1 | 4 | 4 |
| 45,024 | سَعِيدِ بْنِ عَوْسَجَةَ | 1 | 3 | 3 |
| 60,677 | سَنْجَوَيْهِ النَّاهِكِيُّ | 1 | 3 | 3 |
| 45,025 | جَعْفَر بْنِ الْفُرَافِصَةِ الْحَنَفِيِّ | 1 | 4 | 4 |
| 40,139 | سَعْدِ بْنِ عُثْمَانَ | 1 | 4 | 4 |
| 61,758 | الأَخْنَسِ بْنِ زُهَيْرٍ | 1 | 7 | 7 |
| 60,136 | مَنْدُوسٍ | 1 | 6 | 6 |

Stubs touch 60 chain links. They get ordinal 0 (below every threshold but `all`) and are dropped in `kappa_lower`. Several names are relational (`أبي`, `أبيه`, `أباه`).

### 6.3 Marfu'/qudsi chains not ending in a companion

| chain_end | chains | counted_by_upstream |
|---|---|---|
| companion: صحابي | 521,664 | 0 |
| break marker (30002) | 32,497 | 0 |
| companion: صحابية | 10,646 | 10,646 |
| unnamed person (1131) | 5,040 | 0 |
| companion: صحابي صغير | 3,949 | 3,949 |
| companion: مختلف في صحبته | 1,085 | 1,085 |
| other narrator, rank_no 3 | 855 | 855 |
| rank_no 1, not a companion: له إدراك | 284 | 284 |
| other narrator, rank_no 7 | 264 | 264 |
| companion: له رؤية | 196 | 196 |
| other narrator, rank_no 6 | 116 | 116 |
| other narrator, rank_no 2 | 99 | 99 |
| companion: صحابية صغيرة | 92 | 92 |
| other narrator, rank_no 8 | 72 | 72 |
| other narrator, rank_no 9 | 56 | 56 |
| other narrator, rank_no 4 | 52 | 52 |
| companion: مختلف في صحبته ، والأكثر أنه صحابي | 31 | 31 |
| stub | 11 | 0 |
| companion: لها رؤية | 7 | 7 |
| companion: مختلف في صحبتها | 4 | 4 |
| other narrator, rank_no 5 | 2 | 2 |
| other narrator, rank_no 10 | 1 | 1 |
| break marker (30000) | 1 | 0 |

Upstream's 17,811 counts chain ends whose label is not exactly `صحابي`: it **includes** 10,646 chains ending at female companions and 3,879 at `صحابي صغير`, and **excludes** every chain ending at a NULL-rank placeholder (37,538, mostly `موضع إرسال`, the source's own irsal marker). By itibar's companion rule (rank_no 1, minus `لم تثبت له صحبة` / `له إدراك` / `لها إدراك`, plus the young-companion labels at any rank_no) **39,350** marfu'/qudsi chains do not end in a companion; these are kept in their bundles, flagged mursal, and get no PROPHET edge.

### 6.4 Groups without chains

461 groups (id > 0) have no hadith, group 0 is the `غير منشور` placeholder, and 1 group has hadith but no chain. All get a row in `out/records.parquet` with `status = 'no_chains'`. 4 chains belong to marfu' hadith without a group and are outside every bundle.

## 7. Grade codes (`matn_no`) verified

**meaning_groups**

| matn_no | label_from_tarafs | n |
|---|---|---|
| 0 | صحيح | 6,063 |
| 1 | حسن | 4,675 |
| 2 | ضعيف | 4,153 |
| 3 | شديد الضعف | 2,630 |
| 4 | متهم بالوضع | 2,022 |
| 5 | موضوع | 1,202 |

**tarafs**

| matn_no | label | n |
|---|---|---|
| 0 | صحيح | 6,063 |
| 1 | حسن | 4,675 |
| 2 | ضعيف | 4,153 |
| 3 | شديد الضعف | 2,630 |
| 4 | متهم بالوضع | 2,022 |
| 5 | موضوع | 1,202 |

**sanads**

| matn_no | label | n |
|---|---|---|
| 0 | صحيح | 151,067 |
| 1 | حسن | 186,493 |
| 2 | ضعيف | 170,195 |
| 3 | شديد الضعف | 41,860 |
| 4 | متهم بالوضع | 19,457 |
| 5 | موضوع | 7,952 |

**hadiths**

| matn_no | label | n |
|---|---|---|
| -1 | بدون سند | 1,311 |
| 0 | صحيح | 112,123 |
| 1 | حسن | 126,856 |
| 2 | ضعيف | 112,159 |
| 3 | شديد الضعف | 31,667 |
| 4 | متهم بالوضع | 14,602 |
| 5 | موضوع | 5,961 |
| 6 | موقوف | 118,721 |
| 7 | مقطوع | 191,955 |
| 8 | بدن شواهد أوسند | 435 |

`meaning_groups.matn_no` carries no label; its codes 0–5 decode through `tarafs` (one taraf per group, same code). The upstream comment (`0=صحيح 1=حسن 2=ضعيف 3=شديد الضعف …`) is confirmed and completed: 4 = `متهم بالوضع`, 5 = `موضوع`. `hadiths` adds −1 (no chain), 6 (mawquf), 7 (maqtu'), 8 (no shawahid or chain). itibar quotes these labels as the source's; its own derived grade is expressed as a Taqrib level and a code on this scale.

## 8. Findings that change connectivity numbers

### 8.1 Four placeholder rows are not narrators

| id | name | rank_no | chain_links | chains | at_pos0 | at_chain_end |
|---|---|---|---|---|---|---|
| 30,002 | موضع إرسال | 12 | 32,502 | 32,502 | 5 | 32,497 |
| 1,131 | اسم مبهم | 12 | 15,187 | 14,299 | 312 | 5,040 |
| 30,000 | موضع انقطاع | 12 | 13,996 | 13,852 | 0 | 1 |
| 30,001 | موضع تعليق | 12 | 6,719 | 6,718 | 2,730 | 0 |

`config/grades.yaml: placeholders` lists exactly this set: **yes**. Three are the source's break markers — `موضع إرسال` (irsal: companion dropped), `موضع انقطاع` (inqita': link missing inside the chain), `موضع تعليق` (ta'liq: compiler omitted the start) — and one, `اسم مبهم`, stands for every unnamed person ("a man", "a shaykh"). Each is a single id shared by tens of thousands of chains, and each carries rank_no 12 (the `كذاب` level). Taken at face value they would (a) fuse unrelated routes through one shared hub, inflating kappa and creating false cut vertices, and (b) give every broken chain the lowest possible weakest link. itibar models break markers as one untraversable gap node per chain occurrence (the gap is recorded; no route crosses it) and the unnamed person as one node per (student, teacher) context with unknown grade.

### 8.2 pos 0 is not always the book's compiler

113,130 chains (of 577,024) start with a narrator other than their book's most frequent pos-0 narrator. In primary collections pos 0 is the compiler (al-Bukhari 99.5%, Muslim 99.9%, Ahmad 99.4%); in secondary ones it is the quoted source or the compiler's teacher, and the compiler himself is absent:

| book_id | name | author_death_year | chains | top_pos0_share | compiler_rawi_id | compiler_node |
|---|---|---|---|---|---|---|
| 303 | تاريخ دمشق لابن عساكر | 571 | 38,820 | 0.110 | 46607 | c32 |
| 9 | مسند أحمد بن حنبل | 241 | 32,146 | 0.994 | 488 | c125 |
| 67 | المعجم الكبير للطبراني | 360 | 24,761 | 0.993 | 18570 | c145 |
| 22 | السنن الكبرى للبيهقي | 458 | 23,378 | 0.993 | 9624 | c39 |
| 13 | مستخرج أبي عوانة | 316 | 13,742 | 0.996 | 34193 | c119 |
| 2 | صحيح مسلم | 261 | 13,368 | 0.999 | 7457 | c198 |
| 17 | السنن الكبرى للنسائي | 303 | 12,999 | 0.982 | 9880 | c70 |
| 66 | المعجم الأوسط للطبراني | 360 | 10,030 | 0.995 | 18570 | c145 |
| 14 | المسند المستخرج على صحيح مسلم لأبي نعيم | 430 | 9,093 | 0.998 | 9927 | c120 |
| 62 | مصنف ابن أبي شيبة | 235 | 8,905 | 0.856 | 5049 | c1 |
| 195 | شعب الإيمان  للبيهقي | 458 | 8,819 | 0.992 | 9624 | c39 |
| 1 | صحيح البخاري | 256 | 8,795 | 0.995 | 6817 | c185 |

344 of 423 books with chains have a dominant pos-0 narrator (share >= 0.5); `compiler_rawi_id` is filled when any book by the same `author_no` has one (Ibn 'Asakir is identified through another of his books). 
Without a correction, Ibn 'Asakir's many teachers would enter *Tarikh Dimashq* as parallel routes into an uncuttable book node, so a report found only there through three of his teachers would score kappa 3 although it passed through one man. itibar puts one cuttable compiler node `c<author_no>` in front of every book; every route into a book passes through it.

### 8.3 Self-loops, repeated narrators and cycles

994 adjacent repeats (same narrator at pos and pos+1: a self-loop) and 123 chains repeating a real narrator. Self-loops are dropped and counted per group; non-adjacent repeats and cross-chain contradictions (A from B in one chain, B from A in another) make cycles. Flow, dominators and SCC-based measures handle cycles; path counts are taken on an acyclic reduction and flagged (`paths_on_acyclic_reduction`).

Groups with a cycle in the on-path bundle: 322.

### 8.4 Homonym misresolution across different full names

Not mergeable without a name-resolution model (out of scope, §6.1). The continuity rule (§8.5) is the visible symptom: a wrongly resolved narrator often sits in the wrong generation for his teacher. For every cross-name misresolution documented in `tests/gold/gold.yaml` (and the one candidate), the links into and out of the wrong narrator are checked against the corrected rule. *Caught* means at least one of them is incompatible, so the `nocompat` graph of `kappa_lower` removes that route.

| gold entry | group | sanad | resolved (in the data) | intended | link above: teacher → resolved | link below: resolved → student | verdict | PR 1 rule |
|---|---|---|---|---|---|---|---|---|
| innama-al-amal | 319 | 320050 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-al-amal | 319 | 320051 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-al-amal | 319 | 320052 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-al-amal | 319 | 320053 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-al-amal | 319 | 320054 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-al-amal | 319 | 320055 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| bay-al-wala | 276 | 494475 | عبد الله بن دينار البهراني (r4796) | عبد الله بن دينار القرشي (r4797) | عبد الله بن عمر العدوي: incompatible (tabaka 1 → 6, gap +5) | compatible (tabaka 6 → 8, gap +2) | **caught** | caught |
| bay-al-wala | 276 | 494476 | عبد الله بن دينار البهراني (r4796) | عبد الله بن دينار القرشي (r4797) | عبد الله بن عمر العدوي: incompatible (tabaka 1 → 6, gap +5) | compatible (tabaka 6 → 8, gap +2) | **caught** | caught |
| kalimatan-khafifatan | 2852 | 145572 | عمارة بن عمير التيمي (r5885) | عمارة بن القعقاع الضبي (r5866) | أبو زرعة بن عمرو البجلي: compatible (tabaka 3 → 4, gap +1) | incompatible (tabaka 4 → 9, gap +5) | **caught** | caught |
| kalimatan-khafifatan | 2852 | 145573 | عمارة بن عمير التيمي (r5885) | عمارة بن القعقاع الضبي (r5866) | أبو زرعة بن عمرو البجلي: compatible (tabaka 3 → 4, gap +1) | incompatible (tabaka 4 → 9, gap +5) | **caught** | caught |
| la-yuminu-ahadukum (candidate) | 1581 | 238022 | سعيد بن بشير الأزدي (r3306) | سعيد بن أبي عروبة العدوي (r3281) | قتادة بن دعامة السدوسي: compatible (tabaka 4 → 8, gap +4) | compatible (years: d. 168 − b. 132 = 36) | **not caught** | not caught |
| la-yuminu-ahadukum (candidate) | 1581 | 280018 | سعيد بن بشير الأزدي (r3306) | سعيد بن أبي عروبة العدوي (r3281) | قتادة بن دعامة السدوسي: compatible (tabaka 4 → 8, gap +4) | compatible (years: d. 168 − b. 132 = 36) | **not caught** | not caught |
| innama-number-class | 319 | 320050 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-number-class | 319 | 320051 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-number-class | 319 | 320052 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-number-class | 319 | 320053 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-number-class | 319 | 320054 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-number-class | 319 | 320055 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320050 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320051 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320052 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320053 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320054 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |
| innama-qarain | 319 | 320055 | يحيى بن سعيد القطان (r8271) | يحيى بن سعيد الأنصاري (r8272) | محمد بن إبراهيم القرشي: incompatible (years: d. 119 − b. 120 = -1) | compatible (years: d. 198 − b. 110 = 88) | **caught** | caught |

**22 of 24** chains caught. The al-Qattan chains are caught by years: the data gives al-Taymi d. 119 (Taqrib: 120) and al-Qattan b. 120, so the student was born after the teacher died; PR 1's rule (death ≥ birth) already flagged them because of the 119, and the corrected rule (death − birth ≥ 5) would also catch the Taqrib date. Every documented case was already flagged under PR 1's rule (last column); what changes is that the flags now lower `kappa_lower` through the `nocompat` graph (§8.7). The candidate (Sa'id b. Bashir for Ibn Abi 'Aruba) sits in a plausible generation and is not caught. Cross-name misresolution the rule does not catch remains an unquantified upward bias on κ.

### 8.5 Continuity: layer gaps and the years rule

Chain links (adjacent narrators in `sanad_rawis`, placeholders excluded) by tabaka gap, student minus teacher. This is the tabaka rule's input; years decide first where both are known.

| student_minus_teacher | links | distinct_pairs | share | itibar_window | brief_window |
|---|---|---|---|---|---|
| ≤ −2 | 9,344 | 2,890 | 0.002 | out | out |
| −1 | 27,261 | 5,209 | 0.007 | in | out |
| 0 | 181,588 | 20,737 | 0.049 | in | in |
| 1 | 685,435 | 52,609 | 0.183 | in | in |
| 2 | 1,438,125 | 91,944 | 0.384 | in | in |
| 3 | 1,028,658 | 53,165 | 0.275 | in | out |
| 4 | 244,461 | 17,816 | 0.065 | in | out |
| 5 | 32,622 | 6,632 | 0.009 | out | out |
| 6+ | 8,720 | 4,061 | 0.002 | out | out |
| missing | 86,393 | 31,369 | 0.023 |  |  |

| link | teacher tabaka | student tabaka | gap |
|---|---|---|---|
| Anas → al-Zuhri | 1 | 4 | 3 |
| 'Alqama → al-Taymi | 2 | 5 | 3 |
| al-Zuhri → Malik | 4 | 7 | 3 |
| Qatada → Shu'ba | 4 | 7 | 3 |
| al-Zuhri → Ibn 'Uyayna | 4 | 8 | 4 |
| 'Umar → al-Taymi (dropped link) | 1 | 5 | 4 |

The brief's window [0, 1, 2] puts 36% of all links outside it, including every canonical gap-3 and gap-4 link above. itibar's window [-1, 0, 1, 2, 3, 4] (`config/structure.yaml`) keeps them and accepts −1 (a senior narrating from a junior, *riwayat al-akabir 'an al-asaghir*); 1.4% of links fall outside it (a gap of 5+ layers, ~125 years, or a student two or more layers before the teacher).

**Years rule.** 1,628,486 of 3,742,607 links (43.5%) have both the teacher's death year and the student's birth year; for them the years decide. Compatible iff death(teacher) − birth(student) ≥ 5 (`continuity.min_hearing_age`): 24,621 links (1.51%) fall below it, of which 8,246 are 0–4 (passed by PR 1's death ≥ birth rule) and the rest negative.

| death_minus_birth | links | distinct_pairs | share | verdict |
|---|---|---|---|---|
| < −20 | 7,324 | 3,138 | 0.004 | incompatible |
| -20 to -16 | 1,518 | 540 | 0.001 | incompatible |
| -15 to -11 | 1,851 | 603 | 0.001 | incompatible |
| -10 to -6 | 1,726 | 631 | 0.001 | incompatible |
| -5 to -1 | 3,956 | 740 | 0.002 | incompatible |
| 0 to 4 | 8,246 | 1,118 | 0.005 | incompatible |
| 5 to 9 | 46,157 | 2,301 | 0.028 | compatible |
| 10 to 14 | 99,124 | 3,191 | 0.061 | compatible |
| 15 to 19 | 110,491 | 4,278 | 0.068 | compatible |
| 20 to 24 | 223,708 | 6,172 | 0.137 | compatible |
| 25 to 29 | 271,136 | 6,682 | 0.166 | compatible |
| 30 to 34 | 205,537 | 6,260 | 0.126 | compatible |
| 35 to 39 | 202,565 | 5,363 | 0.124 | compatible |
| 40 to 44 | 168,695 | 4,441 | 0.104 | compatible |
| 45 to 49 | 104,014 | 3,515 | 0.064 | compatible |
| 50 to 54 | 73,816 | 2,623 | 0.045 | compatible |
| 55 to 59 | 36,518 | 2,081 | 0.022 | compatible |
| 60 to 64 | 20,988 | 1,570 | 0.013 | compatible |
| 65 to 69 | 15,713 | 1,212 | 0.010 | compatible |
| 70 to 74 | 10,964 | 986 | 0.007 | compatible |
| 75 to 79 | 4,243 | 795 | 0.003 | compatible |
| 80 to 84 | 2,824 | 643 | 0.002 | compatible |
| 85 to 89 | 2,180 | 580 | 0.001 | compatible |
| 90 to 94 | 1,335 | 469 | 0.001 | compatible |
| 95 to 99 | 1,041 | 301 | 0.001 | compatible |
| ≥ 100 | 2,816 | 1,004 | 0.002 | compatible |

Verdicts over all chain links, by basis (`continuity_basis`), under the corrected rule and under PR 1's (window [0..4], death ≥ birth):

| verdict | basis | links (corrected) | share | links (PR 1) | share |
|---|---|---|---|---|---|
| compatible | tabaka | 1,993,733 | 53.27% | 1,971,427 | 52.68% |
| compatible | years | 1,603,865 | 42.85% | 1,612,111 | 43.07% |
| incompatible | tabaka | 34,016 | 0.91% | 56,322 | 1.50% |
| incompatible | years | 24,621 | 0.66% | 16,375 | 0.44% |
| unknown | unknown | 86,372 | 2.31% | 86,372 | 2.31% |

The continuity flags feed one quantity: the `nocompat` hypothesis of `kappa_lower` (§8.7), which removes every incompatible link. They are never used in κ itself or in the derived grade.

### 8.6 `max_rank` includes the compiler

| chains | agree_full | agree_derived | compiler_strictly_weakest | book_role_strictly_weakest | other_classes |
|---|---|---|---|---|---|
| 577,020 | 577,020 | 569,379 | 7,641 | 0 | 0 |

`agree_full`: our weakest link over the whole stored chain equals `max_rank` (the like-for-like check of our reading). `agree_derived`: the same with the positions in a book role excluded, as the derived grade does (the compiler at pos 0; or a book transmitter at pos 0 and the compiler after him, §11.6); every disagreement is a chain whose excluded book-role narrator is strictly weaker than everyone else in it.

### 8.7 κ_lower under three hypotheses

`kappa_lower_θ` = min of κ_θ over three graphs, stubs dropped in all: **unmerged** (identities as resolved), **merged** (each same-name cluster one node of min ordinal, unnamed persons merged per student) and **nocompat** (unmerged, every continuity-incompatible link removed). `kappa_lower_source_θ` names the first hypothesis attaining the minimum in that order; since removing links never raises κ, `nocompat` there means removing incompatible links lowered κ below both other graphs.

| threshold | groups | lower_below_kappa | nocompat_below_kappa | nocompat_years_below_kappa | attained_unmerged | attained_merged | attained_nocompat | kappa_2plus_lower_below_2 | kappa_1plus_lower_0 |
|---|---|---|---|---|---|---|---|---|---|
| all | 20,282 | 2,436 | 2,436 | 732 | 17,849 | 1 | 2,432 | 404 | 1,020 |
| above_matruk | 20,282 | 1,765 | 1,764 | 538 | 18,517 | 2 | 1,763 | 303 | 746 |
| saduq_up | 20,282 | 835 | 827 | 327 | 19,447 | 11 | 824 | 131 | 363 |
| thiqa_up | 20,282 | 569 | 569 | 254 | 19,713 | 1 | 568 | 95 | 245 |

It is a lower bound under those hypotheses, not a guarantee: cross-name misresolution that the continuity rule does not catch (§8.4) remains an unquantified upward bias on κ.

`kappa_nocompat_years_θ` removes only the links the years rule marks incompatible (both dates known: the strong evidence); κ_lower keeps the all-incompatible graph. Both are reported for the paper.

### 8.8 Summary of modelling consequences

- break markers: per-chain, untraversable gap nodes (no fused hubs; broken chains do not count as routes)
- unnamed person: per-(student, teacher) node, ordinal 0
- compiler node in front of every book; book nodes never cut
- self-loops dropped; cycles handled; path counts flagged on cyclic bundles
- companion = rank_no 1 minus explicit denials, plus the young-companion labels at any rank_no; mursal chains kept, not connected to PROPHET
- continuity: years first (death − birth ≥ 5), then the tabaka window [-1, 0, 1, 2, 3, 4] calibrated to the source scale
- `kappa_lower`: min of κ over three stated hypotheses — same-name clusters merged, unmerged, continuity-incompatible links removed (stubs dropped in all); a lower bound under those hypotheses, not a guarantee

## 9. Why κ is zero

κ = 0 means **no unbroken companion-ending route in this data**, not no support. 3,421 of 20,745 groups have no PROPHET → book route at *everyone*: 2,958 of the 20,282 groups with chains (14.6%) plus the groups without chains. `kappa_zero_reason` assigns each one reason, by precedence:

| reason | groups | share_of_all_groups | share_of_zero_groups | meaning |
|---|---|---|---|---|
| no_chains | 463 | 0.022 | 0.135 | the group has no chains |
| no_companion_end | 2,531 | 0.122 | 0.740 | no chain ends in a companion (irsal marker, unnamed person, non-companion or stub) |
| broken_only | 427 | 0.021 | 0.125 | companion-ending chains exist, every one with a break marker |
| other | 0 | 0 | 0 | a continuous chain exists yet no route survived (gated at 0) |

**`no_companion_end`: the ten books contributing the most such groups** (a group counts for every book with a chain in it):

| book_id | book | author | groups | groups_with_chains | share_of_book |
|---|---|---|---|---|---|
| 274 | الطبقات الكبرى لابن سعد | محمد بن سعد الزهري | 319 | 2,096 | 0.152 |
| 303 | تاريخ دمشق لابن عساكر | ابن عساكر الدمشقي | 314 | 5,605 | 0.056 |
| 62 | مصنف ابن أبي شيبة | ابن ابي شيبة | 239 | 3,431 | 0.070 |
| 61 | مصنف عبد الرزاق | عبد الرزاق الصنعاني | 174 | 1,900 | 0.092 |
| 22 | السنن الكبرى للبيهقي | البيهقي | 150 | 4,551 | 0.033 |
| 297 | معرفة الصحابة لأبي نعيم | أبو نعيم الأصبهاني | 148 | 3,092 | 0.048 |
| 143 | المراسيل مع الأسانيد لأبي داود | أبو داود السجستاني | 129 | 417 | 0.309 |
| 249 | جامع البيان عن تأويل آي القرآن | ابن جرير الطبري | 129 | 1,292 | 0.100 |
| 269 | دلائل النبوة للبيهقي | البيهقي | 117 | 1,399 | 0.084 |
| 278 | تاريخ المدينة لابن شبة | ابن شبة النميري | 87 | 455 | 0.191 |

**`broken_only`: the ten books contributing the most such groups** (a group counts for every book with a chain in it):

| book_id | book | author | groups | groups_with_chains | share_of_book |
|---|---|---|---|---|---|
| 305 | التدوين في أخبار قزوين للرافعي | عبد الكريم الرافعي | 52 | 1,188 | 0.044 |
| 303 | تاريخ دمشق لابن عساكر | ابن عساكر الدمشقي | 46 | 5,605 | 0.008 |
| 255 | الوسيط في تفسير القرآن المجيد | الواحدي | 33 | 793 | 0.042 |
| 297 | معرفة الصحابة لأبي نعيم | أبو نعيم الأصبهاني | 23 | 3,092 | 0.007 |
| 45 | مسند الشاميين للطبراني | سليمان بن أحمد الطبراني | 19 | 1,846 | 0.010 |
| 274 | الطبقات الكبرى لابن سعد | محمد بن سعد الزهري | 16 | 2,096 | 0.008 |
| 9 | مسند أحمد بن حنبل | أحمد بن حنبل | 15 | 5,666 | 0.003 |
| 40 | المطالب العالية بزوائد المسانيد الثمانية لابن حجر | ابن حجر العسقلاني | 14 | 2,500 | 0.006 |
| 67 | المعجم الكبير للطبراني | سليمان بن أحمد الطبراني | 13 | 5,496 | 0.002 |
| 22 | السنن الكبرى للبيهقي | البيهقي | 11 | 4,551 | 0.002 |

**The converse does not hold.** 13 groups have κ ≥ 1 with no continuous chain: every chain is broken, but at different places, and the union graph joins the intact parts into a route. In group 7978 one copy of the isnad has an inqita' marker in the middle and another a ta'liq at the compiler's end; together they cover the whole chain. Routes are paths in the bundle, not attested chains (DECISIONS D31); `n_chains_connected` and `bypass_chains` count attested chains.

| group_id | kappa_all | n_chains | n_chains_companion_end | n_chains_broken | opening |
|---|---|---|---|---|---|
| 7,978 | 1 | 2 | 2 | 2 | يطير الحمام |
| 9,030 | 1 | 6 | 1 | 5 | ليأخذ العبد من نفسه لنفسه ومن دنياه لآخر |
| 9,730 | 1 | 5 | 1 | 5 | ضرب رسول الله لجعفر يوم بدر بسهمه وأجره |
| 11,928 | 1 | 2 | 2 | 2 | نصلي مع رسول الله المغرب ونحن ننظر إلى ا |
| 11,996 | 1 | 6 | 1 | 6 | آخى رسول الله بين عويم بن ساعدة وبين عمر |
| 12,053 | 1 | 3 | 1 | 1 | نهى عن الشعر إذا أبنت فيه النساء وبذر في |
| 12,120 | 1 | 4 | 3 | 4 | الله يقبض أرواح شهداء البحر بيده ولا يكل |
| 12,518 | 1 | 3 | 2 | 3 | تريدون من ربكم إلا أن يغفر لكم ذنوبكم وي |
| 13,542 | 1 | 5 | 1 | 1 | أهل حين راح إلى منى |
| 14,391 | 1 | 3 | 2 | 3 | عليكم بأمهات الأولاد فإنهن مباركات الأرح |
| 14,804 | 1 | 2 | 1 | 2 | لا تزال مصليا قانتا ما ذكرت الله قائما و |
| 15,955 | 1 | 2 | 1 | 2 | غارت خيل للمشركين على سرح المدينة فخرج ر |
| 16,716 | 1 | 2 | 1 | 2 | أمر معاذا أن يصلي بهم |

**Against the source's recorded group grade** (`meaning_groups.matn_no`, labels quoted from the source). A group the source grades صحيح with no connected chain here is a gap in this data's chains, not a finding about the report:

| reason | 0 صحيح | 1 حسن | 2 ضعيف | 3 شديد الضعف | 4 متهم بالوضع | 5 موضوع |
|---|---|---|---|---|---|---|
| no_chains | 21 | 40 | 180 | 86 | 84 | 52 |
| no_companion_end | 83 | 110 | 1,511 | 426 | 322 | 79 |
| broken_only | 2 | 6 | 245 | 93 | 49 | 32 |
| κ ≥ 1 | 5,957 | 4,519 | 2,217 | 2,025 | 1,567 | 1,039 |
## 10. Indicative chain-level error rate from the gold set

Every gold entry whose chains were inspected one by one (`deviation_key` and `known_deviations` in `tests/gold/gold.yaml`): chains documented as a cross-name misresolution (`misresolution`) or a dropped link, over the chains in the entry's scope. Other documented deviations (alternative routes the classical sources do not count) are listed but are not errors of the data. The four entries are hand-picked famous reports, so this is an indicative rate for the limitations section, not an estimate for the corpus.

| entry | group | in_scope_chains | misresolution | dropped_link | error_chains | other_documented_routes | error_rate |
|---|---|---|---|---|---|---|---|
| innama-al-amal | 319 | 335 | 6 | 2 | 8 | 6 | 0.024 |
| bay-al-wala | 276 | 318 | 2 | 1 | 3 | 40 | 0.009 |
| al-din-al-nasiha | 397 | 157 | 0 | 1 | 1 | 0 | 0.006 |
| kalimatan-khafifatan | 2,852 | 33 | 2 | 0 | 2 | 2 | 0.061 |

Pooled: **14 of 843 in-scope chains (1.66%)** carry a documented misresolution or dropped link; misresolution alone 10 (1.19%).

## 11. Derived grade v2: corroboration, after the PR 5 corrections

Books used by the qarāʾin, the collection classes and the Ṣaḥīḥayn convention, verified: `books.id` 1 = صحيح البخاري; `books.id` 2 = صحيح مسلم.

Agreement with the source's recorded grades is a **reported result, never a gate** (PR 5 removed the v2 ≥ v1 gate: a gate that rewards agreement invites tuning, DECISIONS D37, D63). Nothing below was tuned to it.

### 11.1 The corrections, applied cumulatively

Each row reruns the pipeline (`make stages`, `config/stages/`) with the corrections up to that row switched on, in the brief's order; stage 0 reproduces PR 4 and the last row equals the defaults. *ours 1 / source 3–5*: groups v2 (`ibn_hajar`) places at code 1 that the source records شديد الضعف, متهم بالوضع or موضوع.

| stage | correction | v1 | v2 ibn_hajar | v2 ibn_al_salah | ours 1 / source 3–5 | upgraded groups | groups changed vs previous |
|---|---|---|---|---|---|---|---|
| s0_pr4 | PR 4 as merged (derive v2, structure v3) | 0.7235 | 0.7286 | 0.7237 | 562 | 3,730 |  |
| s1_attested | + §1 a witness is one attested chain | 0.7235 | 0.7341 | 0.7332 | 457 | 3,310 | 526 |
| s2_tadlis | + §2 tiered tadlīs, hearing check (group), Ṣaḥīḥayn convention | 0.7235 | 0.7415 | 0.7391 | 437 | 2,943 | 403 |
| s3_siblings | + §3 shawāhid from sibling groups | 0.7235 | 0.7321 | 0.7261 | 536 | 3,461 | 523 |
| s4_each_defect | + §4 every light defect covered | 0.7235 | 0.7109 | 0.7201 | 486 | 2,855 | 608 |
| s5_book_roles | + §5 compiler roles per edge, book transmitters | 0.7235 | 0.7109 | 0.7201 | 486 | 2,855 | 0 |
| s6_kappa_class | + §6 number class on κ (no effect on grades) | 0.7235 | 0.7109 | 0.7201 | 486 | 2,855 | 0 |
| s7_named_elsewhere | + §8 unnamed person named elsewhere (= PR 5 defaults) | 0.7235 | 0.7121 | 0.7211 | 488 | 2,877 | 34 |

### 11.2 §1 A witness is one attested chain

PR 4 accepted a route spliced from several chains in the union graph: 725 of its 3,730 upgraded groups (19.4%) rested on one. With witnesses restricted to single attested chains, upgraded groups go from 3,730 to 3,310 and the block *ours 1 / source 3–5* from 562 to 457.

`witness_route_exists` (the union graph had a route avoiding the positions, no single chain did), final run: 125 of 5,441 groups whose v2 chain is ḍaʿīf; 1,519 of 24,508 such chains.

### 11.3 §2 Tiered tadlīs, the hearing check, the Ṣaḥīḥayn convention

Ibn Hajar's *Ṭabaqāt al-Mudallisīn* (Shamela 1186, ed. al-Qaryūtī): 152 entries parsed (tiers 1: 33, 2: 33, 3: 50, 4: 12, 5: 24; the book states 152, tier heads 33, 33, 50, 12, 24). Joined to `rawis` by deterministic name matching (README): 92 entries auto-confirmed, 0 by the reviewer, 60 awaiting review in `lists/mudallisin_confirmed.csv`.
Of the 83 narrators the source flags (`has_tadlis = 1`), 58 are matched to the book (tier 1: 4, 2: 8, 3: 25, 4: 10, 5: 11) and 25 are not (unmatched or pending review; they take `untiered_tadlis`, tier 3). 34 narrators matched to the book are not flagged by the source (`mudallis_set: source_flag` leaves them without a tadlīs defect; variant `mudallis_union` adds them).

Flagged narrators without a confirmed tier: الحسن البصري (r1239), الحكم بن عتيبة الكندي (r1372), المطلب بن عبد الله المخزومي (r1643), شعيب بن رزيق المقدسي (r3809), صدقة بن يسار الجزري (r3928), عبد الرحمن بن يزيد السلمي (r4514), عقبة بن عبد الله الأصم (r5676), علي بن عبد العزيز الفزاري (r5806), عيسى بن طهمان الجشمي (r6314), محمد بن ثور الصنعاني (r6896), محمد بن عيسى النقاش (r7230), محمد بن عيسى البغدادي (r7232), مطرف بن مازن الكناني (r7533), واصل بن عبد الرحمن الرقاشي (r8120), إبراهيم بن زكريا العبدستاني (r11465), جعفر بن محمد المستغفري (r13823), الحكم بن عتيبة العجلي (r15578), عبد الله بن محمد الحارثي (r23172), عبد الله بن مراون الحراني (r23191), عطية بن بقية الحمصي (r23567), محمد بن عبد الملك الواسطي (r29842), محمد بن عمر الأندلسي (r30256), محمد بن محمد البخاري (r30543), محمد بن يوسف المهلبي (r31096), عثمان بن محمد المخرمي (r54113).


PR 4 downgraded 271 groups from v1 code 0 only because of a mudallis's ʿan (its binary flag). With tiers, the hearing check and the Ṣaḥīḥayn convention (stage 2), their v2 chains stand as follows (*accepted* = tier 1–2; *accepted_sahihayn* = a chain of al-Bukhārī or Muslim; *covered_tasrih* = the link heard in another chain of the report):

| after §2 | groups |
|---|---|
| code 0: accepted | 122 |
| hasan_li_ghayrihi (code 1.0) | 74 |
| daif (code 2.0) | 57 |
| code 0: accepted_sahihayn | 9 |
| code 0: covered_tasrih | 6 |
| not_repairable (code 2.0) | 3 |

Chain-level counts in the final run (`ibn_hajar`; a chain counts once per kind): `muanan_accepted_sahihayn_tier_3` 1,552; `muanan_accepted_sahihayn_tier_4` 34; `muanan_accepted_tier_1` 10,733; `muanan_accepted_tier_2` 32,112; `muanan_covered_tasrih_tier_3` 28,113; `muanan_covered_tasrih_tier_4` 4,832; `muanan_covered_tasrih_tier_5` 386; still defects: `mudallis_muanan_tier_3` 34,018; `mudallis_muanan_tier_4` 6,712; `mudallis_muanan_tier_5` 2,643.

- variant hearing anywhere in the corpus (`tasrih_corpus`): agreement 0.7237
- variant every narrator matched to the book a mudallis (`mudallis_union`): agreement 0.7096

### 11.4 §3 Shawāhid from sibling groups

Floor: idf-weighted Dice ≥ 0.32 on lists.normalize tokens, set by reading 50 candidate pairs (reports/shahid_inspection.md, D58). In the final run 659 of 2,877 upgraded groups have a cross-group witness in their v2 chain; 1,844 chains in all. Of those chains' witnesses, 17.6% come through the same companion as the chain (a mutābaʿa by the *Nuzha*'s definition; classed shāhid because the source files them as another report).

| reading | agreement |
|---|---|
| with sibling shawāhid (default) | 0.7121 |
| in-group witnesses only (`shahid_group`) | 0.7180 |
| siblings, strict floor 0.38 (`shahid_strict`) | 0.7153 |

The sandals dowry (gold `sandals-asim-b-ubaydallah`, group 2031) is repaired by Sahl b. Saʿd's report in group 763 at overlap 0.333: above the floor, below the strict variant's.

### 11.5 §4 Every light defect covered

| positions to cover | agreement |
|---|---|
| each light defect, a witness of its own (`each_defect`, default) | 0.7121 |
| the weakest light defects, one witness (`weakest`, PR 4) | 0.7334 |
| every light defect, one witness (`all_light_defects`) | 0.7121 |

Groups whose v2 chain needed more than one witness (one per defect): 941 of 2,492 ḥasan li-ghayrihi groups (ḥasan li-ghayrihi chains in all: 211,522).

### 11.6 §5 Book transmitters and compiler roles

Book transmitters (`bundle.book_transmitter_min_share` = 0.2): a narrator at pos 0 while the book's author (death year = `books.author_death_year` ± 1) sits at pos 1 in at least that share of the book's chains. The next largest share in the corpus is under 0.02. The brief's examples are not of this shape in this data: ʿAbd al-Razzāq himself is at pos 0 of 94.5% of the *Muṣannaf*'s chains (al-Dabarī is not in them), and Aḥmad of 99.4% of the *Musnad*'s (ʿAbdallāh b. Aḥmad's chains with Aḥmad at pos 1 are in ʿAbdallāh's own books, *al-Sunna* and *Faḍāʾil ʿUthmān*, where he is the author).

| book | chains | transmitter at pos 0 | share (transmitter at 0, author at 1) | compiler, PR 4 rule | compiler now | PR 4 misidentified him |
|---|---|---|---|---|---|---|
| مسند ابن الجعد (32) | 1,559 | عبد الله بن سابور البغوي (r23051) | 0.459 | عبد الله بن سابور البغوي (r23051) | علي بن الجعد الجوهري (r5730) | yes |
| الورع لأحمد  رواية المروزي (412) | 108 | محمد بن يحيى الوراق (r30978) | 0.333 | أحمد بن حنبل الشيباني (r488) | أحمد بن حنبل الشيباني (r488) | no |

Compiler roles are per edge for single strands, partial common links and common links (D61); the census and the ranks of al-Zuhrī, Qatāda, al-Aʿmash, Shuʿba and Mālik are in reports/common_links.md.

### 11.7 §7 Whose verdicts are the labels: a sample against the Taqrīb and Taḥrīr al-Taqrīb

40 narrators of al-Bukhārī or Muslim (all of whom the Taqrīb covers), 20 labelled «صدوق حسن الحديث» and 20 with other labels of levels 2–9 (seed in `itibar.provenance`), looked up in Shamela's *Taqrīb al-Tahdhīb* (book 8609) and *Taḥrīr Taqrīb al-Tahdhīb* (book 127715), which reprints each entry and adds its own verdict after «بل:» where it disagrees; raw lines in `lists/source/taqrib_sample.jsonl`. *reading*: the label is Taḥrīr's revision; or, where Taḥrīr keeps Ibn Hajar's verdict, his wording, or the formula «صدوق حسن الحديث» put over it; or neither. A label *is* a wording when one contains the other after normalization; an entry whose tabaqa is more than one layer from the narrator's tabaka, without agreeing on the grandfather, is a namesake. Every row is printed for checking.

| stratum | sampled | read whole in both | Taḥrīr revises Ibn Hajar | Taḥrīr's revision | Ibn Hajar's wording | formula over Ibn Hajar's verdict | neither |
|---|---|---|---|---|---|---|---|
| «صدوق حسن الحديث» | 20 | 15 | 6 | 6 | 0 | 9 | 0 |
| other labels | 20 | 14 | 1 | 1 | 12 | 0 | 1 |

| rawi | source label | Taqrīb (Ibn Hajar) | Taḥrīr «بل:» | entry | Taqrīb page | reading |
|---|---|---|---|---|---|---|
| r2504 | صدوق حسن الحديث |  |  |  |  | not found by name search |
| r808 | صدوق حسن الحديث | إبراهيم ابن المنذر ابن عبد الله ابن المنذر ابن المغيرة ابن عبد الله ابن خالد ابن حزام الأسدي الحزامي بالزاي صدوق تكلم فيه أحمد لأجل القرآن |  | ٢٥٣ | https://shamela.ws/book/8609/20 | formula over Ibn Hajar's verdict |
| r6616 | صدوق حسن الحديث | كليب ابن وائل التيمي البكري المدني نزيل الكوفة صدوق |  | ٥٦٦٣ | https://shamela.ws/book/8609/388 | formula over Ibn Hajar's verdict |
| r3607 | صدوق حسن الحديث | سليمان ابن عبد الرحمن ابن عيسى التميمي الدمشقي ابن بنت شرحبيل أبو أيوب صدوق يخطىء |  | ٢٥٨٨ | https://shamela.ws/book/8609/179 | not read: Taḥrīr's entry continues on the next page |
| r8526 | صدوق حسن الحديث | يعقوب ابن عاصم ابن عروة ابن مسعود الثقفي أخو نافع مقبول | صدوقٌ حسن الحديث | ٧٨٢٠ | https://shamela.ws/book/8609/534 | Taḥrīr's revision |
| r1954 | صدوق حسن الحديث | بكير ابن مسمار الزهري المدني أبو محمد أخو مهاجر صدوق |  | ٧٦٦ | https://shamela.ws/book/8609/54 | formula over Ibn Hajar's verdict |
| r5548 | صدوق حسن الحديث | عثمان ابن غياث بمعجمة ومثلثة الراسبي أو الزهراني البصري ثقة ورمي بالإرجاء |  | ٤٥٠٨ | https://shamela.ws/book/8609/312 | formula over Ibn Hajar's verdict |
| r4585 | صدوق حسن الحديث | عبد العزيز ابن عثمان ابن جبلة بفتح الجيم والموحدة ابن أبي رواد الأزدي مولاهم أبو الفضل المروزي لقبه شاذان وهو أخو عبدان مقبول | صدوقٌ حسن الحديث | ٤١١٢ | https://shamela.ws/book/8609/284 | Taḥrīr's revision |
| r2477 | صدوق حسن الحديث | حكيم ابن معاوية ابن حيدة القشيري والد بهز صدوق |  | ١٤٧٨ | https://shamela.ws/book/8609/103 | formula over Ibn Hajar's verdict |
| r206 | صدوق حسن الحديث |  |  |  |  | not found by name search |
| r6146 | صدوق حسن الحديث | عمرو ابن عاصم ابن عبيد الله الكلابي القيسي أبو عثمان البصري صدوق في حفظه شيء | صدوقٌ حسن الحديث | ٥٠٥٥ | https://shamela.ws/book/8609/349 | Taḥrīr's revision |
| r1301 | صدوق حسن الحديث | الحسن ابن مدرك ابن بشير السدوسي أبو علي البصري الطحان لا بأس به ونسبه أبو داود إلى تلقين المشايخ |  | ١٢٨٥ | https://shamela.ws/book/8609/90 | formula over Ibn Hajar's verdict |
| r2654 | صدوق حسن الحديث | خالد ابن سعيد ابن عمرو ابن سعيد ابن العاص أخو إسحاق ابن سعيد صدوق |  | ١٦٣٩ | https://shamela.ws/book/8609/114 | formula over Ibn Hajar's verdict |
| r6726 | صدوق حسن الحديث |  |  |  |  | not found by name search |
| r2683 | صدوق حسن الحديث | خالد ابن ميسرة الطفاوي أبو حاتم البصري العطار صالح الحديث | صدوق حسن الحديث | ١٦٨١ | https://shamela.ws/book/8609/117 | Taḥrīr's revision |
| r2338 | صدوق حسن الحديث | حرب ابن ميمون الأكبر أبو الخطاب الأنصاري مولاهم البصري صدوق رمي بالقدر |  | ١١٦٨ | https://shamela.ws/book/8609/81 | formula over Ibn Hajar's verdict |
| r3840 | صدوق حسن الحديث | شيبان ابن فروخ أبي شيبة الحبطي بمهملة وموحدة مفتوحتين الأبلي بضم الهمزة والموحدة وتشديد اللام أبو محمد صدوق يهم ورمي بالقدر قال أبو حاتم اضطر الناس إليه أخيرا | صدوق حسن الحديث | ٢٨٣٤ | https://shamela.ws/book/8609/195 | Taḥrīr's revision |
| r3670 | صدوق حسن الحديث | سهل ابن حماد أبو عتاب بمهملة ومثناة ثم موحدة الدلال البصري صدوق |  | ٢٦٥٤ | https://shamela.ws/book/8609/183 | formula over Ibn Hajar's verdict |
| r4564 | صدوق حسن الحديث | عبد العزيز ابن المطلب ابن عبد الله ابن حنطب المخزومي أبو طالب المدني صدوق |  | ٤١٢٤ | https://shamela.ws/book/8609/285 | not read: Taḥrīr's entry continues on the next page |
| r5545 | صدوق حسن الحديث | عثمان ابن عمر ابن موسى ابن عبيد الله ابن معمر التيمي المدني قاضيها مقبول | صدوقٌ حسن الحديث | ٤٥٠٥ | https://shamela.ws/book/8609/312 | Taḥrīr's revision |
| r4298 | مختلف في صحبته | عبد الرحمن ابن الأسود ابن عبد يغوث ابن وهب ابن عبد مناف ابن زهرة الزهري ولد على عهد النبي صَلَّى اللهُ عَلَيْهِ وَسَلَّمَ ومات أبوه في ذلك الزمان فعد لذلك في الصحابة وقال العجلي من كبار التابعين خ د ق |  | ٣٨٠١ | https://shamela.ws/book/8609/262 | neither |
| r2485 | ثقة | حماد ابن إسماعيل ابن علية البصري نزيل بغداد ثقة |  | ١٤٨٨ | https://shamela.ws/book/8609/103 | Ibn Hajar's wording |
| r5688 | ثقة ثبت |  |  |  |  | not found by name search |
| r6013 | ثقة | عمر ابن نافع العدوي مولى ابن عمر ثقة |  | ٤٩٧٣ | https://shamela.ws/book/8609/343 | Ibn Hajar's wording |
| r4432 | مقبول |  |  | ٣٩٣٥ | https://shamela.ws/book/8609/271 | not read: the entry found is a namesake (tabaqa) |
| r8098 | ثقة | هناد ابن السري بكسر الراء الخفيفة ابن مصعب التميمي أبو السري الكوفى ثقة |  | ٧٣٢٠ | https://shamela.ws/book/8609/500 | Ibn Hajar's wording |
| r6810 | ثقة | محمد ابن إسحاق ابن منصور أبو عبد الله ابن أبي يعقوب الكرماني نزيل البصرة ثقة |  | ٥٧٢٤ | https://shamela.ws/book/8609/393 | Ibn Hajar's wording |
| r7352 | ثقة | محمود ابن غيلان العدوي مولاهم أبو أحمد المروزي نزيل بغداد ثقة |  | ٦٥١٦ | https://shamela.ws/book/8609/448 | Ibn Hajar's wording |
| r1086 | ثقة | عمر ابن سعيد ابن أبي حسين النوفلي المكي ثقة |  | ٤٩٠٥ | https://shamela.ws/book/8609/339 | Ibn Hajar's wording |
| r2146 | ثقة | جعفر ابن حيان السعدي أبو الأشهب العطاردي البصري مشهور بكنيته ثقة |  | ٩٣٥ | https://shamela.ws/book/8609/66 | not read: Taḥrīr's entry continues on the next page |
| r2122 | ثقة | جرير ابن عبد الحميد ابن قرط بضم القاف وسكون الراء بعدها طاء مهملة الضبي الكوفي نزيل الري وقاضيها ثقة صحيح الكتاب قيل كان في آخر عمره يهم من حفظه مات سنة ثمان وثمانين وله إحدى وسبعون سنة ع |  | ٩١٦ | https://shamela.ws/book/8609/65 | Ibn Hajar's wording |
| r6782 | ثقة | محمد ابن أحمد ابن محمد ابن الحجاج ابن ميسرة الكريزي بتقديم الراء مصغر أبو يوسف الصيدلاني الرقي ثقة حافظ |  | ٥٧١٣ | https://shamela.ws/book/8609/393 | Ibn Hajar's wording |
| r2949 | ثقة |  |  |  |  | not found by name search |
| r1877 | ثقة | بشر ابن شعيب ابن أبي حمزة [بن] دينار القرشي مولاهم أبو القاسم الحمصي ثقة |  | ٦٨٨ | https://shamela.ws/book/8609/49 | Ibn Hajar's wording |
| r5593 | ثقة | عروة ابن الحارث الهمداني الكوفي أبو فروة الأكبر ثقة |  | ٤٥٥٩ | https://shamela.ws/book/8609/315 | Ibn Hajar's wording |
| r7988 | ثقة | هارون ابن معروف المروزي أبو علي الخزاز [بمعجمات] الضرير نزيل بغداد ثقة |  | ٧٢٤٢ | https://shamela.ws/book/8609/495 | Ibn Hajar's wording |
| r4716 | ثقة ثبت فقيه عالم جواد مجاهد جمعت فيه خصال الخير | عبد الله ابن المبارك المروزي مولى بني حنظلة ثقة ثبت فقيه عالم جواد مجاهد جمعت فيه خصال الخير |  | ٣٥٧٠ | https://shamela.ws/book/8609/246 | not read: found in the Taqrīb only |
| r1621 | ثقة | المثنى ابن سعيد الضبعي بضم المعجمة وفتح الموحدة أبو سعيد البصري القسام القصير ثقة قال أبو حاتم هو أوثق من الذي قبله |  | ٦٤٧٠ | https://shamela.ws/book/8609/445 | Ibn Hajar's wording |
| r3343 | ثقة | سعيد ابن سنان البرجمي بضم الموحدة والجيم بينهما راء ساكنة أبو سنان الشيباني الأصغر الكوفي نزيل الري صدوق له أوهام | ثقةٌ | ٢٣٣٢ | https://shamela.ws/book/8609/163 | Taḥrīr's revision |
| r3483 | ثقة |  |  |  |  | not found by name search |

### 11.8 §8 The unnamed person

In PR 4, 569 disagreeing groups had the unnamed person (`اسم مبهم`) among the weakest positions of their v2 chain: 188 only in the companion slot (read as mursal, D36), 381 below it, of which 21 have another chain of the report naming a narrator between the same teacher and student.

| where | named_elsewhere | groups |
|---|---|---|
| mid | 0 | 360 |
| mid | 1 | 21 |
| top | 0 | 188 |

By the source's recorded grade:

| position | source 0 | source 1 | source 2 | source 3 | source 4 | source 5 |
|---|---|---|---|---|---|---|
| mid | 73 | 92 | 0 | 108 | 70 | 38 |
| top | 53 | 63 | 5 | 37 | 21 | 9 |

Effect: agreement 0.7121 with `unknown_repair: named_elsewhere`, 0.7109 without (`unknown_none`). Chains whose unnamed person is named elsewhere: 2,717.

### 11.9 The final grade

**Agreement with `meaning_groups.matn_no`** over the 20,282 groups with chains (variants run on `ibn_hajar` with one switch changed, `derive.variants`):

| grade | agreement_with_matn_no |
|---|---|
| v1 (best single chain) | 0.7235 |
| v2 variant all_light_defects | 0.7121 |
| v2 variant mudallis_union | 0.7096 |
| v2 variant mursal_shafii | 0.7083 |
| v2 variant no_level_8 | 0.7099 |
| v2 variant shahid_group | 0.7180 |
| v2 variant shahid_strict | 0.7153 |
| v2 variant tasrih_corpus | 0.7237 |
| v2 variant unknown_none | 0.7109 |
| v2 variant weakest | 0.7334 |
| v2 variant witness_not_below | 0.7117 |
| v2 ibn_al_salah | 0.7211 |
| v2 ibn_hajar | 0.7121 |

**Disagreement table, `ibn_hajar`**: our v2 code (rows) by the source's code (columns):

| v2 code | 0 صحيح | 1 حسن | 2 ضعيف | 3 شديد الضعف | 4 متهم بالوضع | 5 موضوع |
|---|---|---|---|---|---|---|
| ours 0 | 5,427 | 427 | 0 | 0 | 0 | 0 |
| ours 1 | 345 | 2,629 | 421 | 167 | 191 | 130 |
| ours 2 | 268 | 1,561 | 3,487 | 879 | 637 | 381 |
| ours 3 | 1 | 11 | 42 | 1,496 | 180 | 99 |
| ours 4 | 1 | 5 | 19 | 0 | 930 | 67 |
| ours 5 | 0 | 2 | 4 | 2 | 0 | 473 |

**Disagreement table, `ibn_al_salah`**: our v2 code (rows) by the source's code (columns):

| v2 code | 0 صحيح | 1 حسن | 2 ضعيف | 3 شديد الضعف | 4 متهم بالوضع | 5 موضوع |
|---|---|---|---|---|---|---|
| ours 0 | 5,458 | 726 | 0 | 0 | 0 | 0 |
| ours 1 | 325 | 2,792 | 432 | 175 | 199 | 132 |
| ours 2 | 257 | 1,099 | 3,476 | 871 | 629 | 379 |
| ours 3 | 1 | 11 | 42 | 1,496 | 180 | 99 |
| ours 4 | 1 | 5 | 19 | 0 | 930 | 67 |
| ours 5 | 0 | 2 | 4 | 2 | 0 | 473 |

**For comparison, v1**:

| v1 code | 0 صحيح | 1 حسن | 2 ضعيف | 3 شديد الضعف | 4 متهم بالوضع | 5 موضوع |
|---|---|---|---|---|---|---|
| ours 0 | 5,601 | 110 | 0 | 1 | 1 | 0 |
| ours 1 | 117 | 1,904 | 1 | 0 | 0 | 0 |
| ours 2 | 287 | 2,573 | 3,906 | 859 | 669 | 425 |
| ours 3 | 24 | 31 | 43 | 1,682 | 208 | 125 |
| ours 4 | 11 | 9 | 19 | 0 | 1,060 | 79 |
| ours 5 | 2 | 8 | 4 | 2 | 0 | 521 |

**Rule that fired for the group's v2 chain (`ibn_hajar`)**:

| rule | groups | share |
|---|---|---|
| sahih_li_dhatihi | 5,469 | 0.270 |
| daif | 5,441 | 0.268 |
| fatal | 3,977 | 0.196 |
| hasan_li_ghayrihi | 2,492 | 0.123 |
| hasan_li_dhatihi | 1,391 | 0.069 |
| not_repairable | 1,127 | 0.056 |
| sahih_li_ghayrihi | 385 | 0.019 |

**Divergence class of the summary witness** (upgraded groups; the witness covering the topmost position, D41):

| divergence | groups |
|---|---|
| shahid | 1,937 |
| mutabaa_tamma | 561 |
| mutabaa_qasira | 287 |
| wasl | 92 |

**By the weakest narrator's Taqrīb level** in the group's v2 chain (`ibn_hajar`):

| weakest_level | groups | agree_v1 | agree_v2_ibn_hajar |
|---|---|---|---|
| 1 | 167 | 0.958 | 0.946 |
| 2 | 1,508 | 0.946 | 0.934 |
| 3 | 4,955 | 0.934 | 0.884 |
| 4 | 2,447 | 0.899 | 0.721 |
| 5 | 1,307 | 0.157 | 0.484 |
| 6 | 1,364 | 0.127 | 0.445 |
| 7 | 1,539 | 0.606 | 0.520 |
| 8 | 2,418 | 0.615 | 0.552 |
| 9 | 479 | 0.574 | 0.564 |
| 10 | 1,829 | 0.825 | 0.818 |
| 11 | 1,022 | 0.915 | 0.910 |
| 12 | 481 | 0.983 | 0.983 |
| unknown | 766 | 0.351 | 0.244 |

**Narrators most often weakest in the disagreeing groups** (`ibn_hajar`):

| narrator | groups_disagreeing |
|---|---|
| اسم مبهم (r1131) | 631 |
| ابن إسحاق القرشي (r6811) | 98 |
| عبد الله بن لهيعة الحضرمي (r5033) | 93 |
| الحسن البصري (r1239) | 67 |
| بقية بن الوليد الكلاعي (r1919) | 62 |
| أبو إسحاق السبيعي (r6155) | 50 |
| سماك بن حرب الذهلي (r3638) | 47 |
| الحجاج بن أرطاة النخعي (r2288) | 44 |
| مسلم بن أبي كريمة التميمي (r31544) | 40 |
| محمد بن مسلم القرشي (r7270) | 38 |
| الليث بن أبي سليم القرشي (r6638) | 37 |
| علي بن زيد القرشي (r5770) | 36 |
| إبراهيم بن أبي يحيى الأسلمي (r870) | 35 |
| إسماعيل بن عياش العنسي (r1050) | 34 |
| ابن جريج المكي (r5223) | 32 |

**Downgrades.** 231 groups that v1 grades 0 get a higher v2 code under `ibn_hajar` (223 of them recorded 0 by the source). The defects of their v2 chain: mudallis_muanan_tier_3 186; mursal 11; none 8; level_5 5; level_8 5; mudallis_muanan_tier_4 4; level_6 3; level_8,mursal 2; level_5,mudallis_muanan_tier_3 1; level_5,mursal 1; level_7 1; level_7,mursal 1.

## 12. Number class and qarāʾin

`number_class` on κ_all (structure version 4, D60): 1 gharīb, 2 ʿazīz, 3–9 mashhūr, ≥ 10 mutawātir by count; gharīb muṭlaq when a companion is among the cut vertices. `no route`: κ_all = 0.

| number_class | groups | share |
|---|---|---|
| gharib_mutlaq | 10,425 | 0.514 |
| gharib_nisbi | 750 | 0.037 |
| aziz | 2,679 | 0.132 |
| mashhur | 2,965 | 0.146 |
| mutawatir_count | 505 | 0.025 |
| no route | 2,958 | 0.146 |

**The topmost cut vertex of the gharīb groups**: companion 10,425; narrator 736; compiler 14 (*compiler*: every route ends in one compiler's books, so the tafarrud is his).

**The width reading (rows, diagnostic, `number_class_width`) against the κ reading (columns)**:

| width \ κ | aziz | gharib_mutlaq | gharib_nisbi | mashhur | mutawatir_count | no route |
|---|---|---|---|---|---|---|
| aziz | 177 | 15 | 5 | 651 | 45 | 0 |
| gharib_mutlaq | 0 | 9,433 | 1 | 0 | 0 | 0 |
| gharib_nisbi | 2,498 | 977 | 743 | 1,859 | 29 | 0 |
| mashhur | 4 | 0 | 1 | 453 | 340 | 0 |
| mutawatir_count | 0 | 0 | 0 | 2 | 91 | 0 |
| no route | 0 | 0 | 0 | 0 | 0 | 2,958 |

The readings differ in 31.5% of groups. The width reading treats each Taqrīb layer as a cut, but routes skip layers (tabaka steps of 2–4 are normal on this scale, §8.5), so a layer is a cut only when every route has a narrator in it: 4,386 groups read gharīb by width while κ_all ≥ 2. Tafarrud is one man through whom every route passes, which is a cut vertex; hence the κ reading is the class.


**Sensitivity to tawatur_n** (the numbers the books report as proposed):

| tawatur_n | mutawatir_count (κ_all) | mashhur (κ_all) | mutawatir_count (width) |
|---|---|---|---|
| 4 | 2,299 | 1,171 | 563 |
| 5 | 1,662 | 1,808 | 399 |
| 10 | 505 | 2,965 | 93 |
| 12 | 330 | 3,140 | 61 |
| 40 | 4 | 3,466 | 4 |
| 70 | 0 | 3,470 | 0 |

**Qarāʾin flags** (reported, never combined; knowledge yield is not computed; `huffaz_chain` now excludes gharīb by κ):

| flag | groups | share | recorded 0 (صحيح) among them |
|---|---|---|---|
| in_sahihayn | 2,690 | 0.133 | 0.935 |
| in_sahih_class | 6,756 | 0.333 | 0.649 |
| sound_distinct_routes | 1,557 | 0.077 | 0.978 |
| huffaz_chain | 1,185 | 0.058 | 0.992 |

All three flags together: 657 groups.

## Appendix A. Full `rawis.rank` vocabulary

| rank_no | rank | n | ordinal |
|---|---|---|---|
| 0 | (NULL) | 25 | 0 |
| 1 | صحابي | 2,187 | 12 |
| 1 | صحابية | 48 | 12 |
| 1 | مختلف في صحبته | 27 | 12 |
| 1 | صحابي صغير | 22 | 12 |
| 1 | له رؤية | 13 | 12 |
| 1 | له إدراك | 10 | 12 |
| 1 | لم تثبت له صحبة | 2 | 12 |
| 1 | مختلف في صحبته ، والأكثر أنه صحابي | 2 | 12 |
| 1 | مختلف في صحبتها | 2 | 12 |
| 1 | لها إدراك | 1 | 12 |
| 1 | لها رؤية | 1 | 12 |
| 2 | ثقة حافظ | 283 | 11 |
| 2 | ثقة ثبت | 191 | 11 |
| 2 | ثقة مأمون | 127 | 11 |
| 2 | ثقة إمام | 57 | 11 |
| 2 | ثقة متقن | 54 | 11 |
| 2 | ثقة حجة | 26 | 11 |
| 2 | ثقة محدث | 13 | 11 |
| 2 | ثقة ثقة | 12 | 11 |
| 2 | إمام حجة | 7 | 11 |
| 2 | ثقة أمين | 7 | 11 |
| 2 | ثقة إمام حافظ | 7 | 11 |
| 2 | ثقة حافظ إمام | 7 | 11 |
| 2 | حافظ ثقة | 7 | 11 |
| 2 | حافظ ثبت | 6 | 11 |
| 2 | ثقة ضابط | 5 | 11 |
| 2 | مختلف في صحبته | 5 | 11 |
| 2 | ثقة ثبت فاضل | 4 | 11 |
| 2 | إمام حافظ | 3 | 11 |
| 2 | ثبت حافظ | 3 | 11 |
| 2 | ثقة حافظ ثبت | 3 | 11 |
| 2 | ثقة حافظ حجة | 3 | 11 |
| 2 | ثقة حافظ فقيه | 3 | 11 |
| 2 | ثقة حافظ مصنف | 3 | 11 |
| 2 | حافظ متقن | 3 | 11 |
| 2 | أحد الحفاظ | 2 | 11 |
| 2 | إمام ثقة | 2 | 11 |
| 2 | ثقة إمام حجة | 2 | 11 |
| 2 | ثقة ثبت إمام | 2 | 11 |
| 2 | ثقة ثبت حافظ | 2 | 11 |
| 2 | ثقة حافظ أمين | 2 | 11 |
| 2 | ثقة حافظ متقن | 2 | 11 |
| 2 | ثقة حافظ نبيل | 2 | 11 |
| 2 | ثقة صالح | 2 | 11 |
| 2 | ثقة صدوق | 2 | 11 |
| 2 | ثقة عارف | 2 | 11 |
| 2 | ثقة فقيه حافظ | 2 | 11 |
| 2 | ثقة يحفظ | 2 | 11 |
| 2 | حافظ | 2 | 11 |
| 2 | أحد الأئمة ثقة حافظ | 1 | 11 |
| 2 | أحد الأئمة حافظ صنف السنن والتفسير والتاريخ | 1 | 11 |
| 2 | أحد العلماء الأثبات الفقهاء الكبار | 1 | 11 |
| 2 | إمام ثبت | 1 | 11 |
| 2 | إمام ثقة ثبت | 1 | 11 |
| 2 | إمام ثقة حافظ | 1 | 11 |
| 2 | إمام ثقة حجة | 1 | 11 |
| 2 | إمام جبل حجة | 1 | 11 |
| 2 | إمام حافظ ثبت | 1 | 11 |
| 2 | إمام حافظ ثقة مشهور | 1 | 11 |
| 2 | الإمام الحافظ | 1 | 11 |
| 2 | الإمام الحافظ الثقة | 1 | 11 |
| 2 | الإمام الحافظ الحجة ، محدث نيسابور | 1 | 11 |
| 2 | الإمام المحدث | 1 | 11 |
| 2 | الإمام المحدث الحجة | 1 | 11 |
| 2 | الحافظ الأوحد | 1 | 11 |
| 2 | الحافظ الإمام | 1 | 11 |
| 2 | الحافظ الثبت | 1 | 11 |
| 2 | الحافظ الثقة | 1 | 11 |
| 2 | الحافظ الثقة الإمام | 1 | 11 |
| 2 | الحافظ المتقن | 1 | 11 |
| 2 | الفقيه الحافظ متفق على جلالته وإتقانه | 1 | 11 |
| 2 | المجدد لأمر الدين على رأس المائتين | 1 | 11 |
| 2 | المحدث المسند أحد الثقات | 1 | 11 |
| 2 | ثبت رضي حجة إمام كبير الشأن | 1 | 11 |
| 2 | ثبت صحيح الكتاب | 1 | 11 |
| 2 | ثقة | 1 | 11 |
| 2 | ثقة أفضل أهل زمانه | 1 | 11 |
| 2 | ثقة أمين فقيه | 1 | 11 |
| 2 | ثقة إمام ثبت حافظ | 1 | 11 |
| 2 | ثقة إمام ثبت مأمون | 1 | 11 |
| 2 | ثقة إمام فاضل | 1 | 11 |
| 2 | ثقة إمام في التفسير والعلم | 1 | 11 |
| 2 | ثقة إمام في الحديث | 1 | 11 |
| 2 | ثقة إمام لكنه اختلط في آخر عمره | 1 | 11 |
| 2 | ثقة إمام محدث | 1 | 11 |
| 2 | ثقة إمام مقرئ | 1 | 11 |
| 2 | ثقة إمام مكثر | 1 | 11 |
| 2 | ثقة ثبت إلا أنه يرى القدر | 1 | 11 |
| 2 | ثقة ثبت إلا في روايته عن قتادة ففيها لين | 1 | 11 |
| 2 | ثقة ثبت إمام أعلم أهل عصره بالحديث وعلله | 1 | 11 |
| 2 | ثقة ثبت تغير في آخر عمره | 1 | 11 |
| 2 | ثقة ثبت حافظ عارف بالرجال والحديث | 1 | 11 |
| 2 | ثقة ثبت حافظ فقيه واسع الرحلة | 1 | 11 |
| 2 | ثقة ثبت ربما أغرب | 1 | 11 |
| 2 | ثقة ثبت رمي بالتشيع | 1 | 11 |
| 2 | ثقة ثبت سنى | 1 | 11 |
| 2 | ثقة ثبت عالم | 1 | 11 |
| 2 | ثقة ثبت فاضل ورع | 1 | 11 |
| 2 | ثقة ثبت فقيه إمام كبير مشهور | 1 | 11 |
| 2 | ثقة ثبت فقيه إمام مشهور | 1 | 11 |
| 2 | ثقة ثبت فقيه عالم جواد مجاهد جمعت فيه خصال الخير | 1 | 11 |
| 2 | ثقة ثبت فيه تشيع قليل | 1 | 11 |
| 2 | ثقة ثبت قد يخطئ في حديث الثوري | 1 | 11 |
| 2 | ثقة ثبت قدري | 1 | 11 |
| 2 | ثقة ثبت كبير القدر لا يرى الرواية بالمعنى | 1 | 11 |
| 2 | ثقة ثبت لكنه يدلس ويرسل | 1 | 11 |
| 2 | ثقة ثبت مشهور | 1 | 11 |
| 2 | ثقة ثبت مشهور بالتدليس | 1 | 11 |
| 2 | ثقة ثبت نبيل عابد | 1 | 11 |
| 2 | ثقة ثبت وقد رمي بالقدر | 1 | 11 |
| 2 | ثقة ثبتت حجة | 1 | 11 |
| 2 | ثقة جليل | 1 | 11 |
| 2 | ثقة حافظ أجل أصحاب ابن عيينة | 1 | 11 |
| 2 | ثقة حافظ إمام الجرح والتعديل | 1 | 11 |
| 2 | ثقة حافظ جليل | 1 | 11 |
| 2 | ثقة حافظ شهير ، وله أوهام | 1 | 11 |
| 2 | ثقة حافظ صاحب تصانيف | 1 | 11 |
| 2 | ثقة حافظ غلط في أحاديث | 1 | 11 |
| 2 | ثقة حافظ فاضل | 1 | 11 |
| 2 | ثقة حافظ فقيه إمام حجة وربما دلس | 1 | 11 |
| 2 | ثقة حافظ فقيه حجة | 1 | 11 |
| 2 | ثقة حافظ له تصانيف | 1 | 11 |
| 2 | ثقة حافظ مأمون | 1 | 11 |
| 2 | ثقة حافظ متقن إمام | 1 | 11 |
| 2 | ثقة حافظ متقن عابد | 1 | 11 |
| 2 | ثقة حافظ وكان يدلس أسماء الشيوخ | 1 | 11 |
| 2 | ثقة حجة حافظ | 1 | 11 |
| 2 | ثقة سني فقيه حافظ | 1 | 11 |
| 2 | ثقة صاحب حديث | 1 | 11 |
| 2 | ثقة صاحب حديث من أهل السنة | 1 | 11 |
| 2 | ثقة صادق حافظ | 1 | 11 |
| 2 | ثقة عارف بالحديث | 1 | 11 |
| 2 | ثقة عالم | 1 | 11 |
| 2 | ثقة فاضل مأمون | 1 | 11 |
| 2 | ثقة فاضل متقن حافظ | 1 | 11 |
| 2 | ثقة فقيه | 1 | 11 |
| 2 | ثقة فقيه ثبت | 1 | 11 |
| 2 | ثقة فقيه حافظ إمام جبل | 1 | 11 |
| 2 | ثقة فقيه صالح | 1 | 11 |
| 2 | ثقة فقيه عابد | 1 | 11 |
| 2 | ثقة فقيه فاضل | 1 | 11 |
| 2 | ثقة فقيه مشهور | 1 | 11 |
| 2 | ثقة فقيه من أهل السنة | 1 | 11 |
| 2 | ثقة فقيه ورع | 1 | 11 |
| 2 | ثقة فهم | 1 | 11 |
| 2 | ثقة مأمون حافظ مشهور | 1 | 11 |
| 2 | ثقة مأمون سنى | 1 | 11 |
| 2 | ثقة متقن حافظ | 1 | 11 |
| 2 | ثقة متقن حافظ إمام قدوة | 1 | 11 |
| 2 | ثقة متقن صحيح الكتاب | 1 | 11 |
| 2 | ثقة متقن فقيه ورع | 1 | 11 |
| 2 | ثقة متقن لا يروي إلا عن الثقات | 1 | 11 |
| 2 | ثقة متقن من أثبت الناس في الموطأ | 1 | 11 |
| 2 | ثقة محدث حافظ | 1 | 11 |
| 2 | ثقة مسند | 1 | 11 |
| 2 | ثقة نبيل | 1 | 11 |
| 2 | ثقة نبيل حافظ | 1 | 11 |
| 2 | ثقة ورع متقن متثبت | 1 | 11 |
| 2 | جبل الحفظ وإمام الدنيا في فقه الحديث | 1 | 11 |
| 2 | حافظ إمام فقيه مكثر | 1 | 11 |
| 2 | حافظ ثبت حجة | 1 | 11 |
| 2 | حافظ ثقة تغير بأخرة | 1 | 11 |
| 2 | حافظ ثقة ثبت | 1 | 11 |
| 2 | حافظ حجة | 1 | 11 |
| 2 | حافظ حجة متقن | 1 | 11 |
| 2 | حافظ كبير | 1 | 11 |
| 2 | حافظ متفق عليه | 1 | 11 |
| 2 | حافظ متقن ثبت | 1 | 11 |
| 2 | حافظ محدث متقن | 1 | 11 |
| 2 | رأس المتقنين وكبير المتثبتين | 1 | 11 |
| 2 | رأس في معرفة الحديث | 1 | 11 |
| 2 | ركن السنة والحديث | 1 | 11 |
| 2 | مخضرم | 1 | 11 |
| 2 | من أثبات المحدثين | 1 | 11 |
| 2 | من أكابر الرؤساء والمحدثين | 1 | 11 |
| 2 | من الحفاظ الكبار الثقات | 1 | 11 |
| 3 | ثقة | 6,002 | 10 |
| 3 | له رؤية | 32 | 10 |
| 3 | مختلف في صحبته | 14 | 10 |
| 3 | ثقة صدوق | 8 | 10 |
| 3 | صحابي صغير | 6 | 10 |
| 3 | ثقة فاضل | 5 | 10 |
| 3 | ثقة مخضرم | 5 | 10 |
| 3 | ثقة يرسل | 5 | 10 |
| 3 | مخضرم | 5 | 10 |
| 3 | ثقة له أفراد | 4 | 10 |
| 3 | ثقة رمي بالنصب | 3 | 10 |
| 3 | لم تثبت له صحبة | 3 | 10 |
| 3 | له إدراك | 3 | 10 |
| 3 | ثقة حافظ | 2 | 10 |
| 3 | ثقة رمي بالإرجاء | 2 | 10 |
| 3 | ثقة رمي بالتشيع | 2 | 10 |
| 3 | ثقة رمي بالقدر | 2 | 10 |
| 3 | ثقة صالح | 2 | 10 |
| 3 | ثقة فقيه وكان يرسل | 2 | 10 |
| 3 | ثقة مدلس | 2 | 10 |
| 3 | ثقة مكثر | 2 | 10 |
| 3 | ثقة وكان يدلس كثيرا | 2 | 10 |
| 3 | ثقة يدلس | 2 | 10 |
| 3 | ثقه | 2 | 10 |
| 3 | صحابية صغيرة | 2 | 10 |
| 3 | مختلف في صحبته ، والراجح أنه تابعي ثقة | 2 | 10 |
| 3 | إمام فاضل | 1 | 10 |
| 3 | ثقة ، شيعي جلد | 1 | 10 |
| 3 | ثقة ، يميل إلى التشيع | 1 | 10 |
| 3 | ثقة إلا أنه رمي بالقدر | 1 | 10 |
| 3 | ثقة إلا في حديثه عن الثوري ففيه لين | 1 | 10 |
| 3 | ثقة إلا في حديثه عن زائدة | 1 | 10 |
| 3 | ثقة إلا في روايته عن الثوري وشعبة فهي ضعيفة | 1 | 10 |
| 3 | ثقة إمام | 1 | 10 |
| 3 | ثقة إمام عالم | 1 | 10 |
| 3 | ثقة اختلط قبل موته | 1 | 10 |
| 3 | ثقة تغير | 1 | 10 |
| 3 | ثقة تغير بأخرة فلم يفحش اختلاطه | 1 | 10 |
| 3 | ثقة تغير حفظه قليلا | 1 | 10 |
| 3 | ثقة تكلموا في روايته عن أبيه لصغره | 1 | 10 |
| 3 | ثقة ثبت كثير التدليس والإرسال الخفي | 1 | 10 |
| 3 | ثقة حجة | 1 | 10 |
| 3 | ثقة رمي ببدعة | 1 | 10 |
| 3 | ثقة رمي برأي الخوارج وصح رجوعه عنه | 1 | 10 |
| 3 | ثقة زاهد | 1 | 10 |
| 3 | ثقة عابد ، تغير حفظه قليلا بآخره | 1 | 10 |
| 3 | ثقة عابد مخضرم | 1 | 10 |
| 3 | ثقة فقيه إمام في المغازي | 1 | 10 |
| 3 | ثقة فقيه جليل | 1 | 10 |
| 3 | ثقة فقيه كثير الإرسال | 1 | 10 |
| 3 | ثقة فقيه مصنف | 1 | 10 |
| 3 | ثقة في حديثه وهم | 1 | 10 |
| 3 | ثقة في غير الزهري ، وضعيف في حديث الزهري | 1 | 10 |
| 3 | ثقة فيه تشيع | 1 | 10 |
| 3 | ثقة فيه نصب | 1 | 10 |
| 3 | ثقة كثير الإرسال | 1 | 10 |
| 3 | ثقة كثير الحديث | 1 | 10 |
| 3 | ثقة مرضي | 1 | 10 |
| 3 | ثقة مسند | 1 | 10 |
| 3 | ثقة مشهور | 1 | 10 |
| 3 | ثقة مصنف | 1 | 10 |
| 3 | ثقة يتشيع | 1 | 10 |
| 3 | ثقة يرسل عن الصحابة | 1 | 10 |
| 3 | ثقة يرسل كثيرا ويدلس | 1 | 10 |
| 3 | حافظ | 1 | 10 |
| 3 | شيخ ثقة | 1 | 10 |
| 3 | صدوق ثقة | 1 | 10 |
| 3 | صدوق حسن الحديث | 1 | 10 |
| 3 | كان حافظا | 1 | 10 |
| 3 | لها إدراك | 1 | 10 |
| 3 | لها رؤية | 1 | 10 |
| 3 | مختلف في صحبته ، والراجح أنه من ثقات التابعين | 1 | 10 |
| 3 | مختلف في صحبته ، وهو تابعي ثقة | 1 | 10 |
| 3 | مختلف في صحبته والراجح أنه تابعي ثقة | 1 | 10 |
| 3 | مختلف في صحبتها ، والراجح أنها تابعية ثقة | 1 | 10 |
| 3 | مخضرم ، مختلف في صحبته ، والراجح أنه تابعي ثقة | 1 | 10 |
| 3 | مخضرم ثقة جليل | 1 | 10 |
| 3 | مقبول | 1 | 10 |
| 4 | صدوق حسن الحديث | 5,649 | 9 |
| 4 | صدوق | 8 | 9 |
| 4 | له رؤية | 6 | 9 |
| 4 | مختلف في صحبته | 4 | 9 |
| 4 | صحابي صغير | 3 | 9 |
| 4 | صدوق رمي بالتشيع | 3 | 9 |
| 4 | صدوق رمي بالقدر | 2 | 9 |
| 4 | له إدراك | 2 | 9 |
| 4 | مخضرم | 2 | 9 |
| 4 | شيعي صدوق | 1 | 9 |
| 4 | صدوف حسن الحديث | 1 | 9 |
| 4 | صدوق إلا أنه يدلس | 1 | 9 |
| 4 | صدوق اختلط بآخره | 1 | 9 |
| 4 | صدوق اختلط قبل موته وضابطه أن من سمع منه ببغداد فبعد الاختلاط | 1 | 9 |
| 4 | صدوق تغير | 1 | 9 |
| 4 | صدوق تغير بآخره قدر ست سنين | 1 | 9 |
| 4 | صدوق تكلم في حديثه عن الأعمش | 1 | 9 |
| 4 | صدوق تكلم فيه للقدر | 1 | 9 |
| 4 | صدوق تكلم فيه للوقف في القرآن | 1 | 9 |
| 4 | صدوق تكلموا في روايته عن هقل | 1 | 9 |
| 4 | صدوق ثبت في القراءة | 1 | 9 |
| 4 | صدوق جهمي كبر فصار يتلقن | 1 | 9 |
| 4 | صدوق حسن الأصول | 1 | 9 |
| 4 | صدوق حسن الحديث غال في التشيع | 1 | 9 |
| 4 | صدوق حسن لحديث | 1 | 9 |
| 4 | صدوق حين الحديث | 1 | 9 |
| 4 | صدوق رمي بالإرجاء | 1 | 9 |
| 4 | صدوق صالح فقيه | 1 | 9 |
| 4 | صدوق عارف | 1 | 9 |
| 4 | صدوق فاضل | 1 | 9 |
| 4 | صدوق فاضل عالم صالح | 1 | 9 |
| 4 | صدوق فقيه | 1 | 9 |
| 4 | صدوق فقيه إمام | 1 | 9 |
| 4 | صدوق كان على مذهب الخوارج ، ويقال : رجع عن ذلك | 1 | 9 |
| 4 | صدوق كان يدلس عن الحسن | 1 | 9 |
| 4 | صدوق كان يصحف | 1 | 9 |
| 4 | صدوق كثير الإرسال | 1 | 9 |
| 4 | صدوق لكن عيب عليه شيء يتعلق بالقضاء | 1 | 9 |
| 4 | صدوق له أوهام | 1 | 9 |
| 4 | صدوق مدلس | 1 | 9 |
| 4 | صدوق مشهور | 1 | 9 |
| 4 | صدوق مصنف | 1 | 9 |
| 4 | صدوق يرسل | 1 | 9 |
| 4 | صدوق يغرب | 1 | 9 |
| 4 | لا بأس به | 1 | 9 |
| 4 | له إدراك ورؤية | 1 | 9 |
| 4 | مجهول الحال | 1 | 9 |
| 4 | مختلف في صحبته والراجح أنه تابعي صدوق حسن الحديث | 1 | 9 |
| 5 | صدوق يخطئ | 79 | 8 |
| 5 | صدوق يهم | 27 | 8 |
| 5 | صدوق له أوهام | 25 | 8 |
| 5 | صدوق يغرب | 9 | 8 |
| 5 | صدوق رمي بالتشيع | 8 | 8 |
| 5 | صدوق رمي ببدعة | 8 | 8 |
| 5 | صدوق كثير الخطأ | 8 | 8 |
| 5 | صدوق سيء الحفظ | 7 | 8 |
| 5 | صدوق يتشيع | 7 | 8 |
| 5 | صدوق تغير بآخره | 6 | 8 |
| 5 | صدوق ربما وهم | 6 | 8 |
| 5 | صدوق فيه لين | 6 | 8 |
| 5 | صدوق رمي بالقدر | 4 | 8 |
| 5 | صدوق سيئ الحفظ | 4 | 8 |
| 5 | صدوق يخطئ كثيرا | 4 | 8 |
| 5 | صدوق ربما أخطأ | 3 | 8 |
| 5 | صدوق رمي بالإرجاء | 3 | 8 |
| 5 | صدوق له غرائب | 3 | 8 |
| 5 | صدوق يخطىء | 3 | 8 |
| 5 | صدوق يهم كثيرا | 3 | 8 |
| 5 | صدوق اختلط | 2 | 8 |
| 5 | صدوق اختلط بآخره | 2 | 8 |
| 5 | صدوق اختلط بأخرة | 2 | 8 |
| 5 | صدوق تغير بآخرة | 2 | 8 |
| 5 | صدوق ساء حفظه | 2 | 8 |
| 5 | صدوق فيه تشيع | 2 | 8 |
| 5 | صدوق يخطئ ويخالف | 2 | 8 |
| 5 | صدوق يغلط | 2 | 8 |
| 5 | صدوق اخباري رمي برأي الخوارج | 1 | 8 |
| 5 | صدوق اختلط بآخرة | 1 | 8 |
| 5 | صدوق اختلط قبل موته | 1 | 8 |
| 5 | صدوق تغير بأخرة | 1 | 8 |
| 5 | صدوق تغير حفظه | 1 | 8 |
| 5 | صدوق تغير حفظه لما قدم بغداد ، وكان فقيها | 1 | 8 |
| 5 | صدوق تغير في آخره | 1 | 8 |
| 5 | صدوق تغير لما كبر وأدخل عليه ابنه ما ليس من حديثه | 1 | 8 |
| 5 | صدوق تكلم فيه للنصب | 1 | 8 |
| 5 | صدوق خلط بأخرة | 1 | 8 |
| 5 | صدوق ربما أخطأ ، وربما دلس مكثر من التحديث عن المتروكين | 1 | 8 |
| 5 | صدوق ربما أغرب وخالف | 1 | 8 |
| 5 | صدوق ربما خالف | 1 | 8 |
| 5 | صدوق ربما وهم ، ورمي بالإرجاء | 1 | 8 |
| 5 | صدوق ربما وهم وكان فاضلا | 1 | 8 |
| 5 | صدوق ربما يخطئ | 1 | 8 |
| 5 | صدوق رمي بالإرجاء لم يصب من ضعفه | 1 | 8 |
| 5 | صدوق رمي بالإرجاء والنصب | 1 | 8 |
| 5 | صدوق رمي بالتشيع ثم اختلط | 1 | 8 |
| 5 | صدوق رمي بالرفض | 1 | 8 |
| 5 | صدوق رمي بالرفض ويقال : رجع عنه | 1 | 8 |
| 5 | صدوق رمي بالغلو في التشيع | 1 | 8 |
| 5 | صدوق رمي بالقدر والتشيع | 1 | 8 |
| 5 | صدوق رمي بالقدر وبالتشيع | 1 | 8 |
| 5 | صدوق رمي بالنصب | 1 | 8 |
| 5 | صدوق رمي ببدعة الرفض | 1 | 8 |
| 5 | صدوق سيء الحفظ ، تغير بآخره وروايته عن عكرمة مضطربة | 1 | 8 |
| 5 | صدوق سيء الحفظ ، له أغلاط | 1 | 8 |
| 5 | صدوق سيء الحفظ خلط بآخره ورمي بالإرجاء | 1 | 8 |
| 5 | صدوق سيء الحفظ يخطئ كثيرا | 1 | 8 |
| 5 | صدوق شيعي | 1 | 8 |
| 5 | صدوق شيعي بغيض | 1 | 8 |
| 5 | صدوق طعنوا فيه للرأي | 1 | 8 |
| 5 | صدوق عارف رمي بالتشيع | 1 | 8 |
| 5 | صدوق في روايته عن أهل بلده وخلط في غيرهم | 1 | 8 |
| 5 | صدوق فيه غفلة | 1 | 8 |
| 5 | صدوق كثير الأوهام | 1 | 8 |
| 5 | صدوق كثير الإرسال | 1 | 8 |
| 5 | صدوق كثير الإرسال والأوهام | 1 | 8 |
| 5 | صدوق كثير التدليس عن الضعفاء | 1 | 8 |
| 5 | صدوق كثير التدليس والإرسال | 1 | 8 |
| 5 | صدوق كثير الخطأ ، وحديثه عن عطاء ضعيف | 1 | 8 |
| 5 | صدوق كثير الخطأ والتدليس | 1 | 8 |
| 5 | صدوق كثير الخطأ والوهم ، ورمي بالإرجاء | 1 | 8 |
| 5 | صدوق كثير الخطا يغرب | 1 | 8 |
| 5 | صدوق له أفراد | 1 | 8 |
| 5 | صدوق له خطأ كثير | 1 | 8 |
| 5 | صدوق له مناكير | 1 | 8 |
| 5 | صدوق لين الحديث | 1 | 8 |
| 5 | صدوق مبتدع | 1 | 8 |
| 5 | صدوق مدلس | 1 | 8 |
| 5 | صدوق ناصبي | 1 | 8 |
| 5 | صدوق وكان يدلس ويتشيع | 1 | 8 |
| 5 | صدوق يحفظ وله غرائب | 1 | 8 |
| 5 | صدوق يخطئ اختلط ورمي بالقدر | 1 | 8 |
| 5 | صدوق يخطئ ويدلس | 1 | 8 |
| 5 | صدوق يخطئ ويهم | 1 | 8 |
| 5 | صدوق يدلس ويسوي | 1 | 8 |
| 5 | صدوق يهم ، ورمي برأي الخوارج | 1 | 8 |
| 5 | صدوق يهم ويخطئ | 1 | 8 |
| 5 | صدوقة اختلطت | 1 | 8 |
| 5 | محله الصدق وفيه غفلة | 1 | 8 |
| 6 | مقبول | 5,854 | 7 |
| 6 | مختلف في صحبته | 12 | 7 |
| 6 | له إدراك | 8 | 7 |
| 6 | انفرد بتوثيقه ابن حبان | 7 | 7 |
| 6 | مقبولة | 4 | 7 |
| 6 | لم تثبت له صحبة | 3 | 7 |
| 6 | له رؤية | 3 | 7 |
| 6 | لم يثبت له صحبة | 2 | 7 |
| 6 | لين الحديث | 2 | 7 |
| 6 | مختلف في صحبته ، والراجح أنه تابعي | 2 | 7 |
| 6 | انفرد بتوثيقه ابن شاهين | 1 | 7 |
| 6 | فقيه مشهور مؤسس المذهب الحنفي | 1 | 7 |
| 6 | مفبول | 1 | 7 |
| 6 | مقبول من غلاة الشيعة | 1 | 7 |
| 7 | مجهول الحال | 22,308 | 6 |
| 7 | انفرد بتوثيقه ابن حبان | 588 | 6 |
| 7 | مختلف في صحبته | 57 | 6 |
| 7 | مجهولة الحال | 21 | 6 |
| 7 | لم تثبت له صحبة | 8 | 6 |
| 7 | له إدراك | 3 | 6 |
| 7 | له رؤية | 2 | 6 |
| 7 | مجهول | 2 | 6 |
| 7 | مختلف في صحبتها | 2 | 6 |
| 7 | أدرك النبي ولم يره | 1 | 6 |
| 7 | انفرد بتوثيقها ابن حبان | 1 | 6 |
| 7 | ضعيف الحديث | 1 | 6 |
| 7 | لم تثبت صحبتها | 1 | 6 |
| 7 | لم تثبت له صحبه | 1 | 6 |
| 7 | مجهوال الحال | 1 | 6 |
| 7 | مختلف في صحبته ، والراجح أنه تابعي | 1 | 6 |
| 7 | مخضرم | 1 | 6 |
| 7 | مقبول | 1 | 6 |
| 7 | وثقه ابن حبان | 1 | 6 |
| 8 | ضعيف الحديث | 1,762 | 5 |
| 8 | ضعيف | 4 | 5 |
| 8 | ضعف الحديث | 3 | 5 |
| 8 | مختلف في صحبته ، والراجح أنه تابعي ضعيف الحديث | 2 | 5 |
| 8 | انفرد بتوثيقه ابن حبان | 1 | 5 |
| 8 | ضعيف ، وكان غاليا في التشيع | 1 | 5 |
| 8 | ضعيف أسن واختلط | 1 | 5 |
| 8 | ضعيف اختلط بآخرة | 1 | 5 |
| 8 | ضعيف الحديث ، اختلط | 1 | 5 |
| 8 | ضعيف الحديث مع صلاحه وعدالته | 1 | 5 |
| 8 | ضعيف رافضي سيء الحفظ | 1 | 5 |
| 8 | ضعيف رمي بالرفض | 1 | 5 |
| 8 | ضعيف زاهد | 1 | 5 |
| 8 | ضعيف سيء الحفظ | 1 | 5 |
| 8 | ضعيف غال في التشيع | 1 | 5 |
| 8 | ضعيف غير محتج بحديثه | 1 | 5 |
| 8 | ضعيف كثير الغلط كثير الحديث | 1 | 5 |
| 8 | ضعيف لا يتابع على حديثه | 1 | 5 |
| 8 | ضعيف مجهول | 1 | 5 |
| 8 | ضعيف وهو ممن تغير | 1 | 5 |
| 8 | مختلف في صحبته | 1 | 5 |
| 9 | مجهول | 1,866 | 4 |
| 9 | انفرد بتوثيقه ابن حبان | 1 | 4 |
| 9 | لم تثبت له صحبة | 1 | 4 |
| 10 | متروك الحديث | 629 | 3 |
| 10 | منكر الحديث | 319 | 3 |
| 10 | ضعيف الحديث | 7 | 3 |
| 10 | أسلم في عهد النبي ولم يمت على الإيمان | 1 | 3 |
| 10 | ذاهب الحديث | 1 | 3 |
| 10 | فيه نظر | 1 | 3 |
| 10 | متروك الحدبث | 1 | 3 |
| 10 | متروك رمي بالقدر | 1 | 3 |
| 10 | متروك شديد التشيع | 1 | 3 |
| 10 | متروك غال في التشيع | 1 | 3 |
| 10 | متروك كثير الوهم | 1 | 3 |
| 10 | متروك متهم بالوضع | 1 | 3 |
| 10 | متروك وكان حافظا | 1 | 3 |
| 10 | متهم بالكذب | 1 | 3 |
| 11 | متهم بالوضع | 325 | 2 |
| 11 | متهم بالكذب | 141 | 2 |
| 11 | كذاب | 21 | 2 |
| 11 | متهم | 21 | 2 |
| 11 | متروك متهم بالكذب | 9 | 2 |
| 11 | متهم بالكذب والوضع | 5 | 2 |
| 11 | متروك متهم بالوضع | 3 | 2 |
| 11 | متهم بوضع الحديث | 3 | 2 |
| 11 | متهم بالوصع | 2 | 2 |
| 11 | ضعيف متهم بالكذب | 1 | 2 |
| 11 | كذاب ذاهب الحديث | 1 | 2 |
| 11 | متروك الحديث ، متهم بالوضع | 1 | 2 |
| 11 | متروك متهم | 1 | 2 |
| 11 | متهم بالكذب رغم كونه حافظا | 1 | 2 |
| 11 | متهم بالكذب ورمي بالرفض | 1 | 2 |
| 11 | متهم بالوضع والكذب | 1 | 2 |
| 11 | متهم بسرقة الحديث | 1 | 2 |
| 11 | متهم هالك | 1 | 2 |
| 11 | منكر الحديث | 1 | 2 |
| 12 | كذاب | 100 | 1 |
| 12 | يضع الحديث | 72 | 1 |
| 12 | وضاع | 46 | 1 |
| 12 | كذاب خبيث | 6 | 1 |
| 12 | يكذب | 6 | 1 |
| 12 | كذاب وضاع | 5 | 1 |
| 12 | (NULL) | 4 |  |
| 12 | كذاب يضع الحديث | 4 | 1 |
| 12 | متهم بالوضع | 3 | 1 |
| 12 | وضاع كذاب | 2 | 1 |
| 12 | رافضي يضع الحديث | 1 | 1 |
| 12 | كذاب مارق من الغلاة | 1 | 1 |
| 12 | كذاب يروي المناكير | 1 | 1 |
| 12 | متروك متهم بالكذب والوضع | 1 | 1 |
| 12 | وضاع رافضي | 1 | 1 |
| 12 | يكذب ويضع الحديث | 1 | 1 |

_Audit computed in 9.1s._
