# Profile: evidence (DRAFT — table never arrived; correct me)

For findings text: claims weighed against supporting evidence.

- Node roles: START states the question; steps are observations or trials; outputs are conclusions; TAKE is the bottom line.
- Diamonds mean a fork the evidence forces (effect vs no effect, competing interpretations).
- Edge labels name the inference (supports / contradicts / inconclusive).
- Bullets: findings with magnitudes, samples, conditions; keep uncertainty words.

```mermaid
flowchart LR
n1(["<b>Question</b><br/>• Context"]):::startNode
n2{"What shows?"}:::decisionNode
n3(["<b>Finding</b><br/>• Effect size"]):::altDx
n4(["<b>Answer</b><br/>• Bottom line"]):::dispoNode
n1 --> n2
n2 -->|"Supports"| n3
n2 -->|"Against"| n4
n3 --> n4
```
