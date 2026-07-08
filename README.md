# Wisdom Map

An interactive map of the ideas humans keep arriving at independently.
3,635 passages from public-domain wisdom texts across nine traditions are
embedded and projected to 2D — passages that mean similar things sit close
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

## Sources (all via Project Gutenberg)

| Tradition | Text | Translation |
|---|---|---|
| Taoism | Tao Te Ching | James Legge |
| Buddhism | Dhammapada | F. Max Müller |
| Stoicism | Meditations | Meric Casaubon |
| Stoicism | Enchiridion | T. W. Higginson |
| Hebrew wisdom | Proverbs, Ecclesiastes | KJV |
| Christianity | NT teaching chapters: Matt 5–7, 13, 18, 25; Luke 6, 12, 14–16; John 13–15; Rom 12; 1 Cor 13; James | KJV |
| Hinduism | Bhagavad Gita | Edwin Arnold |
| Hinduism | Upanishads (Isa, Katha, Kena) | Swami Paramananda |
| Confucianism | Analects | James Legge |
| Islam | Quran — the shorter (chiefly Meccan) suras plus the Night Journey, Luqman, Yā-Sīn, the Merciful, and the Kingdom | J. M. Rodwell |
| Epicureanism | Letter to Menoeceus, Principal Doctrines | C. D. Yonge (Diogenes Laertius X) |

(The Gospel of Thomas from the original notes was dropped — the ancient text
is public domain but every complete English translation is modern and
copyrighted. The Sermon on the Mount and the Enchiridion stand in.)

## Three views

- **The map** (`site/index.html`) — the embedding scatter described above.
- **The ideas** (`site/ideas.html`) — the higher-level view: the same embeddings
  k-means-clustered into 60 named ideas. Each idea is a bubble sized by passage
  count whose ring shows which traditions arrive at it; a "most shared ideas"
  list ranks ideas by how evenly they spread across traditions (effective number
  of traditions). Click a bubble for its composition and passages, grouped by
  tradition. Cluster names are Haiku one-liners (`pipeline/ideas.py`, cached in
  `data/idea_labels.json`).
- **The lineage** (`site/lineage.html`) — a *family tree of scripture*: ~30 major
  religious texts and traditions placed left-to-right by date and coloured by the
  language they were composed in (Semitic, Hellenic, Indo-Aryan, Iranian, Sinitic…).
  Solid lines are descent, dashed lines are cross-branch influence. Hover a node to
  trace its ancestry; click for language, place of origin, date, and parents/children.
  It's a hand-built, self-contained SVG (no data pipeline) — the data lives inline in
  the file. The two pages link to each other from the header.

## Run it

The site is fully static; `site/data.json` is precomputed.

```sh
cd site && python3 -m http.server 8643
# map:     http://localhost:8643/
# lineage: http://localhost:8643/lineage.html
```

Deep-link a passage with `#p<id>` (e.g. `/#p102`), or a lineage node by id
(e.g. `lineage.html#quran`).

## Rebuild the data

```sh
pipeline/fetch.sh                    # download raw texts -> data/raw/
python3 pipeline/chunk.py            # parse + chunk      -> data/passages.json
python3 pipeline/distill.py          # LLM gists          -> data/gists.json
uv run pipeline/embed_project.py     # embed + UMAP       -> site/data.json
uv run pipeline/ideas.py             # cluster + label    -> site/ideas.json
```

The distill step calls `claude -p` (Haiku) in 60-passage batches; it tracks and
prints total cost (~$3.50 for the full corpus), caches per passage, and stops
if a probe batch projects past its budget. The embed step is a self-contained
uv script (sentence-transformers `BAAI/bge-large-en-v1.5`, UMAP with a fixed
seed); embeddings are cached in `data/` keyed by content hash, so re-runs are
fast.

Each passage in `data.json` carries its top-10 cosine neighbours and a
**resonance** score: how many *other* traditions appear among those
neighbours.

## Ideas not built yet

Each has a short project description in `docs/`:

- [Ask the Ages](docs/semantic-search.md) — type a modern sentence, see which
  traditions were already there (in-browser embedding model, no server).
- [The Affinities](docs/affinity-matrix.md) — a 9×9 heatmap of which
  traditions echo each other most (free — derived from existing neighbours).
- [The Distinctives](docs/divergence-view.md) — the inverse of the ideas view:
  what each tradition says that no one else does.
- More traditions: Rumi, Zhuangzi, Pirkei Avot, Seneca's letters…

*Interpretive, not authoritative — a curiosity, not a theological claim.*
