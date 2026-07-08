# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#   "sentence-transformers>=3.0",
#   "umap-learn>=0.5.6",
#   "numpy",
# ]
# ///
"""Embed passages, project to 2D with UMAP, precompute neighbours.

Each passage is embedded as a blend of its LLM-distilled gist (the idea, in
plain modern English — see distill.py) and its original text, so clustering
follows meaning rather than shared vocabulary.

data/passages.json + data/gists.json -> data/embeddings-*.npy (cached) -> site/data.json
Run with: uv run pipeline/embed_project.py
"""

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = "BAAI/bge-large-en-v1.5"
K = 10  # neighbours per passage
SEED = 42
GIST_WEIGHT = 0.65  # rest is the original text


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
    n_gists = sum(1 for g, p in zip(gists, passages) if g != p["text"])
    print(f"{n_gists}/{len(passages)} passages have gists")

    text_emb = embeddings_for([p["text"] for p in passages])
    gist_emb = embeddings_for(gists)
    emb = GIST_WEIGHT * gist_emb + (1 - GIST_WEIGHT) * text_emb
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    print(f"{len(passages)} passages, embeddings {emb.shape}")

    import umap

    xy = umap.UMAP(
        n_neighbors=25, min_dist=0.08, metric="cosine", random_state=SEED
    ).fit_transform(emb)
    # normalize to [0, 1] for the frontend
    xy = (xy - xy.min(axis=0)) / (xy.max(axis=0) - xy.min(axis=0))

    # top-K cosine neighbours (embeddings are normalized -> dot product)
    sims = emb @ emb.T
    np.fill_diagonal(sims, -np.inf)
    top = np.argpartition(-sims, K, axis=1)[:, :K]

    traditions = sorted({p["tradition"] for p in passages})
    sources = sorted({p["source"] for p in passages})
    t_idx = {t: i for i, t in enumerate(traditions)}
    s_idx = {s: i for i, s in enumerate(sources)}

    out = []
    for i, p in enumerate(passages):
        nb = sorted(top[i].tolist(), key=lambda j: -sims[i, j])
        # resonance: how many distinct *other* traditions among neighbours
        other = {passages[j]["tradition"] for j in nb} - {p["tradition"]}
        gist = gists[i] if gists[i] != p["text"] else None
        out.append({
            **({"g": gist} if gist else {}),
            "t": t_idx[p["tradition"]],
            "s": s_idx[p["source"]],
            "ref": p["ref"],
            "text": p["text"],
            "x": round(float(xy[i, 0]), 4),
            "y": round(float(xy[i, 1]), 4),
            "nb": [[j, round(float(sims[i, j]), 3)] for j in nb],
            "r": len(other),
        })

    data = {"model": MODEL, "traditions": traditions, "sources": sources, "passages": out}
    dest = ROOT / "site" / "data.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {dest} ({dest.stat().st_size / 1e6:.1f} MB)")

    res = sorted(out, key=lambda p: -p["r"])[:3]
    for p in res:
        print(f"\nresonance {p['r']}: [{p['ref']}] {p['text'][:110]}")


if __name__ == "__main__":
    main()
