#!/usr/bin/env bash
# Download the public-domain source texts from Project Gutenberg into data/raw/.
set -euo pipefail
cd "$(dirname "$0")/../data/raw"

# 216   Tao Te Ching (Legge)          2017  Dhammapada (Müller)
# 2680  Meditations (Casaubon)        10    KJV Bible (Proverbs, Ecclesiastes)
# 2388  Bhagavad Gita (Arnold)        3330  Analects (Legge)
# 45109 Enchiridion (Higginson)       3434  Koran (Rodwell)
# 3283  Upanishads (Paramananda)      57342 Diogenes Laertius (Yonge; Epicurus)
# 59709 Zhuangzi (Giles)              10056 Sayings of Mencius (Giles anthology)
# 8547  Pirkei Avot (Taylor)          45159 Rumi, The Persian Mystics (Davis)
for id in 216 2017 2680 10 2388 3330 45109 3434 3283 57342 59709 10056 8547 45159; do
  [ -f "pg${id}.txt" ] || curl -sL -o "pg${id}.txt" "https://www.gutenberg.org/cache/epub/${id}/pg${id}.txt" &
done
wait

# archive.org OCR scans (djvu.txt). Unlike Gutenberg these are messy OCR, cleaned
# downstream by pipeline/ocr_extract.py (LLM). The djvu.txt filename is NOT
# "<id>_djvu.txt" — it's prefixed by the item's own title, so resolve it from the
# metadata API first. Format: local_name=archive_id
for spec in "zoro_sbe31.txt=in.ernet.dli.2015.110222"; do   # SBE 31 = the Gathas (Mills 1887)
  out="${spec%%=*}"; id="${spec##*=}"
  [ -f "$out" ] && continue
  fn=$(curl -sL "https://archive.org/metadata/${id}/files" \
       | tr ',' '\n' | grep -oE '"[^"]*_djvu\.txt"' | head -1 | tr -d '"')
  [ -n "$fn" ] && curl -sL -o "$out" "https://archive.org/download/${id}/${fn}"
done
ls -la
