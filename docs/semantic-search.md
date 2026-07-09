# Ask the Ages — a semantic search box over the corpus

**Status: built 2026-07-09 — search box on `site/index.html`, corpus matrix
from `pipeline/embed_search.py` (`site/search.bin`, int8, 1.4 MB). Zero
marginal cost per query — the model runs in the visitor's browser.**

## What it is

A search box on the map: type a modern sentence — *"how do I deal with a
difficult coworker"*, *"I'm afraid of dying"*, *"is ambition bad?"* — and the
map lights up with the passages closest in meaning, showing which traditions
were already there, millennia ago. This is the single most direct way to
deliver the project's thesis to someone who won't pan around a scatter plot:
your question is old, and it has many answers.

## How it works

The corpus side is already done — every passage has a 1024-d embedding. The
challenge is embedding the *query* without a server:

1. **In-browser model (recommended).** Run a small sentence-embedding model
   with `transformers.js` (ONNX, WebGPU/WASM). The catch: the corpus is
   embedded with `bge-large` (1024-d, too big to ship comfortably), and
   queries must live in the *same* space as documents. The clean fix is a
   **two-tower trick**: re-embed all 3,635 passages once with a small model
   (`bge-small-en-v1.5`, 384-d, ~34 MB ONNX quantised, one free pipeline run)
   and ship those as a second matrix (3,635 × 384 float16 ≈ 2.8 MB). Queries
   and passages then share the small model's space. Search quality drops only
   slightly from bge-large, and only for search — the map itself stays on
   bge-large.
2. Embed the query with the same "Represent this sentence…" query prefix
   bge models expect, cosine against the matrix (a 3,635 × 384 matmul is
   instant in JS), take the top ~20.
3. Model files are fetched from the Hugging Face CDN on first use (with a
   loading indicator) and cached by the browser thereafter. Note: this is the
   one feature that breaks the "fully static, no external requests" property —
   worth a small "download 34 MB model?" consent moment.

Alternative rejected: a tiny embedding API (server) — recurring cost and ops
for a hobby page; against the grain of a static site.

## UI sketch

- A search field top-centre of the map. On submit: matching dots stay at full
  opacity and gain a halo, everything else dims; a results panel lists the
  top passages grouped by tradition, each row showing source · ref · gist,
  clicking a row selects that dot (existing `#p<id>` machinery).
- The empty state can carry three example queries as clickable chips —
  "fear of death", "dealing with anger", "does wealth matter" — so visitors
  understand instantly what the box does.
- Show the *spread*: "closest answers come from 6 traditions" — reusing the
  resonance framing.

## Cost

- Pipeline: one local `bge-small` embedding run (free, minutes).
- Site: +2.8 MB data file; model downloaded client-side from HF's CDN.
- $0 LLM. $0 per query. No server.

## Open questions

- float16 vs int8 quantisation of the passage matrix (int8 halves it again;
  quality loss likely invisible at this scale).
- Whether to also search the *gists* (they're in `data.json` already) and
  blend scores, mirroring the 0.65/0.35 blend used for the map.
- Mobile: WASM fallback speed is fine for one query embed (~100 ms), but the
  34 MB download wants wifi — the consent prompt matters there.
