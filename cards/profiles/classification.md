# Profile: classification (DRAFT — table never arrived; correct me)

For taxonomy text: sorting items into named categories by criteria.

- Node roles: START names what is being classified; steps are sorting stages; outputs are the categories; TAKE is the scheme summary.
- Diamonds mean a distinguishing criterion the source states.
- Edge labels name the criterion value leading to each category.
- Bullets: defining features, typical members, boundary notes.

```mermaid
flowchart LR
n1(["<b>Items</b><br/>• Domain"]):::startNode
n2{"Criterion?"}:::decisionNode
n3(["<b>Type A</b><br/>• Has trait"]):::altDx
n4(["<b>Type B</b><br/>• Lacks trait"]):::dispoNode
n1 --> n2
n2 -->|"Present"| n3
n2 -->|"Absent"| n4
n3 --> n4
```
