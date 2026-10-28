# Profile: procedure

For how-to text: ordered actions that transform an input into an outcome.
Boards grammar: a resident's walkthrough — present, check, act, confirm.

- START frames the task and its starting state in source terms, 2–4 bullets.
- Diamonds are readiness or validity checks the source states, numbered broad to specific. Never invent a check.
- Edge labels name the check outcome (Yes / No / the named state).
- Step bullets carry the action detail: who acts, with what, how much, how long. Thresholds and numbers exactly as written.
- Each fact once; the done-state closes the chart; TAKE names it in one line.

```mermaid
flowchart LR
n1(["<b>Prepare infusion</b><br/>• Gather sterile set<br/>• Verify order"]):::startNode
n2{"1. Order valid?"}:::decisionNode
n3(["<b>Run infusion</b><br/>• Set rate per order<br/>• Flush before and after"]):::altDx
n4(["<b>Done</b><br/>• Document volume given"]):::dispoNode
n1 --> n2
n2 -->|"Yes"| n3
n2 -->|"No"| n1
n3 --> n4
```
