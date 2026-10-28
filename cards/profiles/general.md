# Profile: general (DRAFT — table never arrived; correct me)

Fallback for expository text that fits no other profile.

- Node roles: START frames the topic; steps are key points in source order; outputs are results; TAKE is the one-line synthesis.
- Diamonds only for explicit comparisons or choices the source states.
- Edge labels name the relation (leads to / contrasts / for example).
- Bullets: key facts with numbers and hedges kept verbatim in spirit.

```mermaid
flowchart LR
n1(["<b>Topic</b><br/>• Frame"]):::startNode
n2{"Which case?"}:::decisionNode
n3(["<b>Point</b><br/>• Key fact"]):::altDx
n4(["<b>Synthesis</b><br/>• One line"]):::dispoNode
n1 --> n2
n2 -->|"Case A"| n3
n2 -->|"Case B"| n4
n3 --> n4
```
