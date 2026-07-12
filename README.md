# Wisdom Map

**Live site → https://www.alecsharpie.me/wisdom-map/**

An interactive map of the ideas humans keep arriving at independently.
**5,097 passages** from public-domain wisdom texts across **15 traditions**
are embedded and projected to 2D — passages that mean similar things sit close
together, *whatever tradition they came from*.

To cluster by **idea rather than vocabulary**, each passage is first distilled
by an LLM into a one-sentence plain-modern-English gist ("No man can serve two
masters…" → *"You cannot fully commit to two opposing value systems at
once"*), and the embedding blends gist (65%) with original text (35%). Without
this, embeddings latch onto surface words — every "The Master said…" clusters
with every other one.

Click a dot and the map draws threads to its nearest echoes in other
traditions: a Taoist line, a Confucian line, and a verse from Proverbs landing
on top of each other.

*Interpretive, not authoritative — a curiosity, not a theological claim.*

## The views

| | |
|---|---|
| **The map** (`index.html`) | The embedding scatter. Carries **Ask the Ages** — a search box that embeds your question *in the browser* (transformers.js + bge-small, model fetched once from Hugging Face behind a consent prompt) and lights up the closest passages. No server, $0 per query. |
| **The ideas** (`ideas.html`) | The same embeddings k-means-clustered into 60 named ideas. Each is a bubble sized by passage count whose ring shows which traditions arrive at it. |
| **Most shared** (`most-shared.html`) | Ideas ranked by how evenly they spread across traditions (effective number of traditions). The most universal idea now spans ~10.5 effective traditions. |
| **The affinities** (`affinities.html`) | A 15×15 heatmap of which traditions echo each other most, as observed-vs-expected neighbour lift (1.0 = chance). It "finds" the real lineages — e.g. Ancient Egypt ↔ Hebrew wisdom (Amenemope → Proverbs). |
| **The distinctives** (`distinctives.html`) | The inverse: what each tradition says that the others here don't, ranked by purity × lift, plus each tradition's *island* share. |
| **The lineage** (`lineage.html`) | A hand-built *family tree of scripture*: ~30 texts placed left-to-right by date, coloured by the language they were composed in. Solid lines are descent, dashed lines cross-branch influence. |
| **The corpus** (`corpus.html`) | The full text of every passage, browsable — the raw material, for trust. |
| **How it's made** (`methodology.html`) | The full pipeline and per-view maths, with diagrams. |

Deep-link a passage with `#p<id>` (e.g. `/#p102`), or a lineage node by id
(e.g. `lineage.html#quran`).

## Sources

All translations are public domain, via Project Gutenberg and archive.org.

| Tradition | Texts (passages) |
|---|---|
| Stoicism | Meditations · Enchiridion |
| Hebrew wisdom | Proverbs · Ecclesiastes · Pirkei Avot |
| Confucianism | Analects · Mencius |
| Islam | Quran (chiefly Meccan suras) · Rumi |
| Buddhism | Dhammapada · Diamond Sutra |
| Hinduism | Bhagavad Gita · Upanishads (Isa, Katha, Kena) |
| Taoism | Zhuangzi (Inner Chapters) · Tao Te Ching |
| Christianity | NT teaching chapters (Matt, Luke, John, Romans, 1 Cor, James) |
| Zoroastrianism | Gāthās |
| Jainism | Uttarādhyayana |
| Bahá'í | Tablets of Abdul-Baha |
| Sikhism | Adi Granth (Macauliffe) |
| Mesopotamia | Babylonian & Assyrian hymns and psalms |
| Ancient Egypt | Maxims of Ptah-hotep · Instruction of Ke'gemni |
| Epicureanism | Letter to Menoeceus · Principal Doctrines |

(The Gospel of Thomas from the original notes was dropped — the ancient text
is public domain but every complete English translation is modern and
copyrighted. The Sermon on the Mount and the Enchiridion stand in.)

## Run it locally

The site is fully static; everything under `site/` is precomputed.

```sh
cd site && python3 -m http.server 8643
# then open http://localhost:8643/
```

(The search box is the one feature that isn't fully offline — it fetches the
embedding model from Hugging Face's CDN on first use, behind a consent prompt.)

## Rebuild the data

```sh
pipeline/fetch.sh                    # download raw texts -> data/raw/
python3 pipeline/chunk.py            # parse + chunk      -> data/passages.json
python3 pipeline/distill.py          # LLM gists          -> data/gists.json
uv run pipeline/embed_project.py     # embed + UMAP       -> site/data.json
uv run pipeline/ideas.py             # cluster + label    -> site/ideas.json
uv run pipeline/embed_search.py      # bge-small re-embed -> site/search.bin
```

The distill step calls `claude -p` (Opus) in 60-passage batches; it tracks and
prints total cost, caches per passage, and stops if a probe batch projects past
its budget. The embed step is a self-contained `uv` script
(sentence-transformers `BAAI/bge-large-en-v1.5`, UMAP with a fixed seed);
embeddings are cached by content hash, so re-runs are fast. Non-Gutenberg
scanned sources (the Gāthās, Uttarādhyayana, Adi Granth, Mesopotamian hymns)
are extracted from archive.org OCR by `pipeline/ocr_extract.py`.

Each passage in `data.json` carries its top-10 cosine neighbours and a
**resonance** score: how many *other* traditions appear among those neighbours.

## Deployment

The static `site/` directory is published to GitHub Pages by
`.github/workflows/pages.yml` on every push to `main`.
