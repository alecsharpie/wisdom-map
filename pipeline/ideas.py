# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = [
#   "scikit-learn>=1.4",
#   "numpy",
# ]
# ///
"""Cluster the passage embeddings into named ideas -> site/ideas.json

The higher-level view: k-means over the same blended (gist + text) embeddings
the map uses, one short Haiku-written name per cluster, and a per-cluster
tradition composition so you can see which ideas are shared and which are
unique. Labels are cached in data/idea_labels.json by cluster content, so
re-runs cost nothing unless clusters change.

Run AFTER embed_project.py (it reuses the cached embeddings and the map's
x/y): uv run pipeline/ideas.py
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = "BAAI/bge-large-en-v1.5"   # must match embed_project.py
GIST_WEIGHT = 0.65                 # must match embed_project.py
K = 60
SEED = 42
LLM = "haiku"
BUDGET_USD = 1.0
LABEL_BATCH = 15  # clusters per claude call
SAMPLES = 12      # gists shown per cluster

PROMPT = """You will get numbered clusters of short gists of passages from world wisdom \
texts. For each cluster, name the single idea its passages share. Reply with ONLY a JSON \
array like [{"c":<cluster id>,"label":"...","desc":"..."}] where label is the idea in \
3-5 plain modern English words (no tradition names, no archaic words), and desc is one \
plain sentence stating the idea itself (not "these passages discuss..."). Every cluster \
id in the input must appear exactly once."""


def cached_embeddings(texts: list[str]) -> np.ndarray:
    key = hashlib.sha256((MODEL + "\0" + "\0".join(texts)).encode()).hexdigest()[:16]
    cache = ROOT / "data" / f"embeddings-{key}.npy"
    if not cache.exists():
        sys.exit(f"missing {cache.name} — run embed_project.py first")
    return np.load(cache)


def label_clusters(payloads: dict[int, str]) -> dict[int, dict]:
    """payloads: cluster id -> newline-joined sample gists. Returns id -> {label, desc}."""
    cache_path = ROOT / "data" / "idea_labels.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    keys = {c: hashlib.sha1(s.encode()).hexdigest()[:16] for c, s in payloads.items()}
    todo = [c for c in payloads if keys[c] not in cache]
    total = 0.0
    for i in range(0, len(todo), LABEL_BATCH):
        batch = todo[i : i + LABEL_BATCH]
        blob = "\n\n".join(f"CLUSTER {c}:\n{payloads[c]}" for c in batch)
        r = subprocess.run(
            ["claude", "-p", "--model", LLM, "--output-format", "json", PROMPT],
            input=blob, capture_output=True, text=True, timeout=600,
        )
        doc = json.loads(r.stdout)
        total += doc.get("total_cost_usd") or 0
        m = re.search(r"\[.*\]", doc["result"], re.S)
        for row in json.loads(m.group(0)):
            c = int(row["c"])
            if c in payloads:
                cache[keys[c]] = {"label": row["label"], "desc": row["desc"]}
        print(f"labelled {min(i + LABEL_BATCH, len(todo))}/{len(todo)} clusters, ${total:.2f}")
        if total > BUDGET_USD:
            sys.exit(f"over label budget (${total:.2f} > ${BUDGET_USD}) — stopping")
    if todo:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
        print(f"label cost this run: ${total:.4f}")
    return {c: cache[k] for c, k in keys.items() if k in cache}


def relax(xy: np.ndarray, r: np.ndarray, steps: int = 300) -> np.ndarray:
    """Push overlapping bubbles apart, gently, keeping the layout's shape."""
    xy = xy.copy()
    for _ in range(steps):
        moved = False
        for i in range(len(xy)):
            for j in range(i + 1, len(xy)):
                d = xy[j] - xy[i]
                dist = float(np.hypot(*d)) or 1e-6
                overlap = r[i] + r[j] - dist
                if overlap > 0:
                    push = d / dist * overlap * 0.35
                    xy[i] -= push
                    xy[j] += push
                    moved = True
        if not moved:
            break
    return xy


def main():
    passages = json.loads((ROOT / "data" / "passages.json").read_text())
    site = json.loads((ROOT / "site" / "data.json").read_text())
    assert len(site["passages"]) == len(passages), "site/data.json is stale — rerun embed_project.py"
    gists_by_key = json.loads((ROOT / "data" / "gists.json").read_text())
    gists = [
        gists_by_key.get(hashlib.sha1(p["text"].encode()).hexdigest()[:16], p["text"])
        for p in passages
    ]
    text_emb = cached_embeddings([p["text"] for p in passages])
    gist_emb = cached_embeddings(gists)
    emb = GIST_WEIGHT * gist_emb + (1 - GIST_WEIGHT) * text_emb
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)

    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=K, random_state=SEED, n_init=10).fit(emb)
    labels, centers = km.labels_, km.cluster_centers_
    centers /= np.linalg.norm(centers, axis=1, keepdims=True)
    centrality = (emb * centers[labels]).sum(axis=1)  # cosine to own centroid

    traditions = site["traditions"]
    t_idx = {t: i for i, t in enumerate(traditions)}
    xy = np.array([[p["x"], p["y"]] for p in site["passages"]])

    clusters = []
    payloads = {}
    for c in range(K):
        idx = np.where(labels == c)[0]
        order = idx[np.argsort(-centrality[idx])]
        counts = [0] * len(traditions)
        for i in idx:
            counts[t_idx[passages[i]["tradition"]]] += 1
        shares = np.array(counts) / len(idx)
        nz = shares[shares > 0]
        eff = float(np.exp(-(nz * np.log(nz)).sum()))  # effective #traditions
        payloads[c] = "\n".join(f"- {gists[i][:160]}" for i in order[:SAMPLES])
        clusters.append({
            "id": c,
            "n": int(len(idx)),
            "x": float(xy[idx, 0].mean()),
            "y": float(xy[idx, 1].mean()),
            "counts": counts,
            "eff": round(eff, 2),
            "ids": [int(i) for i in order],
        })

    named = label_clusters(payloads)
    for cl in clusters:
        meta = named.get(cl["id"], {"label": f"cluster {cl['id']}", "desc": ""})
        cl["label"], cl["desc"] = meta["label"], meta["desc"]

    # non-overlapping bubble layout seeded from the map's own geography
    pos = np.array([[c["x"], c["y"]] for c in clusters])
    n = np.array([c["n"] for c in clusters], dtype=float)
    r = np.sqrt(n)
    r *= np.sqrt(0.22 / (np.pi * (r ** 2).sum()))  # bubbles fill ~22% of unit square
    pos = relax(pos, r * 1.06)
    pos -= pos.min(axis=0)
    pos /= pos.max(axis=0)
    for cl, (x, y), ri in zip(clusters, pos, r):
        cl["x"], cl["y"], cl["r"] = round(float(x), 4), round(float(y), 4), round(float(ri), 4)

    out = {"traditions": traditions, "clusters": clusters}
    dest = ROOT / "site" / "ideas.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {dest} ({dest.stat().st_size / 1e3:.0f} kB)")
    for cl in sorted(clusters, key=lambda c: -c["eff"])[:8]:
        top = ", ".join(f"{traditions[i]} {c}" for i, c in enumerate(cl["counts"]) if c)
        print(f"eff {cl['eff']:4.1f} · {cl['label']:40s} ({cl['n']}) {top}")


if __name__ == "__main__":
    main()
