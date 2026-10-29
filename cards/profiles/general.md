# Profile: general

Fallback for expository text that fits no other profile.
Boards grammar applies unchanged: frame, fork, route, conclude — each fact once.

- START frames the topic and its setting, 2–4 bullets.
- Diamonds only for explicit comparisons or choices the source states, numbered broad to specific.
- Edge labels name the relation the source supports (leads to / contrasts with / for example).
- Bullets carry key facts with numbers and hedges kept exactly as written.
- Each fact once; the synthesis closes the chart; TAKE states it in one line.

```mermaid
flowchart LR
n1(["<b>Topic</b><br/>• Setting<br/>• Why it matters"]):::startNode
n2{"1. Which case?"}:::decisionNode
n3(["<b>Case A</b><br/>• Key fact<br/>• Key number"]):::altDx
n4(["<b>Synthesis</b><br/>• One line"]):::dispoNode
n1 --> n2
n2 -->|"First case"| n3
n2 -->|"Second case"| n4
n3 --> n4
```
