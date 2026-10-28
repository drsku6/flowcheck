# Profile: rules (DRAFT — table never arrived; correct me)

For normative text: who must do what, by when, and what happens otherwise.

- Node roles: START names the rule system; steps are duties in order; outputs are outcomes or penalties; TAKE is the compliance summary.
- Diamonds mean applicability conditions and exceptions the source states.
- Edge labels name if-applies / if-exempt outcomes.
- Bullets: actors, deadlines, amounts, filings, consequences.

```mermaid
flowchart LR
n1(["<b>Rule</b><br/>• Scope"]):::startNode
n2{"Applies?"}:::decisionNode
n3(["<b>Comply</b><br/>• File by date"]):::altDx
n4(["<b>Result</b><br/>• Penalty if not"]):::dispoNode
n1 --> n2
n2 -->|"Yes"| n3
n2 -->|"Exempt"| n4
n3 --> n4
```
