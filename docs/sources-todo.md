# Source texts — added, deferred, and candidates

A running log of which wisdom texts are in the corpus, which we want next, and —
importantly — **what sourcing we've already tried** so we don't re-derive it.

The corpus is built only from **public-domain plain-text** we can fetch and parse
(see `pipeline/chunk.py`). Each source needs: a raw text in `data/raw/`, a bespoke
parser function, an entry in `fetch.sh` + `main()`, then a rebuild
(`distill.py` → `embed_project.py` → `embed_search.py` → `ideas.py`) and, if it's a
new *tradition*, a lineage node.

---

## Where we look (in order)

1. **Project Gutenberg** — clean, reliably-fetchable plain text. Search via the
   **gutendex API**: `https://gutendex.com/books/?search=<terms>&languages=en`.
   This is the first and best stop; every current source came from here.
2. **archive.org** — huge, but texts are **OCR'd scans** (messy: hyphenation,
   running heads, footnote bleed). **Now workable** — see the OCR pipeline below.
   Two gotchas learned 2026-07-09 doing the Gāthās:
   - The djvu.txt is **NOT** `<identifier>_djvu.txt`. The filename is prefixed by
     the item's own title (e.g. `2015.110222.The-Sacred-Books-Of-The-East-Vol-31_djvu.txt`).
     Resolve it from the metadata API first:
     `curl -s https://archive.org/metadata/<id>/files | grep -oE '"[^"]*_djvu\.txt"'`
     then download `https://archive.org/download/<id>/<that-name>`. `fetch.sh` now
     does this automatically for its archive.org entries.
   - Search via `https://archive.org/advancedsearch.php?q=...&output=json`.
3. **sacred-texts.com** — has essentially everything we want, cleanly. **BUT it
   403-blocks automated fetches** — confirmed dead for both `curl` *and* the
   WebFetch tool (2026-07-09). Only usable by hand-download. Treat as unavailable.

## The OCR pipeline (`pipeline/ocr_extract.py`) — new 2026-07-09

Gutenberg text is clean enough for a bespoke regex parser in `chunk.py`. archive.org
OCR is **not** — verse text breaks across page-break footnote columns, running heads
are inconsistently mangled, apparatus is interleaved line-by-line. So OCR sources go
through an LLM extraction step first: `ocr_extract.py` slices the raw djvu.txt into
per-section blocks, sends each to **Opus** (`claude -p`, same cost-tracked/probe/budget
machinery as `distill.py`), and asks for ONLY the numbered verses — stitching split
lines, dropping footnotes/heads/page-numbers/introductions, keeping the translator's
wording + glosses. Output is a clean `data/raw/<name>.clean.json` that a trivial
`chunk.py` parser emits like any other source. A **canonical verse-count check** flags
anything the pass dropped or doubled (caught 3 off-by-ones on the Gāthās, fixed by
documented `zoro_fixups`). Cost for the 17 Gāthās: **$3.96**. **This generalizes** —
adding Sikhism (Macauliffe) is now: write a `slice_*` fn + prompt, reuse the rest.

---

## ✅ In the corpus (15 traditions, 5,097 passages)

| Tradition | Sources |
|---|---|
| Taoism | Tao Te Ching #216, Zhuangzi #59709 |
| Buddhism | Dhammapada #2017, **Diamond Sutra #64623** (Mahāyāna) |
| Stoicism | Meditations #2680, Enchiridion #45109 |
| Hebrew wisdom | Proverbs/Ecclesiastes (KJV #10), Pirkei Avot #8547 |
| Christianity | NT teaching chapters (KJV #10) |
| Hinduism | Bhagavad Gita #2388, Upanishads #3283 |
| Confucianism | Analects #3330, Mencius #10056 |
| Islam | Qur'an (Rodwell #3434), Rumi / Masnavi #45159 |
| Epicureanism | Letter to Menoeceus + Principal Doctrines (#57342) |
| Zoroastrianism | Gāthās (SBE 31, Mills — archive.org OCR, 239 v.) |
| **Ancient Egypt** | **Ptah-hotep + Ke'gemni #30508** (Gunn; the oldest wisdom, 57 v.) |
| **Bahá'í** | **Tablets of Abdul-Baha #19312** (Vol I; PD 1909–19, capped 175) |
| **Jainism** | **Uttarādhyayana** (SBE 45 pt.2, Jacobi — archive.org OCR, Lect. I–X) |
| **Sikhism** | **Ādi Granth** via Macauliffe Vol I (archive.org OCR — Japji + Nanak hymns) |
| **Mesopotamia** | **Babylonian & Assyrian Literature** (Wilson 1901 — archive.org OCR; hymns, penitential psalms, Sabitu songs) |

Bold = added 2026-07-10. **Six additions in one pass** (5 new traditions + a Mahāyāna
voice for Buddhism), on Alec's "breadth > depth — it's what makes *most shared ideas*
meaningful" steer. Result: the top shared idea now spans **10.5 effective traditions**
(was ~7.9). **Copyright note:** Bahá'í's authoritative *Hidden Words* (Shoghi Effendi
1929) is still under copyright — the Gutenberg *Tablets of Abdul-Baha* (1909–19) is the
PD substitute (like the Gospel-of-Thomas problem, solved by an older PD edition).

**Palette:** now **15 categorical colours** (`--c0..--c14`, validated both modes). New
tradition names re-sort alphabetically, so colours reassign positionally — the whole
15-set was re-picked, not appended. **This is at/over the categorical ceiling** (the
dataviz skill caps clean categorical at ~10–12); the residual CVD floor-band pairs are
covered by the always-on legend + hover + click (secondary encoding). **A 16th tradition
should NOT get a 16th hue** — instead deepen existing traditions (no palette cost), or
switch encoding (colour-by-lineage-family + shape, like `lineage.html`).

**Lineage:** `guru`/`jain`/`bahai` nodes already existed (adding them to the map closed
those orphans). Added two NEW nodes — `egypt` (new `egyptian` family) and `mesopotamia`
(`semitic`, ← proto-Semitic) — both feeding `hebrewbible` by influence. Affinities then
"found" it: **Ancient Egypt ↔ Hebrew wisdom 2.28×** (the Amenemope→Proverbs link),
Buddhism ↔ Jainism 1.50 (śramaṇa), Bahá'í ↔ Mesopotamia 2.71 (devotional/prayer).

---

## ⏳ Deferred / notes

All of the previously-deferred traditions are now **in the corpus**. Remaining ideas
live in the candidate lists below. Sourcing recipes proven this round:
- **Gutenberg** for clean text (Ptahhotep #30508, Diamond Sutra #64623, Bahá'í #19312).
- **archive.org OCR** via `ocr_extract.py` for Sikhism (`in.ernet.dli.2015.85504`),
  Jainism (`1922707.0045.002.umich.edu`), Mesopotamia (`babylonianandnas0000epip`).
  Each is a `slice_*` fn + Opus prompt + a balance cap; the "passages" shape (vs the
  Gathas' verse-count-checked shape) handles messier texts.

---

## 💡 Candidates to deepen existing traditions (not yet attempted)

All plausibly on Gutenberg (Legge/PD); would keep the corpus balanced without new
palette work since they map to existing traditions.

**Deepening existing traditions is now the preferred way to grow** (breadth is well
covered at 15, and no new palette slot is needed). All plausibly on Gutenberg (Legge/PD).

| Tradition | Candidate text | Note |
|---|---|---|
| Confucianism | Doctrine of the Mean, Great Learning | Legge; short, canonical |
| ~~Buddhism~~ | ~~Diamond Sutra (Mahāyāna)~~ | ✅ done 2026-07-10 (#64623); could still add Heart Sūtra / Sutta Nipāta |
| Islam | more of Rumi (Redhouse *Mesnevi* Bk I #61724; Divan #57068) | #45159 was the Davis selection |
| Hinduism | more Upanishads; Yoga Sutras (#2526) | Gita + 3 Upanishads today |
| Stoicism | Seneca's *Letters* / *On the Shortness of Life* | adds a third Stoic voice |
| Jainism | more Uttarādhyayana (Lect. XI–XXXVI) + Sūtrakṛtāṅga | only Lect. I–X taken |
| Sikhism | more of Macauliffe (later Gurus' hymns) | only Vol I / Nanak taken |

## 💡 Whole new traditions (each would need a 16th palette slot — AVOID, see palette note above)

| Tradition | Text | Sourcing note |
|---|---|---|
| ~~Zoroastrianism~~ | ~~Gāthās~~ | ✅ done |
| ~~Sikhism~~ | ~~Ādi Granth~~ | ✅ done — Macauliffe Vol I |
| ~~Jainism~~ | ~~Uttarādhyayana~~ | ✅ done — SBE 45 |
| ~~Ancient Egypt~~ | ~~Ptahhotep~~ | ✅ done — Gutenberg #30508 |
| ~~Mesopotamia~~ | ~~Babylonian hymns/psalms~~ | ✅ done — Wilson 1901 |
| ~~Bahá'í~~ | ~~Tablets of Abdul-Baha~~ | ✅ done — Gutenberg #19312 (Hidden Words is copyrighted) |
| Hermeticism | Corpus Hermeticum (Mead) | likely Gutenberg/archive — but no palette room left |
| Shinto | Kojiki / Nihon Shoki | lineage nodes exist, but they're myth/chronicle, weak "wisdom" fit |

---

## How to add a text (checklist)

1. Find it (gutendex first; archive.org if not). Add the id to `pipeline/fetch.sh`
   (Gutenberg loop, or the archive.org `spec` list — that resolves the real djvu.txt
   name via the metadata API); `./pipeline/fetch.sh` downloads to `data/raw/`.
2. **Clean Gutenberg text:** write a `def <name>(records)` parser in `chunk.py`
   (structure is bespoke — inspect the raw first); add it to `main()`'s tuple.
   **OCR scan:** instead write a `slice_*` fn + Opus prompt in `pipeline/ocr_extract.py`,
   run it (probe first — reports cost), then a trivial `chunk.py` parser that emits its
   `.clean.json`. Either way run `python3 pipeline/chunk.py` and spot-check.
3. Rebuild: `distill.py` (Opus, **WORKERS=2** — 4 rate-limits), then
   `uv run embed_project.py` → `embed_search.py` → `ideas.py`.
4. New tradition? Add a **validated** palette slot (dataviz `validate_palette.js`,
   both modes — new tradition sorts into `data.traditions` alphabetically and takes
   that index's `--c<i>`; add `--c<i>` to all 5 map pages' light+dark `:root`) and,
   if not already present, a `lineage.html` node (+ IDEAS/WHY/DETAIL/SRC entries,
   verified Wikipedia SRC link). Update hardcoded counts in `methodology.html` +
   the footer attribution.
5. Screenshot-verify all views **light + dark**; commit **explicit paths** (never
   `git add -A` — Alec keeps WIP in the tree).
