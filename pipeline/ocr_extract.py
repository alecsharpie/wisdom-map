"""Extract clean scripture verses from noisy archive.org OCR via `claude -p` (Opus).

Gutenberg texts are clean enough for a bespoke regex parser (see chunk.py). The
archive.org SBE scans are not: verse text is broken across page-break footnote
columns, running heads are inconsistently mangled ('YASNA XXVIIL', 'XXXT'), and
scholarly apparatus is interleaved line-by-line with the translation. Regex can't
stitch that back together; an LLM can.

This stage is the reusable OCR path. Per source it slices the raw djvu.txt into
per-section blocks, sends each to Opus asking for ONLY the numbered verses (drop
footnotes/heads/page-numbers/introductions, stitch verses split across breaks,
keep the translator's glosses and wording), and writes a clean intermediate JSON
that chunk.py consumes like any other source. Results cache by block-text hash.

Cost is reported via --output-format json, summed and printed; a probe block runs
first and the projected total must stay under BUDGET_USD.

Usage: python3 pipeline/ocr_extract.py [--probe-only]

Adding another OCR source later (e.g. Sikhism / Macauliffe): write a `slice_*`
function returning [(label, block_text)], add it to SOURCES, reuse everything else.
"""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE_PATH = ROOT / "data" / "ocr_cache.json"
MODEL = "opus"
BUDGET_USD = 10.0


def key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


# --- Zoroastrianism: the Gathas, SBE vol. 31 (Mills, 1887). --------------------
# The Gathas run from the first 'Translation.' header to 'THE YASNA.' (after which
# come the ordinary liturgical Yasnas + fragments — ritual, not wisdom, so cut).
# Each Gatha has exactly one 'Translation.' header right before its verses; two
# OCR'd as 'Translation,' / 'Translation. .'. The 17 Gathas appear in Mills's
# fixed print order (29 before 28, etc.):
ZORO_ORDER = [29, 28, 30, 31, 32, 33, 34, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53]
ZORO_GROUP = {  # the five Gatha collections, by Yasna number
    **{y: "Ahunavaiti Gatha" for y in (28, 29, 30, 31, 32, 33, 34)},
    **{y: "Ushtavaiti Gatha" for y in (43, 44, 45, 46)},
    **{y: "Spenta-mainyu Gatha" for y in (47, 48, 49, 50)},
    51: "Vohu-khshathra Gatha", 53: "Vahishtoishti Gatha",
}
# canonical verse counts, for a completeness sanity-check after extraction
ZORO_VERSES = {28: 11, 29: 11, 30: 11, 31: 22, 32: 16, 33: 14, 34: 15,
               43: 16, 44: 20, 45: 11, 46: 19, 47: 6, 48: 12, 49: 12, 50: 11,
               51: 22, 53: 9}

ZORO_PROMPT = (
    "The text on stdin is OCR'd from Sacred Books of the East vol. 31 (Mills, 1887), "
    "the English translation of a single Zoroastrian Gatha (one Yasna). It is noisy: "
    "the numbered verse translation is interrupted by footnote columns, running heads "
    "('YASNA XXIX.'), page numbers, and small-print scholarly apparatus, and a single "
    "verse may be split across those interruptions.\n\n"
    "Extract ONLY the numbered verses of the translation. Rules:\n"
    "- Return each numbered verse as one continuous passage, stitching together parts "
    "split across page/footnote breaks.\n"
    "- DROP every footnote and word-for-word alternate rendering (lines about "
    "manuscripts, Pahlavi, Haug, Spiegel, Justi, etc.), all running heads, page "
    "numbers, and any prose INTRODUCTION or argument about the hymn.\n"
    "- KEEP the translator's parenthetical glosses like '(O Ahura and Asha!)' and fold "
    "in speaker labels like 'Ahura speaks.' / 'Zarathustra.' before the verse they head.\n"
    "- Do NOT paraphrase, summarize, or modernize the translation's own wording; only "
    "repair obvious OCR garbling of real words.\n"
    "- If the block contains no genuine numbered scripture verse, return [].\n"
    'Reply with ONLY a JSON array: [{"verse":<int>,"text":"..."},...]'
)


def slice_zoroastrianism():
    """-> list of (yasna_number:int, block_text:str), one per Gatha, in print order."""
    body = raw_text = (RAW / "zoro_sbe31.txt").read_text(encoding="utf-8")
    lines = body.split("\n")
    heads = [i for i, ln in enumerate(lines)
             if re.match(r"^Translation[.,]", ln.strip())]
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "THE YASNA.")
    heads = [h for h in heads if h < end]
    if len(heads) != len(ZORO_ORDER):
        raise SystemExit(f"expected {len(ZORO_ORDER)} 'Translation.' headers, "
                         f"found {len(heads)} — OCR structure changed, re-inspect.")
    bounds = heads + [end]
    blocks = []
    for yasna, a, b in zip(ZORO_ORDER, bounds, bounds[1:]):
        blocks.append((yasna, "\n".join(lines[a:b])))
    return blocks


def zoro_fixups(per_yasna):
    """Repair the two artifacts the verse-count check + a spot-read surfaced.

    (1) Yasna 49's final verse prints just after Yasna 50's 'Translation.' header,
        so the slice put it at the head of the 50 block, numbered 12. Move it back:
        49 -> 12 verses, 50 -> 11, both then canonical.
    (2) Yasna 28 opens with an unnumbered liturgical prelude ('A Strengthening
        blessing...') that Opus numbered as verse 1, shifting the real 1-11 to 2-12.
        Relabel the prelude verse 0 and shift the rest back down by one.
    """
    y50 = per_yasna[50]
    stray = [v for v in y50 if v["verse"] == 12]
    if stray and len(y50) == 12 and len(per_yasna[49]) == 11:
        per_yasna[50] = [v for v in y50 if v["verse"] != 12]
        per_yasna[49] = per_yasna[49] + [stray[0]]

    y28 = per_yasna[28]
    if len(y28) == 12 and y28 and y28[0]["text"].lower().startswith(("(a strengthening",
                                                                     "a strengthening")):
        y28[0]["verse"] = 0
        for v in y28[1:]:
            v["verse"] -= 1
    return per_yasna


SOURCES = {
    "zoroastrianism": (slice_zoroastrianism, ZORO_PROMPT, ZORO_ORDER, ZORO_VERSES,
                       ZORO_GROUP),
}


def extract_block(prompt, block):
    """Returns (cost_usd, [{'verse':int,'text':str}, ...])."""
    proc = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--output-format", "json", prompt],
        input=block, capture_output=True, text=True, timeout=600,
    )
    doc = json.loads(proc.stdout)
    cost = float(doc.get("total_cost_usd") or 0)
    m = re.search(r"\[.*\]", doc.get("result", ""), re.S)
    items = json.loads(m.group(0)) if m else []
    verses = [{"verse": it["verse"], "text": " ".join(str(it["text"]).split())}
              for it in items if isinstance(it.get("verse"), int) and it.get("text")]
    return cost, verses


def run_source(name):
    slicer, prompt, order, verse_counts, group = SOURCES[name]
    blocks = slicer()
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    misses = [(lbl, b) for lbl, b in blocks if key(b) not in cache]
    print(f"[{name}] {len(blocks)} blocks, {len(blocks) - len(misses)} cached, "
          f"{len(misses)} to extract")

    total_cost = 0.0
    if misses:
        # probe the first uncached block, project, guard the budget
        lbl, block = misses[0]
        cost, verses = extract_block(prompt, block)
        cache[key(block)] = verses
        CACHE_PATH.write_text(json.dumps(cache))
        total_cost += cost
        projected = cost * len(misses)
        print(f"probe: Yasna {lbl}: ${cost:.4f}, {len(verses)} verses "
              f"(expect {verse_counts.get(lbl, '?')}) "
              f"-> projected ${projected:.2f} over {len(misses)} blocks")
        if "--probe-only" in sys.argv:
            return
        if projected > BUDGET_USD:
            raise SystemExit(f"projected ${projected:.2f} exceeds ${BUDGET_USD} "
                             f"budget — raise BUDGET_USD to continue.")
        for lbl, block in misses[1:]:
            cost, verses = extract_block(prompt, block)
            cache[key(block)] = verses
            CACHE_PATH.write_text(json.dumps(cache))
            total_cost += cost
            print(f"  Yasna {lbl}: +{len(verses)} verses "
                  f"(expect {verse_counts.get(lbl, '?')}), total ${total_cost:.2f}")

    # assemble clean output (per-source fixups applied) + completeness report
    per_yasna = {lbl: list(cache[key(block)]) for lbl, block in blocks}
    if name == "zoroastrianism":
        per_yasna = zoro_fixups(per_yasna)
    out, ok = [], True
    for lbl in order:
        verses = per_yasna[lbl]
        got, exp = sum(1 for v in verses if v["verse"] >= 1), verse_counts.get(lbl)
        flag = "" if exp is None or got == exp else f"  <-- expected {exp}"
        if flag:
            ok = False
        print(f"  Yasna {lbl:>2}: {got:>2} verses{flag}")
        for v in verses:
            out.append({"group": group.get(lbl, ""), "yasna": lbl,
                        "verse": v["verse"], "text": v["text"]})
    out_path = RAW / f"{name}.clean.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"[{name}] wrote {len(out)} verses -> {out_path}"
          f"  TOTAL COST ${total_cost:.2f}"
          f"{'' if ok else '  (verse-count mismatches above — spot-check)'}")


def main():
    for name in SOURCES:
        run_source(name)


if __name__ == "__main__":
    main()
