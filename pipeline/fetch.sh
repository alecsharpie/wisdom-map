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
ls -la
