"""Chunk raw Gutenberg texts into passages -> data/passages.json

Each passage: {id, tradition, source, ref, text}
"""

import json
import re
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT = Path(__file__).resolve().parent.parent / "data" / "passages.json"

MAX_CHARS = 700  # split longer passages at sentence boundaries
MIN_CHARS = 60   # merge shorter ones into the next passage


def load(pgid: int) -> str:
    text = (RAW / f"pg{pgid}.txt").read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    # strip Gutenberg boilerplate
    start = re.search(r"\*\*\* START OF .*? \*\*\*", text)
    end = re.search(r"\*\*\* END OF .*? \*\*\*", text)
    return text[start.end() if start else 0 : end.start() if end else len(text)]


def clean(s: str) -> str:
    s = re.sub(r"\[.*?\]", "", s, flags=re.S)  # editorial notes / footnote refs
    s = re.sub(r"\(\d+\)", "", s)
    s = re.sub(r"\{\d+\}", "", s)              # {NN} inline page numbers (OCR/Gunn)
    s = s.replace("(?)", "")                   # translator's uncertainty marker
    s = s.replace("_", "").replace("=", "")    # Gutenberg italics / bold markers
    s = re.sub(r"&c\.?", "etc.", s)
    s = re.sub(r"\s*(--|——)\s*", " — ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)     # drop space before punctuation
    return s


def sentences(s: str) -> list[str]:
    return re.split(r"(?<=[.!?;:])\s+", s)


def split_long(text: str) -> list[str]:
    """Split text into chunks of <= MAX_CHARS at sentence boundaries."""
    if len(text) <= MAX_CHARS:
        return [text]
    chunks, cur = [], ""
    for sent in sentences(text):
        if cur and len(cur) + len(sent) + 1 > MAX_CHARS:
            chunks.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def emit(records, tradition, source, ref, text):
    text = clean(text)
    if len(text) < MIN_CHARS:
        return
    for i, chunk in enumerate(split_long(text)):
        r = ref if len(split_long(text)) == 1 else f"{ref} ({i + 1})"
        records.append({"tradition": tradition, "source": source, "ref": r, "text": chunk})


# --- Tao Te Ching (Legge). Chapters start "N. 1. text" or "N." alone on a
# line; verse numbers use the same shapes, so require sequential chapters. ---
def tao(records):
    body = load(216)
    m = re.search(r"^Ch\. 1\. ", body, re.M)
    body = body[m.end():]
    cuts, expected = [(0, 1)], 2
    for nm in re.finditer(r"^(\d{1,2})\.(?=\s)", body, re.M):
        if int(nm.group(1)) == expected:
            cuts.append((nm.start(), expected))
            expected += 1
    cuts.append((len(body), None))
    for (start, num), (nxt, _) in zip(cuts, cuts[1:]):
        text = re.sub(r"^(\d{1,2}\.\s*)+", "", body[start:nxt], flags=re.M)  # verse nums
        emit(records, "Taoism", "Tao Te Ching", f"ch. {num}", text)


# --- Dhammapada (Müller). "Chapter I. The Twin-Verses", verses "N. text" ---
def dhammapada(records):
    body = load(2017)
    m = re.search(r"^Chapter I\.", body, re.M)
    end = re.search(r"^\s*(FOOTNOTES|NOTES)", body[m.start():], re.M)
    body = body[m.start() : m.start() + end.start() if end else len(body)]
    chapter = ""
    for block in re.split(r"\n\n+", body):
        block = block.strip()
        cm = re.match(r"Chapter [IVXL]+\.\s*(.+)", block)
        if cm:
            chapter = cm.group(1).strip().rstrip(".")
            continue
        vm = re.match(r"(\d+)(?:, \d+)*\. (.+)", block, re.S)
        if vm:
            emit(records, "Buddhism", "Dhammapada", f"{chapter}, v. {vm.group(1)}", vm.group(2))


# --- Meditations (Casaubon). "THE FIRST BOOK" ... sections "I. text" ---
BOOK_NUMS = {"FIRST": 1, "SECOND": 2, "THIRD": 3, "FOURTH": 4, "FIFTH": 5, "SIXTH": 6,
             "SEVENTH": 7, "EIGHTH": 8, "NINTH": 9, "TENTH": 10, "ELEVENTH": 11, "TWELFTH": 12}


def meditations(records):
    body = load(2680)
    m = re.search(r"^THE FIRST BOOK", body, re.M)
    end = re.search(r"^(APPENDIX|GLOSSARY|NOTES|FOOTNOTES)", body[m.start():], re.M)
    body = body[m.start() : m.start() + end.start() if end else len(body)]
    book = 0
    ref, buf = None, ""

    def flush():
        if ref and buf:
            emit(records, "Stoicism", "Meditations", ref, buf)

    for block in re.split(r"\n\n+", body):
        block = block.strip()
        bm = re.match(r"THE (\w+) BOOK", block)
        if bm and bm.group(1) in BOOK_NUMS:
            flush()
            book, ref, buf = BOOK_NUMS[bm.group(1)], None, ""
            continue
        sm = re.match(r"([IVXL]+)\. (.+)", block, re.S)
        if sm and book:
            flush()
            ref, buf = f"{book}.{sm.group(1)}", sm.group(2)
        elif ref:
            buf = f"{buf} {block}"
    flush()


# --- Enchiridion (Higginson rev.). Centered roman numeral headings. ---
def enchiridion(records):
    body = load(45109)
    m = re.search(r"^\s*THE ENCHIRIDION\s*$", body, re.M)
    # body ends at the numbered footnotes; the publisher's catalog follows them
    end = re.search(r"^\[1\]|^\s*(FOOTNOTES|Footnotes|INDEX|The Library of Liberal Arts)", body[m.end():], re.M)
    body = body[m.end() : m.end() + end.start() if end else len(body)]
    parts = re.split(r"^\s{10,}([IVXL]+)\s*$", body, flags=re.M)
    for num, text in zip(parts[1::2], parts[2::2]):
        emit(records, "Stoicism", "Enchiridion", f"§{num}", text)


# --- KJV: Proverbs + Ecclesiastes. Verses "C:V text..." ---
def kjv(records):
    body = load(10)

    def book(name, start_pat, end_pat, group_chars, tradition="Hebrew wisdom", chapters=None):
        # last occurrence: the first is the table of contents
        m = list(re.finditer(start_pat, body))[-1]
        e = list(re.finditer(end_pat, body))[-1]
        section = body[m.end() : e.start()]
        verses = re.findall(r"(\d+):(\d+)\s+(.*?)(?=\s\d+:\d+\s|\Z)", section, re.S)
        # group consecutive verses in the same chapter up to group_chars
        cur_ch, cur_start, cur_end, cur_text = None, None, None, ""
        def flush():
            if cur_text:
                ref = f"{cur_ch}:{cur_start}" + (f"-{cur_end}" if cur_end != cur_start else "")
                emit(records, tradition, name, ref, cur_text)
        for ch, v, t in verses:
            if chapters and int(ch) not in chapters:
                continue
            t = re.sub(r"\s+", " ", t).strip()
            if ch == cur_ch and len(cur_text) + len(t) <= group_chars:
                cur_end, cur_text = v, f"{cur_text} {t}"
            else:
                flush()
                cur_ch, cur_start, cur_end, cur_text = ch, v, v, t
        flush()

    book("Proverbs", r"\nThe Proverbs\n", r"\nEcclesiastes\n", 220)
    book("Ecclesiastes", r"\nEcclesiastes\n", r"\nThe Song of Solomon\n", 350)
    # Christianity: the teaching-dense parts of the NT — sermons, parables,
    # farewell discourse, and the wisdom epistles (narrative chapters skipped)
    book("Matthew", r"\nThe Gospel According to Saint Matthew\n",
         r"\nThe Gospel According to Saint Mark\n", 300,
         tradition="Christianity", chapters={5, 6, 7, 13, 18, 25})
    book("Luke", r"\nThe Gospel According to Saint Luke\n",
         r"\nThe Gospel According to Saint John\n", 300,
         tradition="Christianity", chapters={6, 12, 14, 15, 16})
    book("John", r"\nThe Gospel According to Saint John\n",
         r"\nThe Acts of the Apostles\n", 300,
         tradition="Christianity", chapters={13, 14, 15})
    book("Romans", r"\nThe Epistle of Paul the Apostle to the Romans\n",
         r"\nThe First Epistle of Paul the Apostle to the Corinthians\n", 300,
         tradition="Christianity", chapters={12})
    book("1 Corinthians", r"\nThe First Epistle of Paul the Apostle to the Corinthians\n",
         r"\nThe Second Epistle of Paul the Apostle to the Corinthians\n", 300,
         tradition="Christianity", chapters={13})
    book("James", r"\nThe General Epistle of James\n",
         r"\nThe First Epistle General of Peter\n", 300,
         tradition="Christianity", chapters={1, 2, 3, 4, 5})


# --- Bhagavad Gita (Arnold, verse). Chapters, stanzas separated by blanks. ---
def gita(records):
    body = load(2388)
    chapters = re.split(r"^\s*CHAPTER ([IVX]+)\s*$", body, flags=re.M)
    for num, text in zip(chapters[1::2], chapters[2::2]):
        text = re.split(r"HERE ENDETH", text)[0]
        buf = ""
        n = 0
        for stanza in re.split(r"\n\s*\n", text):
            stanza = re.sub(r"^\s*\w[\w' ]*:\s*$", "", stanza, flags=re.M)  # speaker labels
            stanza = " ".join(line.strip() for line in stanza.splitlines() if line.strip())
            if not stanza:
                continue
            buf = f"{buf} {stanza}".strip()
            if len(buf) >= 350:
                n += 1
                emit(records, "Hinduism", "Bhagavad Gita", f"ch. {num}, §{n}", buf)
                buf = ""
        if buf:
            n += 1
            emit(records, "Hinduism", "Bhagavad Gita", f"ch. {num}, §{n}", buf)


# --- Analects (Legge). "BOOK I. HSIO R." ... "CHAP. I. 1. text" ---
def analects(records):
    body = load(3330)
    m = re.search(r"^BOOK I\.", body, re.M)
    body = body[m.start():]
    # chapters can share a paragraph block, so split on BOOK/CHAP tokens directly
    for bm in re.finditer(r"BOOK ([IVXL]+)\.(.*?)(?=BOOK [IVXL]+\.|\Z)", body, re.S):
        book, section = bm.group(1), bm.group(2)
        parts = re.split(r"CHAP\. ([IVXL]+)\.", section)
        for chap, text in zip(parts[1::2], parts[2::2]):
            text = re.sub(r"(^|\s)\d+\. ", r"\1", " ".join(text.split()))
            emit(records, "Confucianism", "Analects", f"{book}.{chap}", text)


# --- Koran (Rodwell, chronological order). "SURA XCVI.–NAME [I.]" headings;
# verses are paragraphs; footnotes follow a "____" rule. To keep traditions
# balanced we take the shorter (chiefly Meccan, hymnic/ethical) suras plus a
# few celebrated long ones. ---
QURAN_ALWAYS = {"XVII", "XXXI", "LV", "LXVII", "XXXVI"}  # Night Journey, Luqman, The Merciful, The Kingdom, Ya-Sin
QURAN_MAX_SURA_CHARS = 7000


def quran(records):
    body = load(3434)
    heads = list(re.finditer(r"^SURA1? ([IVXLC]+)[.\d]*[–\-—. ]*([A-Z' \-]*)", body, re.M))
    for h, nxt in zip(heads, heads[1:] + [None]):
        num, name = h.group(1), h.group(2).strip().title()
        section = body[h.end() : nxt.start() if nxt else len(body)]
        section = re.split(r"^_{5,}", section, flags=re.M)[0]  # drop footnotes
        section = re.sub(r"(?<=[a-z,;:!?'\"”’.])\d+", "", section)  # footnote marks
        paras = []
        for p in re.split(r"\n\s*\n", section):
            p = " ".join(p.split())
            if not p or re.match(r"(MECCA|MEDINA)", p) or p.startswith("In the Name of God"):
                continue
            paras.append(p)
        text_len = sum(len(p) for p in paras)
        if text_len > QURAN_MAX_SURA_CHARS and num not in QURAN_ALWAYS:
            continue
        buf, n = "", 0
        ref_name = f"Sura {num}" + (f" ({name})" if name else "")
        for p in paras:
            buf = f"{buf} {p}".strip()
            if len(buf) >= 400:
                n += 1
                emit(records, "Islam", "Quran", f"{ref_name} §{n}", buf)
                buf = ""
        if buf:
            n += 1
            emit(records, "Islam", "Quran", f"{ref_name} §{n}" if n > 1 else ref_name, buf)


# --- Upanishads (Paramananda): Isa, Katha, Kena. Verse = the first paragraph
# after a lone centered roman numeral; the rest is the Swami's commentary. ---
def upanishads(records):
    body = load(3283)
    isa = re.search(r"^\s*Isa-Upanishad\s*$\s+^\s*Peace Chant", body, re.M).start()
    katha = list(re.finditer(r"^\s{10,}Katha-Upanishad\s*$", body, re.M))[-1].start()
    kena = re.search(r"^KENA-UPANISHAD\s*$", body, re.M).start()
    for name, section in (("Isa", body[isa:katha]), ("Katha", body[katha:kena]),
                          ("Kena", body[kena:])):
        part = ""
        blocks = re.split(r"\n\s*\n", section)
        i = 0
        while i < len(blocks):
            b = blocks[i].strip()
            pm = re.match(r"Part (First|Second|Third|Fourth|Fifth|Sixth)$", b, re.I)
            if pm:
                ordinals = ["first", "second", "third", "fourth", "fifth", "sixth"]
                part = f"{ordinals.index(pm.group(1).lower()) + 1}."
                i += 1
                continue
            if re.fullmatch(r"[IVXL]+", b) and i + 1 < len(blocks):
                verse = " ".join(blocks[i + 1].split())
                emit(records, "Hinduism", "Upanishads", f"{name} {part}{b}", verse)
                i += 2
                continue
            i += 1


# --- Epicurus (Yonge's Diogenes Laertius, Book X): the Letter to Menoeceus
# and the Principal Doctrines. ---
def epicurus(records):
    body = load(57342)
    m = re.search(r"^EPICURUS TO MEN.?CEUS, GREETING", body, re.M)
    end = re.search(r"^XXVIII\. Now, he differs", body[m.end():], re.M)
    letter = body[m.end() : m.end() + end.start()]
    n = 0
    for p in re.split(r"\n\s*\n", letter):
        p = " ".join(p.split()).strip("“” ")
        if len(p) < MIN_CHARS:
            continue
        n += 1
        emit(records, "Epicureanism", "Letter to Menoeceus", f"§{n}", p)
    m = re.search(r"^XXXI\. Let us, however, now add the finishing stroke", body, re.M)
    end = re.search(r"^FOOTNOTES", body[m.end():], re.M)
    maxims = body[m.end() : m.end() + end.start()]
    for mm in re.finditer(r"^(\d{1,2})\. (.*?)(?=^\d{1,2}\. |\Z)", maxims, re.M | re.S):
        text = re.sub(r"\(In other passages.*?\)", "", mm.group(2), flags=re.S)
        text = " ".join(text.split()).strip("“” ")
        emit(records, "Epicureanism", "Principal Doctrines", f"#{mm.group(1)}", text)


# --- Zhuangzi (Giles, "Chuang Tzu"). "CHAPTER I." then an all-caps subtitle and
# an "_Argument_:" precis (both skipped); the remainder is prose. ---
def zhuangzi(records):
    body = load(59709)
    heads = list(re.finditer(r"^CHAPTER ([IVXLC]+)\.\s*$", body, re.M))
    # keep only the Inner Chapters (I-VII) — the authentic core; the Outer and
    # Miscellaneous chapters are later accretions and would swamp the corpus.
    inner = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
    for h, nxt in zip(heads, heads[1:] + [None]):
        num = h.group(1)
        if num not in inner:
            continue
        section = body[h.end() : nxt.start() if nxt else len(body)]
        buf = ""
        for para in re.split(r"\n\s*\n", section):
            p = " ".join(para.split())
            if not p or p == p.upper():          # skip the all-caps subtitle
                continue
            if re.match(r"_?Argument_?", p):      # skip the chapter precis
                continue
            buf = f"{buf} {p}".strip()
            if len(buf) >= 500:
                emit(records, "Taoism", "Zhuangzi", f"ch. {num}", buf)
                buf = ""
        if buf:
            emit(records, "Taoism", "Zhuangzi", f"ch. {num}", buf)


# --- Mencius ("Sayings of Mencius", Giles, in the Chinese Literature anthology).
# BOOK I..VII, each with an all-caps honorific title and Part I/II, then dialogue
# paragraphs. The selection ends where "THE SHI-KING" begins. ---
def mencius(records):
    body = load(10056)
    i = body.rfind("THE SAYINGS OF MEN")
    section = body[i : body.index("THE SHI-KING", i)]
    book, part = None, ""
    buf, ref = "", None

    def flush():
        if buf and ref:
            emit(records, "Confucianism", "Mencius", ref, buf)

    for para in re.split(r"\n\s*\n", section):
        p = " ".join(para.split())
        if not p:
            continue
        bm = re.match(r"BOOK ([IVXL]+)$", p)
        pm = re.match(r"Part ([IVX]+)$", p, re.I)
        if bm:
            flush(); book, buf, ref = bm.group(1), "", None; continue
        if pm:
            flush(); part, buf, ref = pm.group(1), "", None; continue
        if p == p.upper() and len(p) < 40:        # book's honorific title line
            continue
        ref = f"{book}.{part}" if part else f"{book}"
        buf = f"{buf} {p}".strip()
        if len(buf) >= 450:
            flush(); buf = ""
    flush()


# --- Pirkei Avot (Taylor, "Sayings of the Jewish Fathers"). CHAPTER I..VI, each
# saying at col-0 "N. ..."; indented blocks below a saying are footnotes. ---
def pirkei_avot(records):
    body = load(8547)
    start = body.index("CHAPTER I", body.index("Moses received") - 400)
    region = body[start:]
    end = re.search(r"^\s*(NOTES|APPENDIX|ABBREVIATIONS|INDEX|Transcriber)", region, re.M)
    if end:
        region = region[: end.start()]
    chaps = list(re.finditer(r"^CHAPTER ([IVX]+)\s*$", region, re.M))
    for h, nxt in zip(chaps, chaps[1:] + [None]):
        num = h.group(1)
        chtext = region[h.end() : nxt.start() if nxt else len(region)]
        parts = re.split(r"(?m)^(\d+)\.\s", chtext)
        for sid, seg in zip(parts[1::2], parts[2::2]):
            cut = re.search(r"\n[ \t]+\S", seg)   # first indented line = footnotes
            saying = " ".join((seg[: cut.start()] if cut else seg).split())
            emit(records, "Hebrew wisdom", "Pirkei Avot", f"{num}:{sid}", saying)


# --- Rumi ("The Persian Mystics", Davis/Whinfield renderings). After the prose
# introduction, a run of titled poems; each all-caps title (col 0) starts one. ---
def rumi(records):
    body = load(45159)
    start = body.index("A CRY TO THE BELOVED")
    region = body[start : body.index("APPENDIX", start)]
    # titles are centre-indented and fully upper-case, one per line
    heads = list(re.finditer(r"^[ \t]*([A-Z][A-Z ,'’\-]{3,75})[ \t]*$", region, re.M))
    for h, nxt in zip(heads, heads[1:] + [None]):
        title = " ".join(h.group(1).split()).title()
        text = " ".join(region[h.end() : nxt.start() if nxt else len(region)].split())
        emit(records, "Islam", "Rumi", title, text)


# --- Ancient Egypt: the Instruction of Ptah-hotep + Ke'gemni (Gunn, "The Oldest
# Books in the World"). Numbered maxims "N.  text" at col 0. The Instruction of
# Amenemhe'et that follows Ke'gemni is a royal political testament, not wisdom —
# skipped (its numbering would also collide). ---
def ptahhotep(records):
    body = load(30508)
    m = re.search(r"^He said unto his son:", body, re.M)
    k = re.search(r"^THE INSTRUCTION OF KE'GEMNI", body[m.end():], re.M)
    pt = body[m.end() : m.end() + k.start()]
    maxim = r"^(\d+)\.(?:\[\d+\])?\s+(.*?)(?=^\d+\.(?:\[\d+\])?\s|\Z)"
    for mm in re.finditer(maxim, pt, re.M | re.S):
        emit(records, "Ancient Egypt", "Ptah-hotep", f"maxim {mm.group(1)}", mm.group(2))
    kb = body[m.end() + k.start():]
    fin = re.search(r"IT IS FINISHED", kb)
    kb = kb[: fin.start()] if fin else kb
    for mm in re.finditer(maxim, kb, re.M | re.S):
        emit(records, "Ancient Egypt", "Ke'gemni", f"maxim {mm.group(1)}", mm.group(2))


# --- Buddhism (Mahāyāna): the Diamond Sutra (Gemmell/Prajna-Paramita). The
# transcriber marks sections "[Chapter N]" and moves footnotes to each chapter's
# end (first indented "[N]" line onward). ---
def diamond_sutra(records):
    body = load(64623)
    m = re.search(r"^\[Chapter 1\]", body, re.M)
    body = body[m.start():]
    for cm in re.finditer(r"^\[Chapter (\d+)\][ \t]*$(.*?)(?=^\[Chapter \d+\]|\Z)",
                          body, re.M | re.S):
        num, text = cm.group(1), cm.group(2)
        cut = re.search(r"\n[ \t]+\[\d+\]", text)
        emit(records, "Buddhism", "Diamond Sutra", f"ch. {num}",
             text[: cut.start()] if cut else text)


# --- Bahá'í: Tablets of Abdul-Baha Abbas (Bahai Publishing Society, 1909–19; PD).
# Volume I only, to keep the corpus balanced (all 3 vols = 840 tablets). Each tablet
# is a letter opening with a col-0 salutation ("O ye…", "O thou…", "He is God…");
# split there. Capped at ~175 passages. ---
def bahai(records):
    body = load(19312)
    m = re.search(r"^TABLETS OF ABDUL-BAHA\s*$", body, re.M)
    v2 = re.search(r"^VOLUME II", body[m.end():], re.M)
    vol1 = body[m.end() : m.end() + v2.start()]
    tablets = re.split(r"(?m)^(?=(?:O (?:ye|thou|my God|God|Lord|thou who)|He is God))",
                       vol1)
    n = 0
    for t in tablets:
        if len(t.strip()) < 120:
            continue
        n += 1
        emit(records, "Bahá'í", "Tablets of Abdul-Baha", f"Vol. I §{n}", t)
        if sum(1 for r in records if r["tradition"] == "Bahá'í") >= 175:
            break


# --- Zoroastrianism: the Gathas (SBE 31, Mills). Not parsed from raw OCR here —
# the scan is too noisy for regex, so pipeline/ocr_extract.py distils it into clean
# numbered verses first (data/raw/zoroastrianism.clean.json); we just emit those. ---
def zoroastrianism(records):
    path = RAW / "zoroastrianism.clean.json"
    if not path.exists():
        print("  (skip Zoroastrianism: run pipeline/ocr_extract.py first)")
        return
    for v in json.loads(path.read_text(encoding="utf-8")):
        emit(records, "Zoroastrianism", "Gathas", f"Yasna {v['yasna']}.{v['verse']}",
             v["text"])


# --- Jainism / Sikhism / Mesopotamia: like Zoroastrianism these are archive.org OCR
# distilled to clean passages by pipeline/ocr_extract.py ([{ref, text}]); emit those. ---
def _ocr_passages(records, tradition, source, filename, ref_prefix=""):
    path = RAW / filename
    if not path.exists():
        print(f"  (skip {tradition}: run pipeline/ocr_extract.py first)")
        return
    for i, v in enumerate(json.loads(path.read_text(encoding="utf-8")), 1):
        ref = f"{ref_prefix}{v['ref']}" if v.get("ref") else f"{ref_prefix}§{i}"
        emit(records, tradition, source, ref, v["text"])


def jainism(records):
    _ocr_passages(records, "Jainism", "Uttaradhyayana", "jainism.clean.json", "v. ")


def sikhism(records):
    _ocr_passages(records, "Sikhism", "Adi Granth (Macauliffe)", "sikhism.clean.json")


def mesopotamia(records):
    _ocr_passages(records, "Mesopotamia", "Babylonian hymns & psalms",
                  "mesopotamia.clean.json")


def main():
    records = []
    for fn in (tao, dhammapada, meditations, enchiridion, kjv, gita, analects,
               quran, upanishads, epicurus, zhuangzi, mencius, pirkei_avot, rumi,
               zoroastrianism, ptahhotep, diamond_sutra, bahai,
               jainism, sikhism, mesopotamia):
        before = len(records)
        fn(records)
        src = records[-1]["source"] if len(records) > before else fn.__name__
        print(f"{src:20s} {len(records) - before:5d} passages")
    for i, r in enumerate(records):
        r["id"] = i
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=1))
    print(f"\ntotal {len(records)} passages -> {OUT}")


if __name__ == "__main__":
    main()
