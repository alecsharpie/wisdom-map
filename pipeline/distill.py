"""Distill each passage into a plain modern-English gist via `claude -p` (Haiku).

The gist is what gets embedded (blended with the original), so passages cluster
by idea rather than by vocabulary. Gists are cached in data/gists.json keyed by
a hash of the passage text; re-runs only pay for new/changed passages.

Cost: every claude call reports cost via --output-format json; we sum and print
it. A probe batch runs first and the projected total must stay under BUDGET.

Usage: python3 pipeline/distill.py [--probe-only]
"""

import hashlib
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = ROOT / "data" / "gists.json"
BATCH = 60
WORKERS = 4
MODEL = "haiku"
BUDGET_USD = 5.0

PROMPT = (
    "For each passage in the JSON array on stdin, distill its core idea into one plain "
    "modern-English sentence (two only if it genuinely contains two distinct ideas). "
    'Drop speaker framing ("The Master said", "Krishna spake"), archaic wording, and '
    "metaphor vehicles - state the underlying claim directly, as a general truth. "
    'Reply with ONLY a JSON array: [{"id":<id>,"gist":"..."},...]'
)


def key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def run_batch(batch):
    """batch: list of (key, text). Returns (cost_usd, {key: gist})."""
    payload = json.dumps([{"id": i, "text": t} for i, (_, t) in enumerate(batch)])
    proc = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--output-format", "json", PROMPT],
        input=payload, capture_output=True, text=True, timeout=600,
    )
    doc = json.loads(proc.stdout)
    cost = float(doc.get("total_cost_usd") or 0)
    m = re.search(r"\[.*\]", doc.get("result", ""), re.S)
    items = json.loads(m.group(0)) if m else []
    out = {}
    for item in items:
        i = item.get("id")
        gist = (item.get("gist") or "").strip()
        if isinstance(i, int) and 0 <= i < len(batch) and gist:
            out[batch[i][0]] = gist
    return cost, out


def main():
    passages = json.loads((ROOT / "data" / "passages.json").read_text())
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}

    todo = {key(p["text"]): p["text"] for p in passages}
    misses = [(k, t) for k, t in todo.items() if k not in cache]
    print(f"{len(passages)} passages, {len(todo) - len(misses)} cached, {len(misses)} to distill")
    if not misses:
        return

    batches = [misses[i : i + BATCH] for i in range(0, len(misses), BATCH)]
    lock = Lock()
    total_cost = 0.0
    done = 0

    # probe: run one batch, project the total, stop if it would bust the budget
    cost, gists = run_batch(batches[0])
    cache.update(gists)
    CACHE_PATH.write_text(json.dumps(cache))
    total_cost += cost
    projected = cost * len(batches)
    print(f"probe: ${cost:.4f} for {len(gists)}/{len(batches[0])} gists"
          f" -> projected total ${projected:.2f} over {len(batches)} batches")
    if "--probe-only" in sys.argv:
        return
    if projected > BUDGET_USD:
        print(f"projected cost exceeds ${BUDGET_USD:.2f} budget - stopping. "
              f"Raise BUDGET_USD to continue.")
        sys.exit(2)

    def work(batch):
        nonlocal total_cost, done
        try:
            cost, gists = run_batch(batch)
        except Exception as e:
            print(f"batch failed ({e}); skipping", file=sys.stderr)
            return
        with lock:
            total_cost += cost
            done += 1
            cache.update(gists)
            CACHE_PATH.write_text(json.dumps(cache))
            print(f"[{done + 1}/{len(batches)}] +{len(gists)} gists, total ${total_cost:.2f}")

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(work, batches[1:]))

    missing = sum(1 for k in todo if k not in cache)
    print(f"\ndone: {len(cache)} gists cached, {missing} passages without a gist "
          f"(will embed raw text), TOTAL COST ${total_cost:.2f}")


if __name__ == "__main__":
    main()
