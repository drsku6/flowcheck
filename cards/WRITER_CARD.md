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

## Roles
- START (context): one node, opens the chart, frames the topic.
- Section subgraphs group one phase each.
- Diamonds only for branches the source states, with at least 2 labeled exits.
- Output nodes close product/result chains.
- TAKE: one one-line synthesis at the end.
