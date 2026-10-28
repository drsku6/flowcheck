# Profile: evidence

For findings text: claims weighed against supporting evidence.
Boards grammar: every finding traces to its sentence; certainty never upgrades.

- START states the question and its context, 2–4 bullets.
- Diamonds are forks the evidence forces (effect vs no effect, rival readings), numbered broad to specific.
- Edge labels name the inference the source supports (supports / contradicts / inconclusive).
- Bullets carry findings with magnitudes, samples, and conditions. Keep every uncertainty word; numbers exactly.
- Each fact once; the bottom line closes the chart; TAKE states it in one line.

```mermaid
flowchart LR
n1(["<b>Does X lower Y?</b><br/>• Trial context<br/>• Measured over weeks"]):::startNode
n2{"1. What showed?"}:::decisionNode
n3(["<b>Effect seen</b><br/>• Mean drop with range<br/>• In the treated group"]):::altDx
n4(["<b>Answer</b><br/>• Modest effect, limited sample"]):::dispoNode
n1 --> n2
n2 -->|"Supports"| n3
n2 -->|"Against"| n4
n3 --> n4
```
