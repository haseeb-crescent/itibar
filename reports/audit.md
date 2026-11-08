# itibar — source audit

Generated 2026-11-08 15:12 by `make audit` (`itibar.audit`) from the Parquet copy of `hadith-kg.db` (Hugging Face `emadjumaah/hadith-kg` @ `8ae7e3d5be28`, sha256 `d528084321e71500…`). Upstream comparison values are from `DATA_REPORT.md` at `emadjumaah/hadith@b5a0cf2`.

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

`upstream` = distinct chain-end narrators with rank exactly `صحابي`; `itibar` = distinct companions (rank_no 1 minus the labels that deny companionship) at chain ends; `on path` = companions narrating directly from PROPHET on an unbroken route to a book (`records.companions`; requires `make bundles`).

| group_id | declared | upstream | itibar | on_path | opening |
|---|---|---|---|---|---|
| 2 | 68 | 63 | 66 | 65 | توضأ فغسل وجهه أخذ غرفة من ماء فمضمض بها واستنشق ث |
| 4 | 46 | 41 | 42 | 41 | إذا قمت إلى الصلاة فأسبغ الوضوء ثم استقبل القبلة ف |
| 3 | 67 | 60 | 61 | 61 | يتوضأ فغسل وجهه ويديه ومسح برأسه ومسح على الخفين |
| 1 | 68 | 64 | 66 | 66 | لا تكذبوا علي فإنه من كذب علي فليلج النار |
| 5 | 44 | 35 | 39 | 35 | صلى لنا رسول الله ركعتين من بعض الصلوات ثم قام فلم |
| 6 | 38 | 31 | 32 | 30 | أقام النبي تسعة عشر يقصر فنحن إذا سافرنا تسعة عشر  |
| 8 | 54 | 45 | 48 | 47 | نهى رسول الله عن الدباء والحنتم والمقير والمزفت |
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

Raw-only values are ranges or approximations the build declined to parse, e.g. `130 - 121` (16), `290 - 281` (14), `300 - 291` (11), `23 - 13` (7), `158 - 136` (6), `40 - 20` (6), `35 - 23` (5), `530 - 540` (4). itibar keeps them beside the parsed value (terminus columns) and never parses them itself. Birth years are rare, so the continuity check falls back to tabaka for most links (§8.5).

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
| سعيد بن عثمان التنوخي | 2 | 2 | 95 |

A cluster can only change kappa inside a group where two of its members both occur: that happens 63 times (group × cluster). `kappa_lower` merges every cluster into one node. Misresolution across *different* full names is not caught by these clusters: e.g. `يحيى بن سعيد` resolved to al-Qattan (r8271, nickname `يحيى بن سعيد القطان`) where the student of al-Taymi is al-Ansari (r8272, `يحيى بن سعيد الأنصاري`) in six chains of *innama al-a'mal* (tests/gold/gold.yaml). Same-name clusters by `nickname` alone would be 2,545.

### 6.2 The 25 stubs

| id | name | chain_links | min_pos | max_pos |
|---|---|---|---|---|
| 40,137 | عَبْدُ اللَّهِ بْنُ عُبَيْدَةَ | 6 | 1 | 6 |
| 47,654 | كُرَيْبٍ السَّحُولِيِّ | 6 | 6 | 10 |
| 51,756 | بِنْتِ كُرْزٍ | 5 | 5 | 7 |
| 44,306 | مُحَمَّدِ بْنِ عَبْدِ الصَّمَدِ | 5 | 4 | 9 |
| 50,119 | أَبِي | 4 | 8 | 10 |
| 44,304 | عَبْدُ الْمُؤْمِنِ | 4 | 2 | 7 |
| 40,740 | وَمُحَمَّدُ بْنُ الْحُسَيْنِ | 2 | 2 | 2 |
| 50,437 | السُّمَيْطِ الْبَجَلِيِّ | 2 | 6 | 6 |
| 44,305 | أَبَاهُ | 2 | 4 | 4 |
| 47,655 | عَبْدِ اللَّهِ بْنِ حُذَيْمٍ | 2 | 5 | 5 |
| 9,481 | غير معرف | 2 | 7 | 7 |
| 26,043 | عِيسَى بْنُ الأَشْعَثِ | 2 | 4 | 8 |
| 50,436 | أَبِيهِ | 2 | 6 | 7 |
| 47,653 | النُّعْمَانِ بْنِ نُعَيْمٍ | 2 | 5 | 7 |
| 60,137 | مَخْرَمَةَ الْعَبْدِيِّ | 2 | 5 | 5 |
| 40,741 | وَأَبُو مُسْلِمٍ | 2 | 2 | 2 |
| 40,138 | مُحَمَّدُ بْنُ عَمْرٍو | 2 | 1 | 3 |
| 40,139 | سَعْدِ بْنِ عُثْمَانَ | 1 | 4 | 4 |
| 40,142 | مُحَمَّدِ بْنِ مَطَرٍ | 1 | 2 | 2 |
| 40,260 | قَيْسٌ السَّعِيدِيُّ | 1 | 4 | 4 |
| 61,758 | الأَخْنَسِ بْنِ زُهَيْرٍ | 1 | 7 | 7 |
| 60,136 | مَنْدُوسٍ | 1 | 6 | 6 |
| 45,025 | جَعْفَر بْنِ الْفُرَافِصَةِ الْحَنَفِيِّ | 1 | 4 | 4 |
| 60,677 | سَنْجَوَيْهِ النَّاهِكِيُّ | 1 | 3 | 3 |
| 45,024 | سَعِيدِ بْنِ عَوْسَجَةَ | 1 | 3 | 3 |

Stubs touch 60 chain links. They get ordinal 0 (below every threshold but `all`) and are dropped in `kappa_lower`. Several names are relational (`أبي`, `أبيه`, `أباه`).

### 6.3 Marfu'/qudsi chains not ending in a companion

| chain_end | chains | counted_by_upstream |
|---|---|---|
| companion: صحابي | 521,664 | 0 |
| break marker (30002) | 32,497 | 0 |
| companion: صحابية | 10,646 | 10,646 |
| unnamed person (1131) | 5,040 | 0 |
| companion: صحابي صغير | 3,879 | 3,879 |
| companion: مختلف في صحبته | 1,085 | 1,085 |
| other narrator, rank_no 3 | 1,001 | 1,001 |
| rank_no 1, not a companion: له إدراك | 284 | 284 |
| other narrator, rank_no 7 | 264 | 264 |
| companion: له رؤية | 196 | 196 |
| other narrator, rank_no 6 | 116 | 116 |
| other narrator, rank_no 2 | 99 | 99 |
| other narrator, rank_no 8 | 72 | 72 |
| other narrator, rank_no 4 | 68 | 68 |
| other narrator, rank_no 9 | 56 | 56 |
| companion: مختلف في صحبته ، والأكثر أنه صحابي | 31 | 31 |
| stub | 11 | 0 |
| companion: لها رؤية | 7 | 7 |
| companion: مختلف في صحبتها | 4 | 4 |
| other narrator, rank_no 5 | 2 | 2 |
| other narrator, rank_no 10 | 1 | 1 |
| break marker (30000) | 1 | 0 |

Upstream's 17,811 counts chain ends whose label is not exactly `صحابي`: it **includes** 10,646 chains ending at female companions and 3,879 at `صحابي صغير`, and **excludes** every chain ending at a NULL-rank placeholder (37,538, mostly `موضع إرسال`, the source's own irsal marker). By itibar's companion rule (rank_no 1, minus `لم تثبت له صحبة` / `له إدراك` / `لها إدراك`) **39,512** marfu'/qudsi chains do not end in a companion; these are kept in their bundles, flagged mursal, and get no PROPHET edge.

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

See §6.1. Not mergeable without a name-resolution model (out of scope); the continuity check is the visible symptom. The gold set documents every such chain it meets.

### 8.5 Layer gaps along chain links (calibrating the continuity window)

| student_minus_teacher | links | share |
|---|---|---|
| 0 | 181,588 | 0.049 |
| 1 | 685,435 | 0.183 |
| 2 | 1,438,125 | 0.384 |
| 3 | 1,028,658 | 0.275 |
| 4 | 244,461 | 0.065 |
| 5 | 32,622 | 0.009 |
| 6+ | 8,720 | 0.002 |
| missing | 86,393 | 0.023 |
| negative | 36,605 | 0.010 |

| link | teacher tabaka | student tabaka | gap |
|---|---|---|---|
| Anas → al-Zuhri | 1 | 4 | 3 |
| 'Alqama → al-Taymi | 2 | 5 | 3 |
| al-Zuhri → Malik | 4 | 7 | 3 |
| Qatada → Shu'ba | 4 | 7 | 3 |
| al-Zuhri → Ibn 'Uyayna | 4 | 8 | 4 |
| 'Umar → al-Taymi (dropped link) | 1 | 5 | 4 |

The brief's window [0, 1, 2] would mark every gap-3 and gap-4 link incompatible — about 36% of all links, including canonical ones above. itibar uses [0, 1, 2, 3, 4] (`config/structure.yaml`), which keeps them; incompatible then means a gap of 5+ layers (~125 years) or a student placed before the teacher. The continuity flags are reported, never used in kappa or the derived grade.

### 8.6 `max_rank` includes the compiler

| chains | agree_full | agree_derived | compiler_strictly_weakest | other_classes |
|---|---|---|---|---|
| 577,020 | 577,020 | 569,379 | 7,641 | 0 |

`agree_full`: our weakest link over the whole stored chain equals `max_rank` (the like-for-like check of our reading). `agree_derived`: the same with the compiler at pos 0 excluded, as the derived grade does; every disagreement is a chain whose compiler is strictly weaker than everyone else in it.

### 8.7 Summary of modelling consequences

- break markers: per-chain, untraversable gap nodes (no fused hubs; broken chains do not count as routes)
- unnamed person: per-(student, teacher) node, ordinal 0
- compiler node in front of every book; book nodes never cut
- self-loops dropped; cycles handled; path counts flagged on cyclic bundles
- companion = rank_no 1 minus explicit denials; mursal chains kept, not connected to PROPHET
- continuity window calibrated to the source scale ([0..4])
- `kappa_lower`: min(κ with homonym clusters merged (min ordinal), unnamed persons merged per student and stubs dropped; κ with stubs dropped only) — merging alone can splice two half-routes into a new route

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

_Audit computed in 1.4s._
