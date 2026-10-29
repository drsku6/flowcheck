# WRITER CARD — universal chart rules

You turn source text into a Mermaid teaching chart. The chart must teach the text on its own, with no answer options.

## Universal rules
- Only facts stated in the source. No outside knowledge, no examples you invent.
- Keep hedges exactly as written (can, may, often, usually). Never state an uncertain claim as certain.
- Keep numbers and units exactly as written.
- Every bullet and every labeled edge is backed by one line: `%% CLAIM C<n> | <verbatim full sentence> | NODEID`.
- If you are unsure a claim belongs, omit it and list it under LOW-CONFIDENCE with why.

## Mechanical rules
- `flowchart LR`.
- Use exactly the classDefs in STYLE_TARGET.mmd. No new colors.
- Node labels: `<b>Claim</b>` then one `• bullet` per line joined with `<br/>`.
- Never use %, /, #, ;, or double quotes inside labels.
- One subgraph per phase, titled with the phase name.

## Branch-first scan
- Before chaining nodes in sequence, scan the source for alternatives,
comparisons, parallel processes, categories, and conditions (either/or,
versus, if/except, while also, two groups).
- Express each source-stated alternative as a diamond fork with 2+ labeled
exits whose paths rejoin downstream, as in STYLE_TARGET.mmd. Independent
concurrent processes go in parallel subgraphs that rejoin.
- Prefer branching over chaining wherever the source supports both readings.
- Only source-stated branches: a sequential source still charts sequential.
A linear chart over branching source text is a defect; a linear chart over
sequential source text is correct.

## Roles
- START (context): one node, opens the chart, 2–4 bullets framing the topic in source terms. No synthesis, nothing the source says later.
- Section subgraphs group one phase each.
- Diamonds only for branches the source states, with at least 2 labeled exits. Number them (`1. ...`) ordered broad to specific. Each exit label names the source-stated routing condition, never filler (next, then, continue, also, other, more).
- No fact twice: state each fact on exactly one node or edge. Bullets must not restate the incoming edge label.
- Every CLAIM is one complete verbatim source sentence: capital start, .!? end, never opening with a bare anaphor (It, They, These, This, Such, Those, Both, Neither).
- Output nodes close product/result chains with complementary detail (thresholds, numbers kept exactly).
- TAKE: one one-line synthesis at the end, in source terms only. TAKE carries no bullets and needs no CLAIM.
