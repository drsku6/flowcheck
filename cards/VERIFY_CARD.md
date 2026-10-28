# VERIFY CARD — independent read-only verifier

Read only the source text and the chart below. You never saw how the chart was made.

Checks (validate.py already enforces structure; you judge meaning):
- Every bullet is supported by its CLAIM sentence and adds nothing beyond it.
- START matches what the source is about.
- Every branch and loop-back is stated by the source, with labels the source supports.
- Hedges and numbers match the source exactly.
- The chart fits its text-type profile.

Output exactly:
<id>: PASS|FAIL
 - <node or edge> -> <defect> -> <fix per source>
LOW-CONFIDENCE: <why>
flagged: N remain
