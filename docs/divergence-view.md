# The Distinctives — what each tradition says that no one else does

**Status: built 2026-07-09 — `site/distinctives.html`, computed in the browser
from `ideas.json` + `data.json`. No hard purity threshold in the end: small
traditions (Taoism, Epicureanism) never reach 70% at k=60, so ideas are ranked
by purity × lift and the purity is shown honestly per row. $0.**

## What it is

The ideas map (`site/ideas.html`) celebrates overlap: ideas whose rings hold
many colours. This view is its deliberate opposite: for each tradition, *what
does it emphasise that no other tradition does?* The unique contribution of
each voice — Islam's insistence on divine unity, the Tao's praise of
not-striving, Epicurus' cool arithmetic of pleasure and pain — is exactly what
the "most shared" ranking hides.

## How it works

Everything needed is already in `site/ideas.json` (and its inputs):

- **Cluster purity.** Each of the 60 idea clusters carries per-tradition
  counts. A cluster is *distinctive* for tradition T when T's share is high
  (say ≥ 70%) **and** T's share is far above T's base rate in the corpus
  (lift, so 759-passage Stoicism doesn't win everything by volume). The
  effective-traditions score already computed (`eff`) is the inverse signal:
  distinctive clusters are the low-eff ones.
- **Per-passage isolation (finer grain, optional).** A passage whose top-10
  neighbours are *all* from its own tradition is an "island" passage. The
  fraction of island passages per source is a nice one-number summary of how
  much a text speaks only to itself.
- Ranking within a tradition: sort its distinctive clusters by lift ×
  cluster size, take the top 3–5.

## UI sketch

- One column (or card) per tradition, in the tradition's colour: "**Only in
  Taoism**" followed by its top distinctive ideas as small bubbles or rows,
  each expandable to the passages behind it.
- Each idea row shows the purity plainly: "34 of 36 passages are Taoist."
- Cross-links: every idea deep-links to `ideas.html#i<id>`, every passage to
  the map's `#p<id>`.
- A short honest caveat in the footer: distinctiveness is relative to *this
  corpus* — "unique to Hinduism" means "not in the eight other text
  selections," not "absent from all other human thought."

## Cost

$0 if built from the existing 60 clusters and labels. Optionally ~$0.05 of
Haiku to write one "what makes this tradition's voice distinct here" sentence
per tradition (9 calls' worth of tokens in a single batch), cached like the
cluster labels.

## Open questions

- Threshold tuning: purity ≥ 70%? lift ≥ 2? Pick by eyeballing the ranked
  list, not a priori.
- Small traditions (Taoism 122, Epicureanism 67) will have few distinctive
  clusters at k=60 — may want a finer clustering (k=120) computed once just
  for this view.
