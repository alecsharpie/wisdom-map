# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#   "sentence-transformers>=3.0",
#   "numpy",
# ]
# ///
"""Re-embed the corpus with bge-small for in-browser semantic search.

The map's bge-large space (1024d) is too big to ship, and a query embedded by
a different model can't be compared against it. So the search feature gets its
own space: every passage re-embedded once with bge-small-en-v1.5 (384d), whose
quantised ONNX build (~34 MB) runs in the visitor's browser via transformers.js.
Queries and passages then share one shippable space; the map stays on bge-large.

Same gist/text blend as the map (65/35) so search follows meaning, not archaic
vocabulary. Output is int8-quantised (per-vector scale) — ~1.4 MB on the wire.

Binary layout of site/search.bin (little-endian):
  4 bytes  magic "WMS1"
  uint32   N passages
  uint32   D dims
  N float32 per-vector dequant scales
  N*D int8  row-major quantised vectors (vec = int8 * scale)

data/passages.json + data/gists.json -> data/embeddings-*.npy (cached) -> site/search.bin
Run with: uv run pipeline/embed_search.py
"""

import hashlib
import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = "BAAI/bge-small-en-v1.5"
GIST_WEIGHT = 0.65  # rest is the original text (same blend as embed_project.py)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def embeddings_for(texts: list[str]) -> np.ndarray:
    key = hashlib.sha256((MODEL + "\0" + "\0".join(texts)).encode()).hexdigest()[:16]
    cache = ROOT / "data" / f"embeddings-{key}.npy"
    if cache.exists():
        print(f"using cached embeddings {cache.name}")
        return np.load(cache)
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL)
    emb = model.encode(texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
    np.save(cache, emb)
    return emb


def main():
    passages = json.loads((ROOT / "data" / "passages.json").read_text())
    gist_path = ROOT / "data" / "gists.json"
    gists_by_key = json.loads(gist_path.read_text()) if gist_path.exists() else {}
    gists = [
        gists_by_key.get(hashlib.sha1(p["text"].encode()).hexdigest()[:16], p["text"])
        for p in passages
    ]

    text_emb = embeddings_for([p["text"] for p in passages])
    gist_emb = embeddings_for(gists)
    emb = GIST_WEIGHT * gist_emb + (1 - GIST_WEIGHT) * text_emb
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    n, d = emb.shape
    print(f"{n} passages, embeddings {emb.shape}")

    # int8 quantise, one scale per vector
    scales = np.abs(emb).max(axis=1) / 127.0
    q = np.round(emb / scales[:, None]).clip(-127, 127).astype(np.int8)

    # quantisation quality: cosine between original and dequantised vectors
    deq = q.astype(np.float32) * scales[:, None]
    deq_n = deq / np.linalg.norm(deq, axis=1, keepdims=True)
    cos = (deq_n * emb).sum(axis=1)
    print(f"int8 round-trip cosine: min {cos.min():.5f}, mean {cos.mean():.5f}")

    dest = ROOT / "site" / "search.bin"
    with dest.open("wb") as f:
        f.write(b"WMS1")
        f.write(struct.pack("<II", n, d))
        f.write(scales.astype("<f4").tobytes())
        f.write(q.tobytes())
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.2f} MB)")

    # sanity: run a few modern queries through the same model + prefix,
    # score against the dequantised matrix exactly as the browser will
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL)
    queries = [
        "how do I deal with a difficult coworker",
        "I'm afraid of dying",
        "is ambition bad?",
    ]
    q_emb = model.encode(
        [QUERY_PREFIX + s for s in queries], normalize_embeddings=True
    )
    sims = q_emb @ deq.T
    for qi, query in enumerate(queries):
        print(f"\nquery: {query}")
        top = np.argsort(-sims[qi])[:5]
        trads = set()
        for j in top:
            p = passages[j]
            trads.add(p["tradition"])
            print(f"  {sims[qi, j]:.3f} [{p['tradition']} · {p['source']} {p['ref']}] "
                  f"{gists[j][:90]}")
        print(f"  -> {len(trads)} traditions in top 5")


if __name__ == "__main__":
    main()
