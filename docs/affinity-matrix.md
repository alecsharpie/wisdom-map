# The Affinities — a tradition × tradition resonance matrix

**Status: built 2026-07-09 — `site/affinities.html`, computed in the browser
from `data.json` at load time. Zero LLM cost.**

## What it is

A 9×9 heatmap answering one question the map only hints at: *which pairs of
traditions echo each other most?* One glance should tell you whether Stoicism
really is closer to Buddhism than to its Greek sibling Epicureanism, whether
Hebrew wisdom leans toward Christianity or Islam, and which pairing is the
most estranged.

## How it works

No new pipeline stage and no LLM calls — every ingredient is already in
`site/data.json`:

- **Neighbour-based affinity (recommended).** Every passage carries its top-10
  cosine neighbours (`nb`). For each ordered pair of traditions (A, B), count
  how often a passage from A has a neighbour from B, then normalise by the
  count expected if neighbours were assigned at random given tradition sizes
  (observed / expected, a lift score). Lift > 1 means "more entangled than
  chance"; < 1 means mutual avoidance. Normalising by expectation matters
  because Stoicism (759 passages) would otherwise dominate every row.
- Alternative: mean pairwise cosine between all cross-tradition passage pairs
  (needs the cached `.npy` embeddings, one afternoon of numpy). Smoother, but
  the neighbour version better reflects what a user actually experiences when
  clicking around the map.

The matrix is symmetric-ish but not exactly (A→B lift ≠ B→A lift); showing
the symmetrised mean is fine, with the asymmetry available on hover.

## UI sketch

- A single-hue sequential heatmap (one colour, light→dark = low→high lift),
  9×9 with tradition names on both axes, values on hover, and the diagonal
  greyed out (self-affinity is uninteresting).
- Click a cell → side panel listing the strongest actual passage pairs behind
  that number (e.g. the ten highest-similarity Stoicism↔Buddhism pairs), each
  deep-linking into the map.
- A one-line "headline" above the grid, computed from the data: *"Closest
  pair: X ↔ Y. Most estranged: P ↔ Q."*
- Optionally a second toggle: raw counts vs. lift, for the curious.

## Cost

$0. One ~100-line addition to the pipeline (or even computed in the browser
from `data.json` at load time — 3,635 × 10 neighbour entries is nothing), one
new static page reusing the site's palette and panel styling.

## Open questions

- Sequential colour ramp needs picking + validating against both surfaces
  (the categorical palette doesn't apply to a heatmap).
- Does the Sermon-on-the-Mount-heavy Christianity sample bias its row toward
  Hebrew wisdom? Worth a footnote in the UI either way.
