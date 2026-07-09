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

## ✅ In the corpus (10 traditions, 4,380 passages)

| Tradition | Sources (Gutenberg #) |
|---|---|
| Taoism | Tao Te Ching #216, **Zhuangzi** #59709 (Inner Ch. I–VII) |
| Buddhism | Dhammapada #2017 |
| Stoicism | Meditations #2680, Enchiridion #45109 |
| Hebrew wisdom | Proverbs/Ecclesiastes (KJV #10), **Pirkei Avot** #8547 |
| Christianity | NT teaching chapters (KJV #10) |
| Hinduism | Bhagavad Gita #2388, Upanishads #3283 |
| Confucianism | Analects #3330, **Mencius** #10056 |
| Islam | Qur'an (Rodwell #3434), **Rumi / Masnavi** #45159 |
| Epicureanism | Letter to Menoeceus + Principal Doctrines (#57342) |
| **Zoroastrianism** | **Gāthās** (SBE 31, Mills — archive.org `in.ernet.dli.2015.110222`, 239 v.) |

Bold = added 2026-07-09. Zoroastrianism is the **10th tradition** and the first
**archive.org / OCR** source (all others are Gutenberg) → it needed a validated
10th palette slot: `--c9` = `#b02d8f` light / `#d45cae` dark (**magenta**), which
passes dataviz `validate_palette.js` in both modes. Zoroastrianism sorts last
alphabetically so it takes index 9; no existing tradition's colour shifted. In the
map it forms its own tight cluster; affinities put it closest to Islam/Hebrew/
Christian (the Abrahamic side — matching the Avesta→Hebrew-Bible influence edge in
`lineage.html`, where the `avesta` node already existed).

---

## ⏳ Deferred — wanted, but not cleanly sourceable yet

~~Zoroastrianism~~ ✅ **done 2026-07-09** (see above — first OCR source, proved the
`ocr_extract.py` pipeline). **Sikhism is now the obvious next**: the OCR pipeline
exists, so it's no longer blocked on tooling — only on writing a `slice_*`/prompt for
Macauliffe. It's **already a node in `lineage.html`** (`guru`, the Ādi Granth) but
absent from the map, so it closes the same kind of inconsistency Zoroastrianism did.
It would be the **11th tradition** → needs a validated 11th palette slot `--c10`
(run dataviz `validate_palette.js`; the wheel is crowded at 10 — budget time for this).

### Sikhism — Ādi Granth / Japji Sahib
- **Gutenberg:** ❌ not found — searched `sikh`, `sikhism`, `granth`, `adi granth`,
  `macauliffe` (nothing).
- **sacred-texts:** `/skh/` exists but 403s.
- **archive.org leads (untried):** Macauliffe, **The Sikh Religion** (1909, PD) —
  `TheSikhReligionVolVI`, `in.ernet.dli.2015.45273` (Vol 5),
  `in.ernet.dli.2015.214766` (Vol III), `in.gov.ignca.13815` (Vol 4). Vol I holds
  the Japji. **Care:** Macauliffe interleaves translation with heavy biographical
  commentary — the `slice_*` fn must find the hymn blocks, and the Opus prompt must
  reject the surrounding prose (the Gāthās had cleaner per-section headers).

---

## 💡 Candidates to deepen existing traditions (not yet attempted)

All plausibly on Gutenberg (Legge/PD); would keep the corpus balanced without new
palette work since they map to existing traditions.

| Tradition | Candidate text | Note |
|---|---|---|
| Confucianism | Doctrine of the Mean, Great Learning | Legge; short, canonical |
| Buddhism | Sutta Nipata; Heart / Diamond Sutra (Mahāyāna) | broadens beyond the Dhammapada |
| Islam | more of Rumi (Redhouse *Mesnevi* Bk I #61724; Divan #57068) | #45159 was the Davis selection |
| Hinduism | more Upanishads; Yoga Sutras | Gita + 3 Upanishads today |
| Stoicism | Seneca's *Letters* / *On the Shortness of Life* | adds a third Stoic voice |

## 💡 Whole new traditions (would each need a palette slot + lineage already has some)

| Tradition | Text | Sourcing note |
|---|---|---|
| ~~Zoroastrianism~~ | ~~Gāthās~~ | ✅ done — in corpus |
| Sikhism | Ādi Granth | see Deferred above — OCR pipeline ready |
| Jainism | Jain Āgamas / Tattvartha Sutra | check Gutenberg/archive; PD translations thin |
| Ancient Egypt | Instruction of Ptahhotep | PD translations exist; short |
| Mesopotamia | Epic of Gilgamesh (wisdom passages) | OCR/older translations |
| Hermeticism | Corpus Hermeticum (Mead) | likely Gutenberg/archive |
| Bahá'í | Hidden Words | short; already a lineage node |

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
