"""Extract clean scripture from noisy archive.org OCR via `claude -p` (Opus).

Gutenberg texts are clean enough for a bespoke regex parser (see chunk.py). The
archive.org scans are not: verse text breaks across page-break footnote columns,
running heads are inconsistently mangled, apparatus and (for Macauliffe) biography
are interleaved line-by-line with the scripture. Regex can't separate that; an LLM
can. This stage is the reusable OCR path.

Two source shapes:
  * "verses"   — a text with a fixed canonical structure we can verify (the Gathas:
                 17 Yasnas, known verse counts). Slice per section, extract numbered
                 verses, sanity-check counts, apply documented fixups.
  * "passages" — a messier text with no clean per-unit contract (Jaina Uttaradhyayana,
                 Macauliffe's Sikh hymns, Babylonian hymns/psalms). Slice a bounded
                 wisdom region into fixed-size blocks, ask Opus for clean passages,
                 cap the total for corpus balance. Spot-check output by eye.

Cost is reported via --output-format json, summed and printed; a probe block runs
first and the projected total must stay under BUDGET_USD. Results cache by block hash.

Usage: python3 pipeline/ocr_extract.py [<name> ...] [--probe-only]
       (no names = all sources; cached sources cost $0)
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
BUDGET_USD = 12.0


def key(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def _lines(fname):
    return (RAW / fname).read_text(encoding="utf-8", errors="replace").split("\n")


def _chunk(lines, a, b, size=340):
    """lines[a:b] as ~size-line string blocks."""
    seg = lines[a:b]
    return ["\n".join(seg[i:i + size]) for i in range(0, len(seg), size)]


# ============================ Zoroastrianism (verses) =========================
# The Gathas run from the first 'Translation.' header to 'THE YASNA.' (after which
# come the ordinary liturgical Yasnas + fragments — ritual, not wisdom, so cut).
# Each Gatha has one 'Translation.' header before its verses (two OCR'd as
# 'Translation,'). The 17 Gathas appear in Mills's fixed print order:
ZORO_ORDER = [29, 28, 30, 31, 32, 33, 34, 43, 44, 45, 46, 47, 48, 49, 50, 51, 53]
ZORO_GROUP = {
    **{y: "Ahunavaiti Gatha" for y in (28, 29, 30, 31, 32, 33, 34)},
    **{y: "Ushtavaiti Gatha" for y in (43, 44, 45, 46)},
    **{y: "Spenta-mainyu Gatha" for y in (47, 48, 49, 50)},
    51: "Vohu-khshathra Gatha", 53: "Vahishtoishti Gatha",
}
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
    "- DROP every footnote and word-for-word alternate rendering, all running heads, "
    "page numbers, and any prose INTRODUCTION or argument about the hymn.\n"
    "- KEEP the translator's parenthetical glosses like '(O Ahura and Asha!)' and fold "
    "in speaker labels like 'Ahura speaks.' before the verse they head.\n"
    "- Do NOT paraphrase, summarize, or modernize the wording; only repair obvious OCR.\n"
    "- If the block contains no genuine numbered scripture verse, return [].\n"
    'Reply with ONLY a JSON array: [{"verse":<int>,"text":"..."},...]'
)


def slice_zoroastrianism():
    lines = _lines("zoro_sbe31.txt")
    heads = [i for i, ln in enumerate(lines) if re.match(r"^Translation[.,]", ln.strip())]
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "THE YASNA.")
    heads = [h for h in heads if h < end]
    if len(heads) != len(ZORO_ORDER):
        raise SystemExit(f"expected {len(ZORO_ORDER)} 'Translation.' headers, found {len(heads)}")
    bounds = heads + [end]
    return [(y, "\n".join(lines[a:b]))
            for y, a, b in zip(ZORO_ORDER, bounds, bounds[1:])]


def zoro_fixups(per_yasna):
    """Repair the two artifacts the verse-count check + a spot-read surfaced:
    (1) Yasna 49's last verse sliced into Yasna 50's block (numbered 12) -> move back.
    (2) Yasna 28's unnumbered liturgical prelude numbered as v1 -> relabel v0, shift."""
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


# ============================ new OCR sources (passages) ======================
JAIN_PROMPT = (
    "The text on stdin is OCR'd from Sacred Books of the East vol. 45 (Jacobi), the "
    "Uttaradhyayana — a Jaina sutra of ethical teaching in numbered verses (each verse "
    "ends with its number in parentheses, e.g. '(15)').\n"
    "- Extract each verse as one clean passage.\n"
    "- Fix OCR errors: rejoin words split across line-breaks ('sub- due' -> 'subdue'), "
    "read a lone '1' as 'I', repair obvious letter swaps.\n"
    "- DROP running heads ('UTTARADHYAYANA'), page numbers, footnote digits, and footnotes.\n"
    "- Keep the translation's wording; use the verse number as the ref if visible.\n"
    "- If the block has no scripture verse, return [].\n"
    'Reply with ONLY a JSON array: [{"ref":"<verse no. or short label>","text":"..."},...]'
)
SIKH_PROMPT = (
    "The text on stdin is OCR'd from Macauliffe's 'The Sikh Religion' vol. I. It mixes "
    "Guru Nanak's translated Sikh scripture (the Japji, and his hymns/shabads) with "
    "Macauliffe's biographical prose and scholarly notes.\n"
    "- Extract ONLY the translated scripture — the hymns, pauris and sloks themselves.\n"
    "- Do NOT include Macauliffe's narrative or framing sentences ('Guru Nanak then "
    "uttered the following', 'On this occasion he composed…'), or any footnote.\n"
    "- Fix OCR errors; keep the scripture's own wording. One hymn or numbered stanza = "
    "one passage.\n"
    "- If the block is entirely prose/biography, return [].\n"
    'Reply with ONLY a JSON array: [{"ref":"<short label e.g. Japji 1>","text":"..."},...]'
)
MESO_PROMPT = (
    "The text on stdin is OCR'd from 'Babylonian and Assyrian Literature' (1901). This "
    "region holds ancient Mesopotamian hymns, prayers, and penitential psalms.\n"
    "- Extract each hymn / prayer / penitential psalm (or a coherent stanza of one) as "
    "a clean passage.\n"
    "- DROP the editor's section headers, running heads, page numbers, footnotes, and "
    "any prose commentary, narrative, or transliteration. Keep only the poem's words.\n"
    "- Fix OCR errors (rejoin split words, repair obvious letter swaps).\n"
    "- If a block is only commentary or narrative, return [].\n"
    'Reply with ONLY a JSON array: [{"ref":"<short label>","text":"..."},...]'
)


def slice_jainism():
    # Uttaradhyayana Lectures I..~X (of 36) — the ethical core, sized for ~200 verses.
    return [(f"b{i}", b) for i, b in enumerate(_chunk(_lines("jain_sbe45.txt"), 1765, 3810))]


def slice_sikhism():
    # the Japji (Guru Nanak's morning prayer) + his collected hymns; both interleaved
    # with Macauliffe's biography, which Opus is told to drop.
    lines = _lines("sikh_macauliffe1.txt")
    blocks = _chunk(lines, 5990, 6430) + _chunk(lines, 14900, 18600)
    return [(f"b{i}", b) for i, b in enumerate(blocks)]


def slice_mesopotamia():
    # the reflective parts only: Heabani's wisdom, the hymn to Istar, prayers, and the
    # penitential psalms — skip the Izdubar epic, creation/flood myth, and exorcisms.
    lines = _lines("meso_babassyr.txt")
    blocks = (_chunk(lines, 2990, 3260)      # Heabani's wisdom
              + _chunk(lines, 9020, 9360)    # Songs of the Sabitu (Siduri's carpe-diem counsel)
              + _chunk(lines, 10650, 10970)  # Accadian hymn to Istar
              + _chunk(lines, 13110, 13660)  # prayer for the king, penitential psalms, imputed sins
              + _chunk(lines, 15370, 15630)  # an Accadian penitential psalm
              + _chunk(lines, 17920, 18570)) # Chaldean hymns to the sun, two Accadian hymns, proverbs
    return [(f"b{i}", b) for i, b in enumerate(blocks)]


SOURCES = {
    "zoroastrianism": {"kind": "verses", "slicer": slice_zoroastrianism,
                       "prompt": ZORO_PROMPT, "order": ZORO_ORDER,
                       "verse_counts": ZORO_VERSES, "group": ZORO_GROUP},
    "jainism": {"kind": "passages", "slicer": slice_jainism, "prompt": JAIN_PROMPT,
                "cap": 200},
    "sikhism": {"kind": "passages", "slicer": slice_sikhism, "prompt": SIKH_PROMPT,
                "cap": 180},
    "mesopotamia": {"kind": "passages", "slicer": slice_mesopotamia, "prompt": MESO_PROMPT,
                    "cap": 160},
}


def extract_block(prompt, block):
    """Returns (cost_usd, [raw item dict, ...]) — items are whatever the model returned."""
    proc = subprocess.run(
        ["claude", "-p", "--model", MODEL, "--output-format", "json", prompt],
        input=block, capture_output=True, text=True, timeout=600,
    )
    doc = json.loads(proc.stdout)
    cost = float(doc.get("total_cost_usd") or 0)
    m = re.search(r"\[.*\]", doc.get("result", ""), re.S)
    items = json.loads(m.group(0)) if m else []
    return cost, items


def run_source(name):
    cfg = SOURCES[name]
    blocks = cfg["slicer"]()
    cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    misses = [(lbl, b) for lbl, b in blocks if key(b) not in cache]
    print(f"[{name}] {len(blocks)} blocks, {len(blocks) - len(misses)} cached, "
          f"{len(misses)} to extract")

    total_cost = 0.0
    for i, (lbl, block) in enumerate(misses):
        cost, items = extract_block(cfg["prompt"], block)
        cache[key(block)] = items
        CACHE_PATH.write_text(json.dumps(cache))
        total_cost += cost
        if i == 0:  # probe
            projected = cost * len(misses)
            print(f"probe [{lbl}]: ${cost:.4f}, {len(items)} items "
                  f"-> projected ${projected:.2f} over {len(misses)} blocks")
            if "--probe-only" in sys.argv:
                return
            if projected > BUDGET_USD:
                raise SystemExit(f"projected ${projected:.2f} exceeds ${BUDGET_USD} budget")
        else:
            print(f"  [{lbl}] +{len(items)} items, total ${total_cost:.2f}")

    if cfg["kind"] == "verses":
        assemble_verses(name, cfg, blocks, cache, total_cost)
    else:
        assemble_passages(name, cfg, blocks, cache, total_cost)


def assemble_verses(name, cfg, blocks, cache, total_cost):
    per = {lbl: [{"verse": it["verse"], "text": " ".join(str(it["text"]).split())}
                 for it in cache[key(b)]
                 if isinstance(it.get("verse"), int) and it.get("text")]
           for lbl, b in blocks}
    if name == "zoroastrianism":
        per = zoro_fixups(per)
    out, ok = [], True
    for lbl in cfg["order"]:
        verses = per[lbl]
        got, exp = sum(1 for v in verses if v["verse"] >= 1), cfg["verse_counts"].get(lbl)
        flag = "" if exp is None or got == exp else f"  <-- expected {exp}"
        ok = ok and not flag
        print(f"  Yasna {lbl:>2}: {got:>2} verses{flag}")
        for v in verses:
            out.append({"group": cfg["group"].get(lbl, ""), "yasna": lbl,
                        "verse": v["verse"], "text": v["text"]})
    path = RAW / f"{name}.clean.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"[{name}] wrote {len(out)} verses -> {path}  TOTAL ${total_cost:.2f}"
          f"{'' if ok else '  (count mismatch — spot-check)'}")


def assemble_passages(name, cfg, blocks, cache, total_cost):
    out, seen = [], set()
    for lbl, b in blocks:
        for it in cache[key(b)]:
            txt = " ".join(str(it.get("text", "")).split())
            if len(txt) < 40 or txt in seen:   # skip empties + de-dup overlaps
                continue
            seen.add(txt)
            out.append({"ref": str(it.get("ref", "") or "").strip(), "text": txt})
    cap = cfg.get("cap")
    if cap and len(out) > cap:
        out = out[:cap]
    path = RAW / f"{name}.clean.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"[{name}] wrote {len(out)} passages "
          f"(cap {cap}) -> {path}  TOTAL ${total_cost:.2f}")


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(SOURCES)
    for name in names:
        run_source(name)


if __name__ == "__main__":
    main()
